"""Unit tests for EnergyFace telemetry parsing logic."""
import unittest
from unittest.mock import MagicMock
import sys
from types import ModuleType

# Mock aiohttp and homeassistant if not present
if "aiohttp" not in sys.modules:
    aiohttp_mock = ModuleType("aiohttp")
    aiohttp_mock.ClientSession = MagicMock()
    aiohttp_mock.WSMsgType = MagicMock()
    sys.modules["aiohttp"] = aiohttp_mock

if "homeassistant" not in sys.modules:
    ha_mock = ModuleType("homeassistant")
    ha_config_entries = ModuleType("homeassistant.config_entries")
    ha_const = ModuleType("homeassistant.const")
    ha_core = ModuleType("homeassistant.core")
    ha_helpers = ModuleType("homeassistant.helpers")
    ha_helpers_uc = ModuleType("homeassistant.helpers.update_coordinator")
    
    class FakeDataUpdateCoordinator:
        def __init__(self, hass, logger, name):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.data = {}

        def async_set_updated_data(self, data):
            self.data = data

    ha_config_entries.ConfigEntry = MagicMock()
    ha_const.CONF_HOST = "host"
    ha_const.Platform = MagicMock()
    ha_core.HomeAssistant = MagicMock()
    ha_helpers_uc.DataUpdateCoordinator = FakeDataUpdateCoordinator

    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_uc

from custom_components.energyfaceha import EnergyFaceDataCoordinator


class TestEnergyFaceParsing(unittest.TestCase):
    def setUp(self):
        self.coordinator = EnergyFaceDataCoordinator(MagicMock(), "10.10.10.90")

    def test_parse_cidla_telemetry(self):
        # 23 elements in telemetry frame
        # Index 3: Kolektor (62.5), Index 5: Bojler nahoře (71.8), Index 11: Potrubí (65.0), Index 12: Bojler dole (48.3), Index 22: Pump active ("1")
        raw = "Cidla#45#0#62.5 °C#NaN °C#71.8 °C#0.0 °C#0#0#0#0#65.0 °C#48.3 °C#0#0#0#0#0#0#0#0#Běží.#1"
        res = self.coordinator._parse_telemetry(raw)
        self.assertTrue(res)
        self.assertEqual(self.coordinator.data.get("solar_collector"), 62.5)
        self.assertEqual(self.coordinator.data.get("boiler_top"), 71.8)
        self.assertEqual(self.coordinator.data.get("solar_pipe"), 65.0)
        self.assertEqual(self.coordinator.data.get("boiler_bottom"), 48.3)
        self.assertEqual(self.coordinator.data.get("pump2_active"), True)

    def test_parse_comma_temperatures(self):
        raw = "Cidla#45#0#62,5 °C#NaN °C#71,8 °C#0.0 °C#0#0#0#0#65,0 °C#48,3 °C#0#0#0#0#0#0#0#0#Nečinný.#0"
        res = self.coordinator._parse_telemetry(raw)
        self.assertTrue(res)
        self.assertEqual(self.coordinator.data.get("solar_collector"), 62.5)
        self.assertEqual(self.coordinator.data.get("boiler_bottom"), 48.3)
        self.assertEqual(self.coordinator.data.get("solar_pipe"), 65.0)
        self.assertEqual(self.coordinator.data.get("boiler_top"), 71.8)
        self.assertEqual(self.coordinator.data.get("pump2_active"), False)

    def test_parse_nastaveni_mode(self):
        # Test ASCII "Nastaveni#"
        raw = "Nastaveni#0#0#0#0#0#0#0#0#0#0#0#0#0#0#0#1" # Index 16 is "1" (ON)
        res = self.coordinator._parse_telemetry(raw)
        self.assertTrue(res)
        self.assertEqual(self.coordinator.data.get("pump2_mode"), "ON")

        # Test Czech diacritics "Nastavení#"
        raw_auto = "Nastavení#0#0#0#0#0#0#0#0#0#0#0#0#0#0#0#0" # Index 16 is "0" (AUTO)
        res_auto = self.coordinator._parse_telemetry(raw_auto)
        self.assertTrue(res_auto)
        self.assertEqual(self.coordinator.data.get("pump2_mode"), "AUTO")

        # Test command mode code "b15" or "15"
        raw_off = "Nastavení#0#0#0#0#0#0#0#0#0#0#0#0#0#0#0#b15"
        res_off = self.coordinator._parse_telemetry(raw_off)
        self.assertTrue(res_off)
        self.assertEqual(self.coordinator.data.get("pump2_mode"), "OFF")

    def test_necinny_text_active_status(self):
        # Index 21 has "Nečinný."
        raw = "Cidla#45#0#25.0 °C#NaN °C#50.0 °C#0.0 °C#0#0#0#0#30.0 °C#25.0 °C#0#0#0#0#0#0#0#0#Nečinný."
        res = self.coordinator._parse_telemetry(raw)
        self.assertTrue(res)
        self.assertEqual(self.coordinator.data.get("pump2_active"), False)

        # Index 21 has "Běží."
        raw_running = "Cidla#45#0#25.0 °C#NaN °C#50.0 °C#0.0 °C#0#0#0#0#30.0 °C#25.0 °C#0#0#0#0#0#0#0#0#Běží."
        res_running = self.coordinator._parse_telemetry(raw_running)
        self.assertTrue(res_running)
        self.assertEqual(self.coordinator.data.get("pump2_active"), True)


if __name__ == "__main__":
    unittest.main()
