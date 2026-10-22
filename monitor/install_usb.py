#!/usr/bin/env python3
"""Prepare an independent USB receiver. Does not start services or change routes."""
import argparse
import html
import json
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit, quote

from firmware_releases import sensor_name
from install import create_private, unit_value

ROOT = Path(__file__).resolve().parent


def install(home, public_url, python, sensor='usb-temperature', http_port=8792, dashboard_port=8793):
    sensor_name(sensor)
    if sensor in ('solar-sensor', 'roof-solar-reference', 'solar-roof'):
        raise ValueError('Choose a USB sensor name distinct from the solar sensor')
    if any(c in str(value) for value in (home, public_url, python) for c in ('\n', '\r', '\0')):
        raise ValueError('Paths and URL must not contain control characters')
    url = urlsplit(public_url)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or
            url.path != '/' + sensor or url.port not in (None, 443, 8443, 10000)):
        raise ValueError('public URL must be https://HOST[:443|8443|10000]/SENSOR without a trailing slash')
    if any(type(p) is not int or not 1024 <= p <= 65535 for p in (http_port, dashboard_port)) or http_port == dashboard_port:
        raise ValueError('Use distinct unprivileged HTTP and dashboard ports')
    if {http_port, dashboard_port} & {8790, 8791}:
        raise ValueError('Ports 8790 and 8791 are reserved for the solar receiver')
    config_dir = home / '.config' / sensor
    state_dir = home / '.local/share' / sensor
    unit_dir = home / '.config/systemd/user'
    for path in (config_dir, state_dir, unit_dir):
        path.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'collector.json'
    config = dict(sensor=sensor, database=str(state_dir / 'readings.sqlite3'),
                  snapshot=str(state_dir / 'public/latest.json'), ingest_token=secrets.token_urlsafe(32),
                  firmware_password=secrets.token_urlsafe(32), firmware_root=str(state_dir / 'firmware'),
                  public_url=public_url, http_port=http_port, dashboard_port=dashboard_port, mqtt_enabled=False)
    created = create_private(config_path, json.dumps(config, indent=2) + '\n')
    config = json.loads(config_path.read_text())
    if config.get('sensor') != sensor:
        raise ValueError('Existing receiver config belongs to a different sensor')
    public = Path(config['snapshot']).expanduser().parent
    public.mkdir(parents=True, exist_ok=True)
    firmware_root = Path(config['firmware_root']).expanduser().resolve()
    if public.resolve() == firmware_root or public.resolve() in firmware_root.parents:
        raise ValueError('Firmware must be outside the dashboard public directory')
    page = (ROOT / 'static/usb.html').read_text().replace('@SENSOR@', html.escape(sensor))
    page = page.replace("'latest.json?t='", json.dumps(quote(Path(config['snapshot']).name) + '?t='))
    (public / 'index.html').write_text(page)
    (public / 'diagnostics.js').write_text((ROOT / 'diagnostics.js').read_text())
    unit = (ROOT / 'solar-sensor-collector.service').read_text()
    unit = unit.replace('Solar roof sensor HTTPS ingestion and live status', sensor + ' HTTPS ingestion and firmware updates')
    for key, value in dict(PYTHON=python, COLLECTOR=ROOT / 'collector.py', CONFIG=config_path).items():
        unit = unit.replace('@' + key + '@', unit_value(value))
    (unit_dir / (sensor + '-collector.service')).write_text(unit)
    return config_path, created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--sensor', default='usb-temperature')
    parser.add_argument('--http-port', type=int, default=8792)
    parser.add_argument('--dashboard-port', type=int, default=8793)
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    try:
        path, created = install(args.home.expanduser().resolve(), args.public_url, Path(sys.executable).absolute(),
                                args.sensor, args.http_port, args.dashboard_port)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(('Created' if created else 'Kept existing') + ' private config: ' + str(path))
    print('Prepared dashboard and collector unit. No services started. Follow docs/usb-sensor.md.')


if __name__ == '__main__':
    main()
