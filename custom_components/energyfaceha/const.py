"""Constants for the EnergyFace Solar Controller integration."""

DOMAIN = "energyface"
DEFAULT_HOST = "10.10.10.90"

# Telemetry parser mapping indices from telemetry string:
# Cidla#45#0#24.9 °C#NaN °C#71.8 °C#0.0 °C#...#48.3 °C#65.0 °C#...
INDEX_SOLAR_COLLECTOR = 3
INDEX_BOILER_TOP = 5
INDEX_BOILER_BOTTOM = 11
INDEX_SOLAR_PIPE = 12
INDEX_PUMP2_STATUS = 22

# Commands for OUT2 (Pump 2 - Solární čerpadlo)
CMD_PUMP2_AUTO = "b13"
CMD_PUMP2_ON = "b14"
CMD_PUMP2_OFF = "b15"
