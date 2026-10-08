# Parts and tools

[Overview](../README.md) · [Wiring next](wiring.md)

## Electronics

| Quantity | Part | Selection notes |
| --- | --- | --- |
| 1 | Seeed XIAO ESP32-C6 | This build uses the **C6**, with two 7-pin headers at 2.54 mm pitch. |
| 1 | Waterproof DS18B20 probe, three wires | Powered three-wire mode. Original 24 AWG stranded leads: red/power, black/ground, yellow/data; confirm your probe's assignment. |
| 1 | 4.7 kΩ resistor | Data pull-up to 3V3. A breadboard adapter may already contain it. |
| 1 | Probe screw-terminal adapter, optional | Useful for stranded leads on the breadboard. The original adapter's `472` resistor is the pull-up. |
| 1 | DFRobot Solar Power Manager 5V, **DFR0559** | Original V1.1; check labels on your version. |
| 1 | Nominal 5 V, 2.5 W solar panel | Measured **130 × 150 × 2.5 mm**, about 1 mm extra wire thickness at center. Verify compatibility with DFR0559 input limits. |
| 1 | Protected rechargeable **single-cell 3.7 V lithium battery**, 2000 mAh | Original pack marked EEMB LP103454, **measured 54 × 33 × 10 mm**. Packaging varies; check dimensions, allowed charge current and temperature limits. |
| 1 | Short USB-A to USB-C cable | Manager USB OUT to C6. Tested cable requires 45 mm beyond the DFRobot for its bend. |
| 1 | Breadboard and jumpers | Logic/probe only; charging current goes through manager connectors. |
| 1 | Isolated-pad perfboard, **30 × 70 mm** | 10 holes across × 24 along, 2.54 mm pitch. Tray assumes **66 × 26 mm mounting-hole centers**, roughly 2 mm holes. Measure yours. |
| 1 | Three-position screw terminal, **2.54 mm pitch** | Accepts the probe wire size; mounts at **W7, W8, W9**. A 5.08 mm block will not fit. |
| As needed | Insulated hookup wire and bare tinned wire | Insulated point-to-point connections on top; short bridges and shared rails underneath. |

Optional battery sensing needs **two 100 kΩ, 1% resistors; one 100 nF ceramic capacitor; one two-pin header and removable shunt**. Read the [power-off limitation](wiring.md#optional-battery-voltage) first.

The [Seeed pin table](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/) identifies D2 as GPIO2 and D0/A0 as GPIO0. Check substituted panels or cells against the [DFRobot requirements](https://wiki.dfrobot.com/dfr0559/).

## Enclosure supplies

| Quantity | Part | Fit used by the CAD |
| --- | --- | --- |
| 2 | PG7 nylon glands, seals and locknuts | Original cable range **3.1–6.6 mm**; 13.2 mm wall holes, 2.4 mm wall. Check actual gland and cable. |
| 1 | **AS568-164 O-ring**, EPDM, 70A | 158.42 mm nominal inside diameter × 2.62 mm cross section; fits the rounded rectangular lid groove. |
| 1 | White PETG filament | Original label: nozzle 225–240 °C, bed 70–80 °C. |
| 1 | Soft 10 mm hook-and-loop battery strap | Secure without compressing the pouch. |
| 2–3 | UV-resistant 2.5 mm-wide cable ties | Fit the probe arm's paired slots. |
| As needed | Stainless fasteners | Complete [size, length and type table](../hardware/enclosure/README.md#fasteners); board/tray screws are self-tapping, enclosure joints use machine screws and nuts. |

## Tools

Multimeter, temperature-controlled soldering iron, solder, flush cutters, 24 AWG wire stripper, tweezers, small manual screwdrivers, USB data cable and calipers. A Linux computer with Python 3.10+ receives data; Arduino CLI builds/uploads firmware. A printer is needed for the supplied enclosure or a custom mount.
