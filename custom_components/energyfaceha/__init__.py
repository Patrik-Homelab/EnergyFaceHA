"""The EnergyFace Solar Controller integration."""
from __future__ import annotations

import asyncio
import logging
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    INDEX_SOLAR_COLLECTOR,
    INDEX_BOILER_TOP,
    INDEX_BOILER_BOTTOM,
    INDEX_SOLAR_PIPE,
    INDEX_PUMP2_STATUS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.BINARY_SENSOR]


class EnergyFaceDataCoordinator(DataUpdateCoordinator):
    """Class to manage real-time WebSocket push updates from EnergyFace."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"EnergyFace ({host})",
        )
        self.host = host
        self.data = {}
        self.ws_url = f"http://{host}:81/"
        self._listen_task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._cmd_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self):
        """Start background WebSocket listener task."""
        self._listen_task = asyncio.create_task(self._ws_loop())

    async def stop(self):
        """Stop background task."""
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_command(self, payload: str):
        """Queue command payload to be sent over the active WebSocket connection."""
        _LOGGER.info("Queueing command '%s' for EnergyFace WebSocket", payload)
        await self._cmd_queue.put(payload)

    async def _ws_loop(self):
        """Persistent WebSocket loop streaming live telemetry updates."""
        while True:
            try:
                self._session = aiohttp.ClientSession()
                _LOGGER.info("Connecting to EnergyFace WebSocket stream at %s", self.ws_url)
                async with self._session.ws_connect(self.ws_url, timeout=10) as ws:
                    cycle = 0
                    while True:
                        # Process any commands queued by HA UI first over the active socket
                        while not self._cmd_queue.empty():
                            cmd = self._cmd_queue.get_nowait()
                            _LOGGER.info("Sending command '%s' over active WebSocket", cmd)
                            await ws.send_str(cmd)
                            try:
                                cmd_msg = await asyncio.wait_for(ws.receive(), timeout=5)
                                if cmd_msg.type == aiohttp.WSMsgType.TEXT:
                                    if self._parse_telemetry(cmd_msg.data):
                                        self.async_set_updated_data(self.data)
                            except Exception as cmd_err:
                                _LOGGER.warning("Error receiving response for command '%s': %s", cmd, cmd_err)

                        # Request live telemetry ("l")
                        await ws.send_str("l")
                        msg = await asyncio.wait_for(ws.receive(), timeout=10)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            _LOGGER.warning("EnergyFace WebSocket received non-text frame type %s. Reconnecting...", msg.type)
                            break

                        if self._parse_telemetry(msg.data):
                            self.async_set_updated_data(self.data)

                        # Periodically send 'p' command to refresh mode settings (Nastaveni)
                        cycle += 1
                        if cycle % 3 == 0:
                            await ws.send_str("p")
                            p_msg = await asyncio.wait_for(ws.receive(), timeout=10)
                            if p_msg.type == aiohttp.WSMsgType.TEXT:
                                if self._parse_telemetry(p_msg.data):
                                    self.async_set_updated_data(self.data)
                            elif p_msg.type != aiohttp.WSMsgType.TEXT:
                                _LOGGER.warning("EnergyFace WebSocket received non-text frame type %s during 'p' command. Reconnecting...", p_msg.type)
                                break

                        await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("EnergyFace WebSocket disconnected (%s). Reconnecting in 5s...", err)
            finally:
                if self._session and not self._session.closed:
                    await self._session.close()
            
            await asyncio.sleep(5)

    def _parse_telemetry(self, raw_text: str) -> bool:
        """Parse raw hash-separated string telemetry from controller."""
        if not raw_text or "#" not in raw_text:
            return False

        updated = False

        # 1. Parse settings frame (Nastaveni / Nastavení) for pump mode
        lower_raw = raw_text.lower()
        nastaveni_idx = -1
        for kw in ("nastavení#", "nastaveni#", "nastaven"):
            idx = lower_raw.find(kw)
            if idx != -1:
                nastaveni_idx = idx
                break

        if nastaveni_idx != -1:
            clean_nast = raw_text[nastaveni_idx:]
            parts_nast = clean_nast.split("#")
            for idx in (16, 17, 15):
                if idx < len(parts_nast):
                    mode_code = parts_nast[idx].strip().lower()
                    if mode_code in ("0", "13", "b13", "auto"):
                        self.data["pump2_mode"] = "AUTO"
                        updated = True
                        break
                    elif mode_code in ("1", "14", "b14", "on", "zapnuto"):
                        self.data["pump2_mode"] = "ON"
                        updated = True
                        break
                    elif mode_code in ("2", "15", "b15", "off", "vypnuto"):
                        self.data["pump2_mode"] = "OFF"
                        updated = True
                        break

        # 2. Parse telemetry frame (Cidla) for sensors and physical relay state
        cidla_idx = raw_text.find("Cidla#")
        if cidla_idx != -1:
            clean_text = raw_text[cidla_idx:]
            parts = clean_text.split("#")
            _LOGGER.debug("Raw WS telemetry (%d parts): %s", len(parts), clean_text)
            self.data["raw"] = parts

            def parse_float(idx: int) -> float | None:
                if idx < len(parts):
                    val_str = parts[idx].replace("°C", "").replace("C", "").replace(",", ".").strip()
                    if val_str.lower() in ("nan", "null", "err", ""):
                        return None
                    try:
                        return float(val_str)
                    except ValueError:
                        return None
                return None

            # Extract targeted sensors
            collector_val = parse_float(INDEX_SOLAR_COLLECTOR)
            if collector_val is not None:
                self.data["solar_collector"] = collector_val

            boiler_top_val = parse_float(INDEX_BOILER_TOP)
            if boiler_top_val is not None:
                self.data["boiler_top"] = boiler_top_val

            boiler_bottom_val = parse_float(INDEX_BOILER_BOTTOM)
            if boiler_bottom_val is not None:
                self.data["boiler_bottom"] = boiler_bottom_val

            pipe_val = parse_float(INDEX_SOLAR_PIPE)
            if pipe_val is not None:
                self.data["solar_pipe"] = pipe_val
            
            # Physical active state of Relay OUT2 (Solární čerpadlo)
            def check_active(val: str) -> bool | None:
                v = val.strip().lower().rstrip(".")
                if v in ("1", "běží", "bezii", "on", "zapnuto", "running", "active"):
                    return True
                if v in ("0", "nečinný", "necinny", "off", "vypnuto", "idle", "inactive"):
                    return False
                return None

            active_state = None
            if len(parts) > INDEX_PUMP2_STATUS:
                active_state = check_active(parts[INDEX_PUMP2_STATUS])
            if active_state is None and len(parts) > 21:
                active_state = check_active(parts[21])
            if active_state is None and len(parts) > 16:
                active_state = check_active(parts[16])

            if active_state is not None:
                self.data["pump2_active"] = active_state

            updated = True

        return updated


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EnergyFace Solar Controller from a config entry."""
    host = entry.data[CONF_HOST]

    coordinator = EnergyFaceDataCoordinator(hass, host)
    await coordinator.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: EnergyFaceDataCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.stop()

    return unload_ok
