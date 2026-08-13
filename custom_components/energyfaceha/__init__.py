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

    async def _sender_loop(self, ws: aiohttp.ClientWebSocketResponse):
        """Background task sending periodic requests ('l', 'p') and user commands over the active socket."""
        cycle = 0
        while True:
            try:
                # 1. Dispatch any user commands queued from HA UI
                while not self._cmd_queue.empty():
                    cmd = self._cmd_queue.get_nowait()
                    _LOGGER.info("Sending command '%s' over active WebSocket", cmd)
                    await ws.send_str(cmd)

                # 2. Periodically send 'l' for live telemetry (every 5 seconds)
                await ws.send_str("l")

                # 3. Periodically send 'p' for mode settings (every 30 seconds)
                cycle += 1
                if cycle % 6 == 0:
                    await ws.send_str("p")

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("Error in WebSocket sender loop: %s", err)
                break

    async def _ws_loop(self):
        """Persistent WebSocket loop streaming live telemetry updates."""
        while True:
            sender_task: asyncio.Task | None = None
            try:
                self._session = aiohttp.ClientSession()
                _LOGGER.info("Connecting to EnergyFace WebSocket stream at %s", self.ws_url)
                async with self._session.ws_connect(self.ws_url, timeout=10) as ws:
                    # Start background sender task for periodic polling & command dispatch
                    sender_task = asyncio.create_task(self._sender_loop(ws))

                    # Continuous receiver loop: immediately consumes incoming frames as they arrive (0 buffer buildup)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            if self._parse_telemetry(msg.data):
                                self.async_set_updated_data(dict(self.data))
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            _LOGGER.warning("EnergyFace WebSocket frame type %s received. Reconnecting...", msg.type)
                            break

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("EnergyFace WebSocket disconnected (%s). Reconnecting in 5s...", err)
            finally:
                if sender_task and not sender_task.done():
                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass
                if self._session and not self._session.closed:
                    await self._session.close()

            await asyncio.sleep(5)

    def _parse_telemetry(self, raw_text: str) -> bool:
        """Parse raw hash-separated string telemetry from controller."""
        if not raw_text or "#" not in raw_text:
            return False

        updated = False

        # Split multi-line messages to handle concatenated WebSocket frames
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or "#" not in line:
                continue

            # 1. Parse settings frame (Nastaveni / Nastavení) for pump mode
            lower_line = line.lower()
            nastaveni_idx = -1
            for kw in ("nastavení#", "nastaveni#", "nastaven"):
                idx = lower_line.find(kw)
                if idx != -1:
                    nastaveni_idx = idx
                    break

            if nastaveni_idx != -1:
                clean_nast = line[nastaveni_idx:]
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
            cidla_idx = line.find("Cidla#")
            if cidla_idx != -1:
                clean_text = line[cidla_idx:]
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
