"""Binary sensor platform for EnergyFace Solar Controller."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EnergyFaceDataCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EnergyFace binary sensor based on a config entry."""
    coordinator: EnergyFaceDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyFacePumpBinarySensor(coordinator, entry)])


class EnergyFacePumpBinarySensor(CoordinatorEntity[EnergyFaceDataCoordinator], BinarySensorEntity):
    """Representation of the Solární čerpadlo physical running state (ON / OFF)."""

    _attr_name = "EnergyFace Solární čerpadlo stav"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        coordinator: EnergyFaceDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pump2_running_state"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"EnergyFace Controller ({coordinator.host})",
            manufacturer="EnergyFace / SDS",
            model="EFx20 / SDS Micro",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the pump relay is physically active / running."""
        return self.coordinator.data.get("pump2_active")
