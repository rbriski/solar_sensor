#!/usr/bin/env bash
# Isolated build with dummy credentials. Never reads secrets.yaml or uploads.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT
python3 - "$repo_dir" "$build_dir" "${ESPHOME_BIN:-esphome}" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

repo, root, esphome = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(repo / 'monitor'))
from usb_release import build

try:
    path = build(root, 'usb-temperature', 1, '1.0.0',
                 repo / 'firmware/usb_sensor/secrets.yaml.example', esphome)
except (subprocess.CalledProcessError, ValueError, OSError):
    log = root / 'build-1.log'
    if log.exists():
        print('\n'.join(log.read_text(errors='replace').splitlines()[-60:]))
    raise
meta = json.loads((path / 'build.json').read_text())
print(f"PASS: C6 USB factory/OTA build, rollback bootloader, verified release identity; {meta['size']} bytes")
PY
