# Firmware

[Wiring](wiring.md) · [Receiver setup](../monitor/README.md)

Run commands from the repository root. Install [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/) and give your user access to USB serial devices. Tested versions:

```bash
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@3.3.11 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli lib install 'DallasTemperature@4.0.6'
arduino-cli board list
```

The URL is the [Espressif stable index](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html). The repository includes a specific [OneWire revision](../firmware/libraries/OneWire/UPSTREAM.txt) with C6 support. **Keep `--libraries firmware/libraries`** so an older global installation does not take precedence.

Replace example port `/dev/ttyACM0` with yours. It may change after reset. Before computer USB, disconnect manager USB and open the optional battery-sense jumper.

## 1. Test the probe over USB

```bash
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc --libraries firmware/libraries firmware/probe_test
arduino-cli upload --fqbn esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc --port /dev/ttyACM0 firmware/probe_test
arduino-cli monitor --port /dev/ttyACM0 --config baudrate=115200
```

The test prints about every two seconds and expects **one DS18B20 on D2**, powered at 3V3 with its pull-up. Warm the probe to confirm a response. Close the serial monitor before another upload.

## 2. Build the wireless firmware

Complete [receiver setup](../monitor/README.md) first. Obtain its HTTPS ingest URL and private `ingest_token`, plus your device network's 2.4 GHz Wi-Fi credentials.

Create the local header only if it does not already exist, then edit it:

```bash
test -f firmware/roof_sensor/secrets.h || cp -f firmware/roof_sensor/secrets.h.example firmware/roof_sensor/secrets.h
```

Set `WIFI_SSID`, `WIFI_PASSWORD`, `INGEST_URL` and `INGEST_TOKEN`. The URL looks like:

```text
https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:10000/solar-roof/ingest
```

Keep credentials out of Git, logs and AI conversations. `secrets.h` is ignored. The node uses its built-in antenna. Its Wi-Fi can be separate from the receiver network, provided DNS, NTP and HTTPS on the chosen port are reachable.

```bash
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc --libraries firmware/libraries firmware/roof_sensor
arduino-cli upload --fqbn esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc --port /dev/ttyACM0 firmware/roof_sensor
```

Each wake reads the probe, joins Wi-Fi, obtains time, verifies TLS, posts a reading and checks the acknowledged event ID. An independent 20-second deadline bounds failed wakes. Missed readings are not queued.

| Compile setting | Default | Meaning |
| --- | --- | --- |
| `ROOF_SLEEP_SECONDS` | `300` | Seconds asleep after each wake; range 1–3600 |
| `ROOF_BATTERY_SENSE` | `0` | Optional supervised divider; see [limits](wiring.md#optional-battery-voltage) |
| `ROOF_TEST_WIFI_FAILURE` | `0` | Test-only: nonexistent SSID on first wake |
| `ROOF_TEST_HTTPS_FAILURE` | `0` | Test-only: unavailable ingest path on second wake |

For a quick bench cycle, add `--build-property 'build.extra_flags=-DROOF_SLEEP_SECONDS=30'` to compilation. For supervised voltage testing, use `--build-property 'build.extra_flags=-DROOF_SLEEP_SECONDS=30 -DROOF_BATTERY_SENSE=1'`. Upload that compiled sketch. Rebuild with ordinary defaults afterward. These settings do not change firmware already on a device.

`ca_cert.h` contains public ISRG Root X1. A future certificate-authority change may require replacing this trust anchor. Do not bypass TLS verification to hide an SSL error. The node synchronizes time before checking certificates.

## 3. Verify without a computer cable

Confirm a fresh reading, then move USB to the manager using the [power procedure](wiring.md#battery-and-solar-power). Verify the receiver time advances next wake. Old dashboard values are historical data.

`temp_ok=false` and null temperatures mean the online node reported a probe error. `battery_ok=false` with null voltage is normal when sensing is off. `event_id` combines a random power-session ID and wake counter. `previous_failures`, `previous_stage` and `previous_http_status` help locate faults.

## Upload recovery

Deep sleep can remove the serial port before upload. Open J1 and use computer USB. Hold C6 **BOOT**, press/release **RESET**, then release BOOT; select the newly enumerated port and upload. Press RESET to run the application. This BOOT is separate from the DFRobot's power button.

The [firmware check script](../scripts/check_firmware.sh) compiles with dummy credentials and never uploads.
