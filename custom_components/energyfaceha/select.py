"""Select platform for controlling EnergyFace pump modes."""
from __future__ import annotations

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EnergyFaceDataCoordinator
from .const import (
    DOMAIN,
    CMD_PUMP2_AUTO,
    CMD_PUMP2_ON,
    CMD_PUMP2_OFF,
)

_LOGGER = logging.getLogger(__name__)

PUMP_MODES = {
    "AUTO": CMD_PUMP2_AUTO,
    "ON": CMD_PUMP2_ON,
    "OFF": CMD_PUMP2_OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EnergyFace pump select entity based on config entry."""
    coordinator: EnergyFaceDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyFacePumpSelect(coordinator, entry)])


class EnergyFacePumpSelect(CoordinatorEntity[EnergyFaceDataCoordinator], SelectEntity):
    """Representation of the Solární čerpadlo (OUT2) mode selector."""

    _attr_name = "EnergyFace Solární čerpadlo režim"
    _attr_options = ["AUTO", "ON", "OFF"]
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        coordinator: EnergyFaceDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pump2_mode"
        self._attr_current_option = "AUTO"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"EnergyFace Controller ({coordinator.host})",
            manufacturer="EnergyFace / SDS",
            model="EFx20 / SDS Micro",
        )

    @property
    def current_option(self) -> str:
        """Return the current selected pump mode."""
        return self.coordinator.data.get("pump2_mode", self._attr_current_option or "AUTO")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and trigger relay command over WebSocket."""
        cmd = PUMP_MODES.get(option)
        if cmd:
            _LOGGER.info("Sending pump mode selection '%s' (%s) to controller", option, cmd)
            self._attr_current_option = option
            self.coordinator.data["pump2_mode"] = option
            self.async_write_ha_state()
            await self.coordinator.send_command(cmd)
            await self.coordinator.send_command("p")
