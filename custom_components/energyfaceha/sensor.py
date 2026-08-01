"""Sensor platform for EnergyFace Solar Controller."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    """Set up EnergyFace sensors based on a config entry."""
    coordinator: EnergyFaceDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        EnergyFaceSensor(coordinator, entry, "solar_collector", "Solární kolektor", "collector_temp"),
        EnergyFaceSensor(coordinator, entry, "solar_pipe", "Potrubí soláru", "pipe_temp"),
        EnergyFaceSensor(coordinator, entry, "boiler_top", "Bojler nahoře", "boiler_top_temp"),
        EnergyFaceSensor(coordinator, entry, "boiler_bottom", "Bojler dole", "boiler_bottom_temp"),
    ]

    async_add_entities(sensors)


class EnergyFaceSensor(CoordinatorEntity[EnergyFaceDataCoordinator], SensorEntity):
    """Representation of an EnergyFace Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: EnergyFaceDataCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unique_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.key = key
        self._attr_name = f"EnergyFace {name}"
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"EnergyFace Controller ({coordinator.host})",
            manufacturer="EnergyFace / SDS",
            model="EFx20 / SDS Micro",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.key)
