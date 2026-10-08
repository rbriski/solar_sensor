#!/usr/bin/env python3
"""Create private receiver settings, dashboard assets and portable user units.

Does not start services, configure Tailscale, or replace existing credentials.
Run with the receiver virtual environment's Python.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
from urllib.parse import urlsplit, quote

ROOT = Path(__file__).resolve().parent


def unit_value(value, executable_argument=True):
    # ExecStart parses quoted words and expands $. EnvironmentFile takes one
    # literal path (including spaces), with % expansion but no quote removal.
    value = str(value).replace('%', '%%')
    if not executable_argument:
        return value
    value = value.replace('$', '$$')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def env_value(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def create_private(path, content):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    return True


def install(home, public_url, python):
    if any(c in str(value) for value in (public_url, home, python) for c in ("\n", "\r", "\0")):
        raise ValueError("Paths and URL must not contain control characters")
    url = urlsplit(public_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('public URL must be HTTPS without credentials, query or fragment')
    if url.path != '/solar-roof/ingest' or url.port not in (None, 443, 8443, 10000):
        raise ValueError('Use /solar-roof/ingest on Funnel port 443, 8443 or 10000')
    config_dir = home/'.config/solar-sensor'
    state_dir = home/'.local/share/solar-sensor'
    unit_dir = home/'.config/systemd/user'
    for p in (config_dir, state_dir, unit_dir):p.mkdir(parents=True, exist_ok=True)
    config_path = config_dir/'collector.json'
    config = json.loads((ROOT/'collector.example.json').read_text())
    config.update(database=str(state_dir/'readings.sqlite3'), snapshot=str(state_dir/'public/latest.json'),
                  ingest_token=secrets.token_urlsafe(32))
    created = create_private(config_path, json.dumps(config, indent=2)+'\n')
    # An update retains the existing database, snapshot and token.
    config = json.loads(config_path.read_text())
    public = Path(config['snapshot']).expanduser().parent
    public.mkdir(parents=True, exist_ok=True)
    page = (ROOT/'static/index.html').read_text()
    page = page.replace("'latest.json?t='", json.dumps(quote(Path(config['snapshot']).name) + '?t='))
    (public/'index.html').write_text(page)
    shutil.copy2(ROOT/'transport_status.js', public/'transport-status.js')
    env_path = config_dir/'transport-watchdog.env'
    env = (f'SOLAR_PUBLIC_URL={env_value(public_url)}\nSOLAR_LOCAL_URL=http://127.0.0.1:{config.get("http_port",8790)}/ingest\n'
           f'SOLAR_SNAPSHOT={env_value(config["snapshot"])}\nSOLAR_FUNNEL_AUTO_RECOVERY=0\n')
    create_private(env_path, env)
    replacements = dict(PYTHON=python, COLLECTOR=ROOT/'collector.py', CONFIG=config_path,
                        WATCHDOG=ROOT/'transport_watchdog.py', ENV=env_path)
    for name in ('solar-sensor-collector.service','solar-sensor-transport.service',
                 'solar-sensor-transport-recover.service','solar-sensor-transport.timer'):
        content = (ROOT/name).read_text()
        for key,value in replacements.items():
            content=content.replace('@'+key+'@',unit_value(value, executable_argument=key != 'ENV'))
        (unit_dir/name).write_text(content)
    return config_path, created


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--home', type=Path, default=Path.home(), help='Installation home (override for isolated checks)')
    args=parser.parse_args()
    try:
        path,created=install(args.home.expanduser().resolve(), args.public_url, Path(sys.executable).absolute())
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(('Created' if created else 'Kept existing')+' private config: '+str(path))
    print('Installed dashboard assets and user units. No services started. Follow monitor/README.md.')


if __name__=='__main__':main()
