"""The EnergyFace Solar Controller integration."""
from __future__ import annotations

import asyncio
import logging
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT]


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

    async def start(self):
        """Start background WebSocket listener task."""
        self._listen_task = asyncio.create_task(self._ws_loop())

    async def stop(self):
        """Stop background task."""
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self._session:
            await self._session.close()

    async def send_command(self, payload: str):
        """Send command code over WebSocket to hardware."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, timeout=5) as ws:
                    await ws.send_str(payload)
                    _LOGGER.debug("Sent command '%s' to %s", payload, self.ws_url)
        except Exception as err:
            _LOGGER.error("Failed to send command '%s' to EnergyFace: %s", payload, err)

    async def _ws_loop(self):
        """Persistent WebSocket loop streaming live telemetry updates."""
        while True:
            try:
                self._session = aiohttp.ClientSession()
                _LOGGER.info("Connecting to EnergyFace WebSocket stream at %s", self.ws_url)
                async with self._session.ws_connect(self.ws_url) as ws:
                    # Request continuous telemetry
                    await ws.send_str("l")
                    
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            raw_text = msg.data
                            self._parse_telemetry(raw_text)
                            self.async_set_updated_data(self.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("EnergyFace WebSocket disconnected (%s). Reconnecting in 5s...", err)
            finally:
                if self._session and not self._session.closed:
                    await self._session.close()
            
            await asyncio.sleep(5)

    def _parse_telemetry(self, raw_text: str):
        """Parse raw hash-separated string telemetry from controller."""
        # Example format: Cidla#45#0#24.9 °C#NaN °C#71.8 °C#0.0 °C#...
        parts = raw_text.split("#")
        self.data["raw"] = parts

        def parse_float(idx: int) -> float | None:
            if idx < len(parts):
                val_str = parts[idx].replace("°C", "").strip()
                try:
                    return float(val_str)
                except ValueError:
                    return None
            return None

        # Extract targeted sensors
        self.data["solar_collector"] = parse_float(3)
        self.data["boiler_top"] = parse_float(5)
        self.data["boiler_bottom"] = parse_float(11)
        self.data["solar_pipe"] = parse_float(12)
        
        # Pump state logic
        if len(parts) > 22:
            self.data["pump2_active"] = parts[22].strip() == "1"


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
