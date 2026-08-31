# Solar-Powered Roof Temperature Sensor

An independent, solar-powered Wi-Fi temperature node mounted beside the pool's
rooftop solar collectors. It reads a DS18B20 probe every five minutes and
publishes over MQTT, so the reading can be logged next to the Pentair
EasyTouch's **Solar Temp** for comparison. The EasyTouch remains the
authoritative pool controller — this node only measures and reports.

**Hardware:** Seeed XIAO ESP32-C3 · DFRobot DFR0559 Solar Power Manager 5V ·
waterproof DS18B20 · 5 V / 2.5 W panel · 3.7 V 2000 mAh LiPo · IP65 enclosure.

## Docs

| Doc | What it is |
|---|---|
| [`docs/solar_powered_roof_temperature_sensor.md`](docs/solar_powered_roof_temperature_sensor.md) | Design spec — architecture, part requirements, wiring, firmware behavior, scope boundary |
| [`docs/solar_sensor_build_guide.html`](docs/solar_sensor_build_guide.html) | Step-by-step build guide — firmware → breadboard → perfboard → enclosure → roof, with diagrams, full sketch, and checklists |

The build guide is a self-contained HTML page; GitHub shows its source, so view
it locally:

```sh
open docs/solar_sensor_build_guide.html
```
