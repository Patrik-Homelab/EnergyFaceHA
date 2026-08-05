# EnergyFace Home Assistant Integration (Custom Component)

This repository contains a full Home Assistant custom integration for the **EnergyFace (EFx20 / SDS Micro)** solar thermal controller.

---

## 📁 Repository & HACS Layout

The repository is structured for Home Assistant (and HACS compatibility):

```text
EnergyFaceHomeAsistant/
├── README.md
├── home_assistant_integration.md
└── custom_components/
    └── energyfaceha/            <-- Domain name
        ├── __init__.py
        ├── binary_sensor.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── select.py
        ├── sensor.py
        └── strings.json
```

### Installation Steps

1. Copy the `custom_components/energyfaceha` directory into your Home Assistant `/config/custom_components/` directory:
   ```bash
   cp -r custom_components/energyfaceha /config/custom_components/
   ```
2. Restart **Home Assistant**.
3. In Home Assistant, go to **Settings** -> **Devices & Services** -> **Add Integration**.
4. Search for **EnergyFace Solar Controller**.
5. Enter your controller's IP address (default: `10.10.10.90`) and submit.

---

## ⚡ Created Entities

| Entity ID | Entity Name | Description |
| --- | --- | --- |
| `sensor.energyface_solarni_kolektor` | Solar Panel / Collector | Live Collector Temp (°C) |
| `sensor.energyface_potrubi_solaru` | Pipe | Live Solar Pipe Temp (°C) |
| `sensor.energyface_bojler_nahore` | Boiler Top | Live Boiler Top Temp (°C) |
| `sensor.energyface_bojler_dole` | Boiler Bottom | Live Boiler Bottom Temp (°C) |
| `binary_sensor.energyface_solarni_cerpadlo_stav` | Solární čerpadlo stav | Physical relay status: `ON` (Running) / `OFF` (Idle) |
| `select.energyface_solarni_cerpadlo_rezim` | Solární čerpadlo režim | Mode command selector: `AUTO`, `ON`, `OFF` |


---

## 📊 Dashboard Widget / Card Examples

### Standard Entities Card

```yaml
type: entities
title: Solární Systém EnergyFace
entities:
  - entity: sensor.energyface_solarni_kolektor
    name: Solární Kolektor
    icon: mdi:solar-power-variant
  - entity: sensor.energyface_potrubi_solaru
    name: Potrubí Soláru
    icon: mdi:pipe
  - entity: sensor.energyface_bojler_nahore
    name: Bojler Nahoře
    icon: mdi:water-boiler
  - entity: sensor.energyface_bojler_dole
    name: Bojler Dole
    icon: mdi:water-boiler
  - entity: select.energyface_solarni_cerpadlo_rezim
    name: Režim Čerpadla
    icon: mdi:pump
```

### Grid Widget with Tile Cards

```yaml
type: grid
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.energyface_solarni_kolektor
    name: Kolektor
    color: orange
  - type: tile
    entity: sensor.energyface_potrubi_solaru
    name: Potrubí
    color: amber
  - type: tile
    entity: sensor.energyface_bojler_nahore
    name: Bojler Horní
    color: red
  - type: tile
    entity: sensor.energyface_bojler_dole
    name: Bojler Spodní
    color: blue
  - type: tile
    entity: select.energyface_solarni_cerpadlo_rezim
    name: Solární čerpadlo
    icon: mdi:pump
```
