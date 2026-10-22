# USB-powered temperature sensor

[Solar build](../README.md) · [Firmware source](../firmware/usb_sensor/usb_sensor.yaml) · [Receiver source](../monitor/collector.py)

This variant uses the same **Seeed XIAO ESP32-C6** and **one DS18B20** as the solar sensor. A continuous 5 V USB supply powers the board. It stays connected to Wi-Fi, reports every **60 seconds**, and checks for an approved firmware release every **hour**, starting 90 seconds after boot. Both intervals can be changed when building. The provisional sensor ID is `usb-temperature`.

There is no DFR0559, battery, solar panel, battery divider or deep sleep. The original solar wiring, Arduino firmware and enclosure remain separate and reproducible. The separate [pipe-mounted enclosure](../hardware/water-enclosure/README.md) includes a black-PETG X2D project, grey DS16-P USB entry and PG7 probe entry for the 2.75-inch pipe.

## Hardware and wiring

Use the [adapter-board wiring diagram](usb-wiring/index.html) for the supplied probe board with its fitted pull-up. The illustrated guide is also published in [Gas City Reports](https://gascity.tail96374b.ts.net/reports/solar-sensor/usb-wiring/).

Use the XIAO **C6** pinout and the same probe adapter/pull-up described in the [wiring guide](wiring.md#probe-on-usb-power). Make connections with USB unplugged:

| XIAO ESP32-C6 | Probe adapter |
| --- | --- |
| 3V3 | VCC |
| GND | GND |
| D2 / GPIO2 | DAT |

DAT needs a **4.7 kΩ pull-up to 3V3**. The existing adapter already has one; do not add another when reusing that adapter. Verify the new probe's lead functions rather than relying solely on colors. Power the C6 through its USB-C connector; probe VCC remains **3V3**, not USB 5 V. Leave D0 and the battery pads unused.

The existing [USB probe test](firmware.md#1-test-the-probe-over-usb) can check the probe first. The final USB firmware is ESPHome/ESP-IDF, matching the water-softener update approach. It does not require Home Assistant and has no Home Assistant API or inbound OTA service enabled. It selects the onboard C6 antenna using GPIO3 and GPIO14.

## Prepare a separate receiver

Run from the repository root. The solar receiver can continue using ports 8790/8791. This instance defaults to **8792** for ingestion/private firmware and **8793** for its private dashboard:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r monitor/requirements.txt
.venv/bin/python monitor/install_usb.py \
  --public-url 'https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:10000/usb-temperature'
```

This prepares `~/.config/usb-temperature/collector.json`, a `usb-temperature-collector.service` user unit and a dashboard. It does **not** start services or change network routes. Reinstalling preserves the existing credentials and settings. Use `--sensor NAME` and a matching URL path for a different identity; select unused ports when installing more than one USB instance.

The private config contains separate `ingest_token` and `firmware_password` values. Data and firmware live under `~/.local/share/usb-temperature/`; only the `public/` subdirectory is suitable for private dashboard hosting. **Firmware images contain device credentials. Never put them in Git, a public release, or the report directory.**

At deployment time, enable the new service and add its public path alongside existing routes:

```bash
systemctl --user daemon-reload
systemctl --user enable --now usb-temperature-collector.service
systemctl --user status usb-temperature-collector.service --no-pager
tailscale serve status
tailscale funnel status
tailscale funnel --bg --https=10000 --set-path=/usb-temperature http://127.0.0.1:8792
```

Use the established Funnel hostname/port and preserve the existing solar and water-softener routes. The device needs outbound Wi-Fi access to DNS, NTP and HTTPS. It does not join the tailnet. Serve the dashboard's public directory or port 8793 through a **tailnet-only** route, as in the [receiver hosting guide](../monitor/README.md#2-route-public-ingestion-and-private-viewing). Do not expose the dashboard, config or database through Funnel. No second automatic Tailscale recovery service is installed.

## Build and provision once over USB

Install the pinned ESPHome version in its own environment:

```bash
python3 -m venv .venv-usb
.venv-usb/bin/python -m pip install -r firmware/usb_sensor/requirements.txt
test -f firmware/usb_sensor/secrets.yaml || cp -f firmware/usb_sensor/secrets.yaml.example firmware/usb_sensor/secrets.yaml
chmod 600 firmware/usb_sensor/secrets.yaml
```

Edit the ignored `secrets.yaml` locally. Set Wi-Fi credentials, `receiver_url` (the HTTPS base path, **without** `/ingest` or a trailing slash), and the two credentials from `collector.json`. Do not paste them into chat or logs. If using another sensor ID, the receiver config and firmware build must use the same ID.

The release builder compiles both a USB factory image and an OTA application image into a private directory. It does not publish or upload:

```bash
.venv/bin/python monitor/usb_release.py \
  --config ~/.config/usb-temperature/collector.json build \
  --release 1 --version 1.0.0 --report-seconds 60 \
  --esphome "$PWD/.venv-usb/bin/esphome"
```

The outputs are in `~/.local/share/usb-temperature/firmware/prepared/1/`. Compiler logs stay in the private firmware directory because error messages can contain substituted credentials. A prepared release number is never overwritten.

Identify the **new C6** serial port before uploading. The following example uses `/dev/ttyACM0`; do not assume that is the correct device. Initial provisioning must use the **factory** image so that the rollback-capable bootloader and two OTA slots are installed together:

```bash
.venv-usb/bin/esphome upload firmware/usb_sensor/usb_sensor.yaml \
  --device /dev/ttyACM0 \
  --file ~/.local/share/usb-temperature/firmware/prepared/1/firmware.factory.bin
.venv-usb/bin/esphome logs firmware/usb_sensor/usb_sensor.yaml --device /dev/ttyACM0
```

The partition table is explicitly for **4 MB flash**, with two `0x1c0000`-byte application slots. Future OTA releases must preserve that layout; a partition-layout or bootloader change needs USB provisioning. If another node name or reporting interval was used for the prepared image, that prepared image already contains those settings; the upload command transfers the specified file.

Expect a first reading after Wi-Fi/time synchronization and the next sample cycle. Warm the probe to check response. Disconnecting the probe produces null temperatures and a visible fault; each sample rescans the bus so a probe reconnected later can recover. Exactly one DS18B20 is accepted. Wi-Fi failures retry automatically; missed samples are not buffered.

## Automatic updates

The node checks a private HTTPS manifest, accepts only a higher integer release for its identity and the `usb-temperature-c6-v1` target, and downloads into the inactive slot. The manifest and image both require separate firmware authentication. Redirects are disabled; TLS certificate checking stays enabled. The image's MD5 must match before activating the new slot. HTTPS authenticates the source; MD5 checks transfer integrity, not a firmware signature.

To release a change, increment the release number and version. **Build first; publish only when ready for the device to install it automatically.**

```bash
.venv/bin/python monitor/usb_release.py \
  --config ~/.config/usb-temperature/collector.json build \
  --release 2 --version 1.0.1 --report-seconds 60 \
  --esphome "$PWD/.venv-usb/bin/esphome"
.venv/bin/python monitor/usb_release.py \
  --config ~/.config/usb-temperature/collector.json publish --release 2
.venv/bin/python monitor/usb_release.py \
  --config ~/.config/usb-temperature/collector.json status
```

Publishing verifies the prepared SHA-256, C6 application header and embedded sensor/release identity. It stores immutable private image bytes and atomically changes the offered release. A device already running that release does not reinstall it. Update results and the last successful check appear in subsequent readings and on the USB dashboard. Temperature delivery still requires the receiver to commit the event before acknowledging its exact ID; duplicate attempts keep their original receipt time.

Normal manifest requests time out after 3 seconds; firmware downloads have a 10-second inactivity timeout and an independent 180-second restart deadline. Reporting pauses while an image is downloaded and flashed, then resumes after reboot. A failed transfer or checksum check normally leaves the previous slot selected and retries on the next hourly check. A reset during an installation attempt conservatively blocks that release; publish a higher release number to try again. A bootloader rollback also blocks the failed release so it cannot create an update loop.

The new image is confirmed after 60 seconds of normal ESPHome runtime. This protects against early boot crashes; it is **not** proof of working probe wiring, network credentials or application behavior. A release with incorrect credentials can still need USB recovery. Withdrawal stops further downloads but cannot cancel an in-flight image or downgrade an already updated device:

```bash
.venv/bin/python monitor/usb_release.py \
  --config ~/.config/usb-temperature/collector.json withdraw
```

To restore old behavior remotely, build the known-good source as a **new, higher release**. For USB recovery, hold BOOT, press/release RESET, release BOOT, identify the newly enumerated port and upload a known-good factory image. The removable enclosure lid provides USB recovery access without removing the cable seal.

## Validation and current limits

```bash
.venv/bin/python -m unittest discover -s monitor -v
ESPHOME_BIN="$PWD/.venv-usb/bin/esphome" bash scripts/check_usb_firmware.sh
python3 scripts/check_docs.py
git diff --check
```

The firmware check copies only source and **dummy** credentials into a temporary build directory. It never reads the real secrets, publishes an update or uploads hardware. Tests use temporary receiver databases and firmware catalogs. Before unattended use, verify a real USB bootstrap, temperature response, Wi-Fi update to a higher release, unplug/replug probe recovery, interrupted download and early-crash rollback on the new board. USB bootstrap, temperature response and an automatic update to release 2 have passed on the installed board. Probe reconnect and fault-recovery checks remain pending. The enclosure CAD and native X2D project checks have passed; physical fit and sealing still need verification.

References: [Seeed XIAO ESP32-C6](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/), [ESPHome HTTP OTA](https://esphome.io/components/ota/http_request/), [ESP32 rollback configuration](https://esphome.io/components/esp32/). The update pattern follows this workspace's water-softener system, with its battery gating and daily sleep removed.
