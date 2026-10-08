# Troubleshooting

[Build overview](../README.md) · [Receiver commands](../monitor/README.md)

Use the **last received time** and dashboard transport check together. A temperature still visible on screen may be a stored historical value. Firmware normally sleeps five minutes after each wake; the dashboard allows more than two expected cycles before declaring a reading overdue.

| Symptom | Check and next action |
| --- | --- |
| No C6 power from solar manager | Meter manager USB output and C6 5V/GND. Check USB cable, output-enable jumper, battery polarity and manager BOOT. Keep optional J1 open during power changes. |
| Reverse-battery indicator | Disconnect sources and verify BAT IN polarity with a meter. Connector fit does not prove polarity. |
| About battery voltage on C6 3V3 | Stop and recheck wiring; 3V3 should be about 3.3 V, not 3.8–4.2 V. |
| Node online, `temp_ok=false` | Power off, then check probe ground, 3V3, D2, the 4.7 kΩ pull-up and terminal grip. Firmware expects exactly one DS18B20. Run USB probe test if needed. |
| Battery voltage missing | Expected with default firmware or J1 open. Read [sense-circuit limits](wiring.md#optional-battery-voltage) before enabling. Never substitute a floating A0 value for a battery measurement. |
| Wi-Fi joins but HTTPS fails | Device Wi-Fi must permit DNS, NTP and chosen HTTPS port. Verify URL/token, public DNS and valid receiver certificate; do not disable TLS checks. |
| SSL protocol error; local collector healthy | Inspect public transport status. A Funnel relay/session fault can interrupt TLS before HTTP. The watchdog can reconnect only after its guarded conditions; it is not a cure for every SSL error. |
| Public route healthy, sensor overdue | Check device power, Wi-Fi reception and probe/firmware logs. Reconnecting healthy Tailscale will not repair an offline sensor. |
| Dashboard says collector unavailable | Check `solar-sensor-collector.service`, its journal and snapshot path. A dashboard server can still serve old files when the collector is stopped. |
| Unauthorized ingest response | A token-free health check should get 401. Firmware must use the exact private token configured on the receiver. |
| USB serial disappears | Normal during deep sleep. Use [BOOT/RESET upload recovery](firmware.md#upload-recovery). |
| Works open, fails after closing | Inspect pinched cables, shifted probe terminal wires and Wi-Fi attenuation. Verify a new receipt time after every reassembly. |

For maintenance, first open the battery sense jumper if fitted, disconnect solar and manager USB as needed, and use only one USB source for the C6. Restore power and ground before reconnecting a supervised sense circuit. Keep exposed battery leads and tools from touching each other.

Receiver recovery was added after a public HTTPS route failed while local ingestion remained healthy. It checks the actual public path, persists its incident state and bounds reconnect attempts. It cannot guarantee uninterrupted Internet access or recover a discharged battery. The receiver preserves history across restarts, while the node resumes with a fresh sample when connectivity returns.
