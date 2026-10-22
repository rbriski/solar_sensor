#!/usr/bin/env python3
"""Build, explicitly publish, inspect or withdraw private USB firmware releases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from firmware_releases import FirmwareReleases, describe_image, identity, private_json, sensor_name

SOURCE = Path(__file__).resolve().parents[1] / 'firmware/usb_sensor'


def build(root, sensor, release, version, secrets_path, esphome, report_seconds=60):
    identity(sensor, release, version)
    if not 10 <= report_seconds <= 3600:
        raise ValueError('report interval must be 10..3600 seconds')
    destination = root / 'prepared' / str(release)
    if destination.exists():
        raise ValueError('prepared release already exists; use a new release number')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Build below the private release directory; source and artifacts contain secrets.
    with tempfile.TemporaryDirectory(dir=root, prefix='.build-') as tmp:
        tmp = Path(tmp)
        for name in ('usb_sensor.yaml', 'update_policy.h', 'usb_runtime.h', 'partitions.csv'):
            shutil.copyfile(SOURCE / name, tmp / name)
        for header in (SOURCE.parent / 'diagnostics').glob('*.h'):
            shutil.copyfile(header, tmp / header.name)
        shutil.copyfile(secrets_path, tmp / 'secrets.yaml')
        os.chmod(tmp / 'secrets.yaml', 0o600)
        command = [esphome, '-s', 'node_name', sensor, '-s', 'firmware_release', str(release),
                   '-s', 'firmware_version', version, '-s', 'report_seconds', str(report_seconds),
                   'compile', str(tmp / 'usb_sensor.yaml')]
        # Compiler output can include secret-substituted source lines on error.
        log = root / ('build-' + str(release) + '.log')
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
        sdkconfig = (tmp / '.esphome/build' / sensor / ('sdkconfig.' + sensor)).read_text()
        if 'CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y' not in sdkconfig.splitlines():
            raise ValueError('build did not enable bootloader rollback')
        output = tmp / '.esphome/build' / sensor / 'build'
        image = (output / 'firmware.ota.bin').read_bytes()
        meta = describe_image(image, sensor, release, version)
        factory = (output / 'firmware.factory.bin').read_bytes()
        destination.mkdir(parents=True, mode=0o700)
        for name, data in (('firmware.ota.bin', image), ('firmware.factory.bin', factory)):
            fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
        private_json(destination / 'build.json', dict(meta, report_interval_seconds=report_seconds,
                     factory_sha256=hashlib.sha256(factory).hexdigest()))
    return destination


def publish_prepared(releases, release):
    path = releases.root / 'prepared' / str(release)
    meta = json.loads((path / 'build.json').read_text())
    data = (path / 'firmware.ota.bin').read_bytes()
    actual = describe_image(data, releases.sensor, release, meta['version'])
    if any(meta.get(key) != value for key, value in actual.items()):
        raise ValueError('prepared release metadata or image changed')
    return releases.publish(path / 'firmware.ota.bin', release, meta['version'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    commands = parser.add_subparsers(dest='action', required=True)
    compile_cmd = commands.add_parser('build', help='Compile privately; does not publish or upload')
    compile_cmd.add_argument('--release', type=int, required=True)
    compile_cmd.add_argument('--version', required=True)
    compile_cmd.add_argument('--secrets', type=Path, default=SOURCE / 'secrets.yaml')
    compile_cmd.add_argument('--esphome', default='esphome')
    compile_cmd.add_argument('--report-seconds', type=int, default=60)
    publish_cmd = commands.add_parser('publish', help='Offer a prepared release; devices install automatically')
    publish_cmd.add_argument('--release', type=int, required=True)
    commands.add_parser('status')
    commands.add_parser('withdraw', help='Stop offering updates; does not downgrade devices')
    args = parser.parse_args()
    try:
        cfg = json.loads(args.config.expanduser().read_text())
        sensor = sensor_name(cfg['sensor'])
        root = Path(cfg['firmware_root']).expanduser().resolve()
        public = Path(cfg['snapshot']).expanduser().resolve().parent
        if root == public or public in root.parents:
            raise ValueError('firmware_root must be outside the public dashboard')
        releases = FirmwareReleases(root, sensor)
        if args.action == 'build':
            path = build(root, sensor, args.release, args.version, args.secrets.expanduser(), args.esphome, args.report_seconds)
            print('Prepared (not published): ' + str(path))
        elif args.action == 'publish':
            print(json.dumps(publish_prepared(releases, args.release), indent=2))
        elif args.action == 'withdraw':
            releases.withdraw()
            print('Update withdrawn. Installed firmware is unchanged.')
        else:
            print(json.dumps(releases.manifest(), indent=2))
    except subprocess.CalledProcessError as exc:
        parser.error(f'Build exited {exc.returncode}; inspect the private build log in firmware_root')
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
