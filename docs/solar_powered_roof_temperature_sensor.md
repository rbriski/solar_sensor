# Solar-Powered Wi-Fi Roof Temperature Sensor

## Project goal

Build a small, independent temperature-monitoring node on the roof beside the pool's solar collectors. The node will:

- Measure the temperature at the collectors approximately every five minutes.
- Send the reading over the home's 2.4 GHz Wi-Fi network.
- Operate from a rechargeable battery kept charged by a small solar panel.
- Avoid running a long temperature-sensor cable from the roof to the pool equipment pad.
- Avoid using a second Raspberry Pi.
- Leave the Pentair EasyTouch as the authoritative pool controller.

The first purpose is measurement and comparison: log the independent rooftop reading beside the EasyTouch **Solar Temp**, air temperature, and pool-water temperature. Feeding the new value back into Pentair control logic is a separate later phase.

## Final architecture

```text
        Small 5 V solar panel
                  |
                  v
    DFRobot DFR0559 Solar Power Manager
          |                         |
          |                         +--> 1-cell 3.7 V Li-ion/LiPo battery
          |
          +--> regulated 5 V USB output
                         |
                         v
                 ESP32 Wi-Fi board
                         |
                         +--> DS18B20 temperature sensor kit
                         |
                         +--> Wi-Fi --> MQTT or HTTP --> logger/database
```

The **DFRobot DFR0559** is the complete power subsystem. It accepts the solar-panel input, charges the battery, protects the battery and output, boosts the battery voltage to regulated 5 V, and powers the ESP32. There is no separate charger, boost converter, regulator, protection board, or generic power-bank module.

The **ESP32** only handles sensing and communications. It wakes on a timer, reads the sensor, connects to Wi-Fi, sends one reading, and returns to deep sleep.

## Required parts

| Qty. | Part | Selected or required specification | Purpose |
|---:|---|---|---|
| 1 | **DFRobot Solar Power Manager 5V, DFR0559 V1.1** | Use the current V1.1 board | Solar charging, battery management, protection, and regulated 5 V output |
| 1 | **ESP32 board** | Recommended: **Seeed Studio XIAO ESP32-C3** with its external antenna; another 5 V USB-powered ESP32 with deep sleep may be substituted | Reads the sensor and publishes over Wi-Fi |
| 1 | **DFRobot Gravity Waterproof DS18B20 Temperature Sensor Kit, KIT0021** | Buy the complete kit, not only a bare probe | Waterproof digital temperature probe plus the resistor/terminal adapter and cable |
| 1 | **5 V outdoor solar panel** | Approximately 1-3 W; operating voltage within 4.5-6 V; **open-circuit voltage must remain below 6.5 V** | Recharges the battery through the DFR0559 |
| 1 | **Single-cell 3.7 V Li-ion or LiPo battery** | Approximately 2,000-3,000 mAh; reputable cell; protected battery preferred | Overnight and cloudy-weather reserve |
| 1 | **Short USB-A-to-USB-C cable** | Short enough to remain inside the enclosure | Connects DFR0559 USB OUT to the XIAO ESP32-C3 USB-C input |
| 1 | **Plastic outdoor enclosure** | White or light gray, UV-resistant, IP65/IP67 or better, roughly 4 × 4 × 2 inches or larger | Protects the power manager, ESP32, battery, and connections |
| 2 | **Waterproof cable glands** | Sized for the solar lead and DS18B20 cable | Weatherproof cable entries and strain relief |
| 1 | **Small perfboard or mounting plate** | Any convenient size | Mechanically secures the boards and wiring |
| As needed | **Hookup wire, standoffs, heat-shrink, UV-rated cable clips, and mounting hardware** | Outdoor-rated where exposed | Assembly and installation |

### Do not substitute these items

- Do **not** use a LiFePO4 battery with the DFR0559. It is designed for a conventional 3.7 V lithium battery that charges to 4.2 V.
- Do **not** assume that any panel marketed as "6 V" is safe. Verify the panel's open-circuit voltage; the DFR0559 solar input must not exceed 6.5 V.
- Do **not** connect the battery to both the DFR0559 and the ESP32's own battery input. The battery belongs only on the DFR0559.
- Do **not** use a generic USB power-bank board that turns itself off when the ESP32 enters deep sleep.

## Electrical connections

### Power connections

```text
Solar-panel positive  --> DFR0559 SOLAR IN +
Solar-panel negative  --> DFR0559 SOLAR IN -

Battery positive      --> DFR0559 BAT IN +
Battery negative      --> DFR0559 BAT IN -

DFR0559 USB OUT       --> ESP32 USB input
```

For the recommended XIAO ESP32-C3, use the DFR0559's USB output and a short USB-A-to-USB-C cable. This avoids adding the diode that Seeed specifies when externally feeding the XIAO through its exposed 5 V pin.

The XIAO's battery pads remain unused.

### Temperature-sensor connections

The DFRobot KIT0021 includes the pull-up-resistor/terminal adapter, so no loose resistor needs to be added.

```text
DS18B20 kit VCC       --> ESP32 3V3
DS18B20 kit GND       --> ESP32 GND
DS18B20 kit DATA      --> XIAO D2 / GPIO4
```

Power the sensor kit from **3.3 V**, not 5 V, so its data signal remains appropriate for the ESP32. Follow the labels on the supplied adapter rather than relying only on probe-wire colors, because DFRobot documents more than one probe color scheme.

## Firmware behavior

The software should perform this cycle:

1. Wake from deep sleep on the ESP32's RTC timer.
2. Read the DS18B20 temperature.
3. Connect to the home 2.4 GHz Wi-Fi network.
4. Publish the reading by MQTT or send it by HTTP.
5. Return to deep sleep for approximately 300 seconds.

A hard Wi-Fi/publish timeout should be included. For example, if it cannot connect and send within 15-20 seconds, it should abandon that sample and return to sleep rather than remain awake and drain the battery.

### Recommended data format

MQTT is the cleanest transport because the existing Raspberry Pi can run or reach an MQTT broker and then forward the reading to InfluxDB, Home Assistant, Grafana, Node-RED, or another logger.

Suggested MQTT topic:

```text
pool/solar-roof/temperature
```

Suggested payload:

```json
{
  "sensor": "roof-solar-reference",
  "temperature_f": 118.4,
  "wifi_rssi_dbm": -67,
  "boot_count": 1532
}
```

The receiving system can timestamp the message. Battery-voltage reporting is deliberately omitted from the base design because the DFR0559 manages the battery but does not provide digital state-of-charge telemetry to the ESP32. Adding battery telemetry would require another measurement circuit or fuel-gauge module.

## Physical installation

### Temperature probe

Mount the DS18B20 probe immediately beside the existing Pentair solar-temperature sensor:

- On the same roof surface.
- With the same orientation and sunlight exposure.
- Close enough that shading and airflow are effectively the same.
- Not touching a collector, solar pipe, or moving valve component.
- Not buried under reflective tape, insulation, or a large mounting block that would materially change its temperature.

The stainless DS18B20 probe has different thermal mass from the Pentair thermistor, so brief differences during passing clouds are normal. Stable-sun periods and longer-term trends are the best comparison.

### Electronics and battery

- Mount the enclosure **under or behind a collector in shade**, or under a nearby eave if only a short local sensor lead is required.
- Expose only the small charging panel and the temperature probe to full sun.
- Use a plastic enclosure so Wi-Fi is not blocked by a metal box.
- Install cable glands on a downward-facing side and add drip loops.
- Keep the Wi-Fi antenna away from the battery and large metal objects.
- Avoid drilling new roof penetrations solely for this sensor; use existing collector framing or a roof-appropriate mounting method.

The battery should not sit in a sealed dark box in direct rooftop sun. The DFR0559 protects against electrical faults, but it does not measure battery temperature.

## Commissioning plan

### Bench test

1. Assemble the DFR0559, battery, ESP32, and DS18B20 indoors.
2. Charge the battery through the DFR0559 USB input.
3. Program the ESP32 and confirm one reading every five minutes.
4. Confirm that the ESP32 wakes normally after repeated deep-sleep cycles.
5. Confirm that the logger receives temperature and Wi-Fi RSSI.

### Roof test

1. Temporarily place the assembled node near the intended roof location.
2. Confirm reliable Wi-Fi before permanently mounting anything.
3. Connect the solar panel and confirm the DFR0559 charging indicator responds in sun.
4. Run the system for several days before sealing the final enclosure.

### Comparison test

Log these values on the same timeline:

- Independent DS18B20 rooftop temperature.
- EasyTouch Solar Temp.
- EasyTouch or independent air temperature.
- Pool-water temperature.
- Solar valve state and pump state, when available through the existing EasyTouch/RS-485 setup.

Compare the two rooftop readings during stable sun, early morning warm-up, passing clouds, and afternoon cool-down. A consistent offset suggests calibration or mounting differences; sudden erratic differences suggest a sensor, connection, or placement problem.

## Scope boundary

This project gets a reliable independent roof temperature reading onto Wi-Fi. It does **not** directly replace the Pentair solar sensor or make EasyTouch consume a network value. EasyTouch's native solar-temperature input is a physical 10 kΩ thermistor connection. Any later method for injecting or using the new Wi-Fi reading in control logic should be treated as a separate integration project.

## Final result

The completed device will be a compact solar-powered rooftop sensor node with this operating loop:

```text
Wake --> measure --> connect to Wi-Fi --> publish --> sleep for five minutes
```

The DFR0559 handles the power-management work; the ESP32 handles Wi-Fi; and the complete DFRobot DS18B20 kit avoids a loose pull-up resistor or custom analog measurement circuit.

## Reference documents

- DFRobot Solar Power Manager 5V, DFR0559 product page and technical wiki.
- DFRobot Gravity Waterproof DS18B20 Temperature Sensor Kit, KIT0021 product documentation.
- Seeed Studio XIAO ESP32-C3 hardware and deep-sleep documentation.
- Espressif ESP32 sleep-mode documentation.
- Pentair EasyTouch/IntelliTouch Load Center Installation Guide, solar-temperature-sensor section.
