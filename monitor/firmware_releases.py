"""Private, immutable, explicitly published firmware for one USB sensor."""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
import time

TARGET = 'usb-temperature-c6-v1'
SLOT_SIZE = 0x1C0000  # Must match firmware/usb_sensor/partitions.csv.


def sensor_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', value) or len(value) > 40:
        raise ValueError('sensor must be a lowercase name with hyphens, at most 40 characters')
    return value


def identity(sensor, release, version):
    sensor_name(sensor)
    if type(release) is not int or not 1 <= release <= 2147483647:
        raise ValueError('release must be an integer from 1 to 2147483647')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?', version) or len(version) > 40:
        raise ValueError('version must have the form 1.2.3 or 1.2.3-label')
    return f'{TARGET}|{sensor}|{release}|{version}'.encode() + b'\0'


def describe_image(data, sensor, release, version):
    marker = identity(sensor, release, version)
    if not 36 <= len(data) <= SLOT_SIZE or data[0] != 0xE9 or int.from_bytes(data[12:14], 'little') != 13:
        raise ValueError('expected an ESP32-C6 OTA application image within the 0x1c0000-byte slot')
    if data[32:36] != bytes.fromhex('3254cdab') or marker not in data:
        raise ValueError('image is not the OTA application for this sensor, release and version')
    return dict(sensor=sensor, target=TARGET, release=release, version=version, size=len(data),
                md5=hashlib.md5(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())


def private_json(path, value):
    """Atomically replace a private file and flush it before exposing the release."""
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def authorized(header, sensor, password):
    expected = 'Basic ' + base64.b64encode(f'{sensor}:{password}'.encode()).decode()
    return bool(password) and hmac.compare_digest(header.encode('utf-8'), expected.encode('utf-8'))


class FirmwareReleases:
    def __init__(self, root, sensor):
        self.root = Path(root).expanduser().resolve()
        self.sensor = sensor_name(sensor)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @contextmanager
    def locked(self):
        fd = os.open(self.root / '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            catalog = self.root / 'catalog.json'
            state = json.loads(catalog.read_text()) if catalog.exists() else {
                'sensor': self.sensor, 'maximum': 0, 'desired': None}
            if state.get('sensor') != self.sensor:
                raise ValueError('firmware directory belongs to a different sensor')
            yield state

    def publish(self, image, release, version):
        data = Path(image).read_bytes()
        meta = describe_image(data, self.sensor, release, version)
        with self.locked() as state:
            if release <= state['maximum']:
                raise ValueError('release numbers must increase, including after withdrawal')
            target = self.root / str(release)
            target.mkdir(mode=0o700)  # Refuse reuse, including incomplete previous publication.
            fd = os.open(target / 'firmware.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            private_json(target / 'manifest.json', meta)
            private_json(self.root / 'catalog.json', dict(state, maximum=release, desired=release))
        return meta

    def withdraw(self):
        with self.locked() as state:
            private_json(self.root / 'catalog.json', dict(state, desired=None))

    def manifest(self):
        with self.locked() as state:
            release = state['desired']
            value = (json.loads((self.root / str(release) / 'manifest.json').read_text())
                     if release is not None else {'sensor': self.sensor, 'release': 0})
            return dict(value, checked_at=int(time.time()))

    def image(self, release):
        with self.locked() as state:
            if state['desired'] != release:
                return None
            path = self.root / str(release)
            meta = json.loads((path / 'manifest.json').read_text())
            data = (path / 'firmware.bin').read_bytes()
            if len(data) != meta['size'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
                raise ValueError('published firmware image changed')
            return data
