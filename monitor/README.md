# Linux receiver and dashboard

[Build overview](../README.md) · [Firmware next](../docs/firmware.md)

The receiver accepts token-authenticated HTTPS readings through **Tailscale Funnel**, saves them in SQLite, then acknowledges the event ID. It writes a dashboard snapshot every two seconds. A Pi or another consumer can read the receiver's data independently; MQTT is optional.

This setup needs Linux with systemd user services, Python 3.10+, and [Tailscale](https://tailscale.com/download/linux) signed in to your tailnet. Use an always-on receiver. The ESP32 does **not** run Tailscale: it reaches the public Funnel hostname from ordinary Wi-Fi. That network must allow DNS, NTP and the selected HTTPS port.

## 1. Install the receiver

Clone the repository to a permanent directory and run from its root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r monitor/requirements.txt
.venv/bin/python monitor/install.py --public-url 'https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:10000/solar-roof/ingest'
```

Replace the example hostname with this receiver's full Tailscale DNS name, visible in `tailscale status --json` under `Self.DNSName` (omit its final dot). Enable HTTPS certificates and Funnel for the node as required by your tailnet policy. The [Funnel setup guide](https://tailscale.com/docs/features/tailscale-funnel) describes those prerequisites.

The installer creates:

| Path | Contents |
| --- | --- |
| `~/.config/solar-sensor/collector.json` | Private token and receiver settings, mode 0600 |
| `~/.config/solar-sensor/transport-watchdog.env` | Public URL, snapshot path, recovery setting, mode 0600 |
| `~/.local/share/solar-sensor/readings.sqlite3` | Durable readings, created when the receiver runs |
| `~/.local/share/solar-sensor/public/` | Dashboard, latest JSON and public transport summary |
| `~/.config/systemd/user/solar-sensor-*` | User units with your actual repository/Python paths |

It generates a random `ingest_token` and **keeps existing credentials, data paths and recovery settings on reinstall**. Open `collector.json` locally to copy the token into the firmware's ignored `secrets.h`. Do not paste it into issue reports. Only HTML, JavaScript and public summaries belong in the `public` directory; keep the private config and database outside it.

The installer does not start services or change Tailscale. Run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now solar-sensor-collector.service
systemctl --user status solar-sensor-collector.service --no-pager
sudo loginctl enable-linger "$USER"
```

Lingering lets the user services run after logout and start at boot. Keep the repository and virtual environment at their installed paths; rerun the installer if moving them.

## 2. Route public ingestion and private viewing

First inspect existing routes with `tailscale serve status` and `tailscale funnel status`. The example uses **10000 for public ingestion** and **8443 for private viewing**; choose unused ports if the receiver already hosts other services.

```bash
tailscale funnel --bg --https=10000 --set-path=/solar-roof http://127.0.0.1:8790
tailscale serve --bg --https=8443 http://127.0.0.1:8791
```

If Tailscale requires administrative permission, use your established operator account or run those configuration commands with `sudo`. Funnel supports ports 443, 8443 and 10000; its [CLI reference](https://tailscale.com/docs/reference/tailscale-cli/funnel) explains persistent `--bg` routes. **Keep the dashboard on a different port:** Funnel makes a host/port public, so another path on the same port is not a private dashboard.

The ingest server binds only to loopback and serves POST `/ingest` or `/solar-roof/ingest`; it does not serve files. The optional dashboard server binds to loopback on 8791. Default URLs:

```text
Sensor URL:  https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:10000/solar-roof/ingest
Dashboard:   https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:8443/
Data feed:   https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:8443/latest.json
```

Check the public ingest route without a token. **401 Unauthorized is the expected healthy response**:

```bash
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' --request POST 'https://YOUR-RECEIVER.YOUR-TAILNET.ts.net:10000/solar-roof/ingest'
```

A browser GET returns 404 by design. View the dashboard from a tailnet-connected browser. After [uploading firmware](../docs/firmware.md), check the receipt time advances and persists after restarting the collector. Retransmission of the same event must not make an old reading look new.

## 3. Monitor transport health

```bash
systemctl --user enable --now solar-sensor-transport.timer
systemctl --user start solar-sensor-transport.service
journalctl --user -u solar-sensor-transport.service -n 20 --no-pager
```

The watchdog checks local ingestion, public DNS, Funnel routing and TLS through each public IPv4 address. It checks public DNS separately from MagicDNS so a healthy tailnet-only route cannot mask a broken public route. It combines transport results with reading age. A healthy route with an overdue sensor is a sensor/power problem, not a reason to reconnect Tailscale.

Automatic recovery defaults **off** for new installs. To enable it, allow the service user to operate Tailscale (for example, `sudo tailscale set --operator="$USER"` if appropriate for this host) and change this line in the private environment file:

```text
SOLAR_FUNNEL_AUTO_RECOVERY=1
```

The next timer run reads it. Recovery requires three consecutive qualifying failures, stale sensor data, a healthy local collector, two successful public DNS checks and failed public network/TLS transport. It excludes certificate-validation errors and ordinary HTTP authorization errors. It allows one reconnect per incident with a one-hour cooldown, and rearms after five healthy checks.

The recovery service briefly runs `tailscale down` then `tailscale up`; this affects **all Tailscale connections on that receiver**. It records a persistent recovery marker, checks preferences/routes afterward and includes an `ExecStopPost` recovery path. It does not reset Funnel configuration. Set the variable back to `0` to disable automatic reconnects while keeping monitoring. Existing installations retain their current opt-in on reinstall.

## Optional MQTT consumers

No broker is required for HTTPS ingestion or the dashboard. To relay readings, add these keys to the private collector config and restart its service:

```json
{
  "mqtt_enabled": true,
  "host": "127.0.0.1",
  "port": 1883,
  "username": "YOUR_BROKER_USER",
  "password": "YOUR_BROKER_PASSWORD"
}
```

These are additional keys, not a replacement for the full config. Use a local or appropriately secured broker; this example uses plain MQTT on loopback. Fresh events are relayed to `pool/solar-roof/temperature`, QoS 1, retained. The receiver also accepts legacy non-retained readings on that topic and acknowledges them on `pool/solar-roof/ack`. Retained MQTT messages are never treated as newly received samples.

MQTT failure does not prevent an HTTPS reading from being saved or acknowledged. MQTT relay is best effort, with no durable forwarding queue. Consumers needing a complete history should read SQLite or the receiver's snapshot instead of treating broker delivery as the system of record.

## Data and maintenance

`latest.json` contains `generated_at`, total `count`, `latest` and the latest 240 events in `history`, oldest first. Each event has receiver-generated `received_at`, the node's unique `event_id`, temperatures/status, Wi-Fi signal and sleep interval. Invalid probe temperatures and disabled/invalid battery voltage are null. Freshness uses receipt time, not value changes; a duplicate preserves its original timestamp.

SQLite table `readings` contains `event_id TEXT PRIMARY KEY`, `received_at REAL`, and the original JSON `payload`. The database keeps all events. Back it up with SQLite's backup command rather than copying a live database without its WAL:

```bash
sqlite3 "$HOME/.local/share/solar-sensor/readings.sqlite3" ".backup '/path/to/backup/readings.sqlite3'"
journalctl --user -u solar-sensor-collector.service -n 30 --no-pager
systemctl --user list-timers solar-sensor-transport.timer --no-pager
```

The dashboard keeps updating while the sensor sleeps; an overdue reading turns its status red. See [troubleshooting](../docs/troubleshooting.md) for power, probe and transport diagnosis. This receiver currently handles one sensor identity, `roof-solar-reference`; adding multiple nodes requires changes to identity validation and per-sensor dashboard storage/querying.
