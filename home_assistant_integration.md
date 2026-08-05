# Home Assistant Integration Guide: EnergyFace Solar Controller

This document outlines architectural patterns, integration strategies, and UI visual extensions for integrating the **EnergyFace (EFx20 / SDS Micro)** solar thermal controller into **Home Assistant**.

---

## 1. Direct Local Communication Protocol

The EnergyFace controller (`10.10.10.90`) exposes a real-time **WebSocket Server** on **Port 81** (`ws://10.10.10.90:81/`).

### Telemetry Stream (`ws.send("l")`)

Sending `"l"` over WebSocket streams live sensor values formatted hash-separated:

```text
Cidla#45#0#24.9 °C#NaN °C#71.8 °C#0.0 °C#...#48.3 °C#65.0 °C#...#Nečinný.#1#...
```

| Field Index | Sensor Name          | Example Reading | Entity ID in HA                      |
| ----------- | -------------------- | --------------- | ------------------------------------ |
| `3`         | Kolektor             | `24.9 °C`       | `sensor.solar_collector_temperature` |
| `5`         | Bojler Nahoře        | `71.8 °C`       | `sensor.boiler_top_temperature`      |
| `11`        | Potrubí Soláru       | `59.8 °C`       | `sensor.solar_pipe_temperature`      |
| `12`        | Bojler Dole          | `69.3 °C`       | `sensor.boiler_bottom_temperature`   |
| `22`        | Stav Čerpadla (OUT2) | `1` / `0`       | `binary_sensor.solar_pump_active`    |

### Direct Hardware Relay Commands

Sending raw string codes over WebSocket flips hardware relays in **0 ms**:

| Action                              | Hardware Relay | WebSocket Payload |
| ----------------------------------- | -------------- | ----------------- |
| Solární Čerpadlo (OUT2) **AUTO**    | Relay OUT2     | `b13`             |
| Solární Čerpadlo (OUT2) **ZAPNUTO** | Relay OUT2     | `b14`             |
| Solární Čerpadlo (OUT2) **VYPNUTO** | Relay OUT2     | `b15`             |
| Čerpadlo 1 (OUT1) **AUTO**          | Relay OUT1     | `b10`             |
| Čerpadlo 1 (OUT1) **ZAPNUTO**       | Relay OUT1     | `b11`             |
| Čerpadlo 1 (OUT1) **VYPNUTO**       | Relay OUT1     | `b12`             |

---

## 2. Integration Approaches for Home Assistant

### Option A: Home Assistant Custom Component (HACS Plugin)

Create a Python custom component under `config/custom_components/energyface_solar/`:

```text
custom_components/energyface_solar/
├── __init__.py
├── manifest.json
├── sensor.py
├── select.py
└── binary_sensor.py
```

#### `select.py` (Pump Mode Selector Entity)

```python
from homeassistant.components.select import SelectEntity
import websockets
import asyncio

PUMP_MODES = {"AUTO": "b13", "ON": "b14", "OFF": "b15"}

class SolarPumpSelect(SelectEntity):
    _attr_name = "Solární čerpadlo režim"
    _attr_options = ["AUTO", "ON", "OFF"]

    async def async_select_option(self, option: str) -> None:
        cmd = PUMP_MODES.get(option)
        if cmd:
            async with websockets.connect("ws://10.10.10.90:81/") as ws:
                await ws.send(cmd)
                self._attr_current_option = option
                self.async_write_ha_state()
```

---

### Option B: MQTT Auto-Discovery Bridge

A lightweight Node.js/Python microservice running on Docker/Raspberry Pi connecting `ws://10.10.10.90:81/` to your MQTT Broker. Home Assistant automatically discovers entities without extra plugins!

```json
// Topic: homeassistant/sensor/solar_collector/config
{
    "name": "Kolektor Teplota",
    "state_topic": "solar/collector/temperature",
    "unit_of_measurement": "°C",
    "device_class": "temperature"
}
```

---

## 3. Lovelace Visual Dashboard Card

You can embed the interactive SVG Schematic directly into Home Assistant using `custom:picture-elements` or `custom:button-card`.

```yaml
type: picture-elements
image: /local/solar_schema_background.png
elements:
    - type: state-label
      entity: sensor.solar_collector_temperature
      style:
          top: 15%
          left: 20%
          color: '#fb923c'
          font-weight: bold
          font-size: 16px

    - type: state-label
      entity: sensor.boiler_top_temperature
      style:
          top: 35%
          left: 85%
          color: '#f87171'
          font-weight: bold
          font-size: 16px

    - type: state-label
      entity: sensor.boiler_bottom_temperature
      style:
          top: 70%
          left: 85%
          color: '#60a5fa'
          font-weight: bold
          font-size: 16px

    - type: service-button
      title: Režim Čerpadla
      service: select.select_option
      target:
          entity_id: select.solarni_cerpadlo_rezim
      service_data:
          option: AUTO
      style:
          top: 90%
          left: 40%
```

---

## 4. Home Assistant Automations (Nocturnal Cooling / Safety)

```yaml
alias: 'Solár: Noční chlazení při přehřátém bojleru'
trigger:
    - platform: time
      at: '23:00:00'
condition:
    - condition: numeric_state
      entity_id: sensor.boiler_top_temperature
      above: 75
action:
    - service: select.select_option
      target:
          entity_id: select.solarni_cerpadlo_rezim
      data:
          option: 'ON'
```
