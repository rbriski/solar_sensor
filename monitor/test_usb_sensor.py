"""USB ingestion and OTA tests use dummy credentials and temporary directories."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from collector import Store, make_handler, validate
from firmware_releases import FirmwareReleases, SLOT_SIZE, describe_image, identity, private_json
from install_usb import install
from test_collector import sample
from usb_release import publish_prepared

PASSWORD = 'test-firmware-password-32-characters'
SENSOR = 'usb-temperature'


def image(release=2, sensor=SENSOR, version='1.0.1'):
    # Minimal header fixture for publisher validation, not a bootable image.
    data = bytearray(256)
    data[0] = 0xE9
    data[12] = 13
    data[32:36] = bytes.fromhex('3254cdab')
    return bytes(data) + identity(sensor, release, version)


def reading():
    return dict(sample(), sensor=SENSOR, power_mode='usb', sleep_seconds=0,
                report_interval_seconds=60, sample_sequence=1, firmware_release=1,
                firmware_version='1.0.0', firmware_checked_at=0, attempted_release=0, update_result='none')


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.releases = FirmwareReleases(self.root / 'firmware', SENSOR)
        self.binary = self.root / 'input.bin'
        self.binary.write_bytes(image())

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_withdraw_and_monotonic_releases(self):
        self.assertEqual(self.releases.manifest()['release'], 0)
        meta = self.releases.publish(self.binary, 2, '1.0.1')
        self.assertEqual(meta['sha256'], hashlib.sha256(image()).hexdigest())
        self.assertEqual(self.releases.image(2), image())
        self.assertEqual(self.releases.manifest()['release'], 2)
        self.assertEqual((self.releases.root / '2/firmware.bin').stat().st_mode & 0o777, 0o600)
        self.releases.withdraw()
        self.assertEqual(self.releases.manifest()['release'], 0)
        self.assertIsNone(self.releases.image(2))
        with self.assertRaises(ValueError):
            self.releases.publish(self.binary, 2, '1.0.1')
        self.binary.write_bytes(image(3, version='1.0.2'))
        self.releases.publish(self.binary, 3, '1.0.2')
        self.assertEqual(self.releases.manifest()['release'], 3)

    def test_rejects_wrong_board_target_release_factory_size_and_changed_image(self):
        bad_chip = bytearray(image()); bad_chip[12] = 5
        for bad in (b'', bytes(SLOT_SIZE + 1), bytes(bad_chip), image(sensor='other'), image(3),
                    image().replace(b'usb-temperature-c6-v1', b'water-softener-c6-v01'), b'factory' + image()):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                describe_image(bad, SENSOR, 2, '1.0.1')
        self.releases.publish(self.binary, 2, '1.0.1')
        (self.releases.root / '2/firmware.bin').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.releases.image(2)

    def test_prepared_artifacts_are_verified_before_publication(self):
        prepared = self.releases.root / 'prepared/2'
        prepared.mkdir(parents=True)
        (prepared / 'firmware.ota.bin').write_bytes(image())
        meta = describe_image(image(), SENSOR, 2, '1.0.1')
        private_json(prepared / 'build.json', meta)
        (prepared / 'firmware.ota.bin').write_bytes(image() + b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            publish_prepared(self.releases, 2)
        self.assertEqual(self.releases.manifest()['release'], 0)
        (prepared / 'firmware.ota.bin').write_bytes(image())
        publish_prepared(self.releases, 2)
        self.assertEqual(self.releases.manifest()['release'], 2)

    def test_concurrent_publication_cannot_reuse_release(self):
        def publish():
            try:
                self.releases.publish(self.binary, 2, '1.0.1')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(2) as executor:
            self.assertEqual(sorted(executor.map(lambda _: publish(), range(2))), [False, True])
        self.assertEqual(self.releases.image(2), image())


class UsbHttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'readings.sqlite3', SENSOR)
        self.releases = FirmwareReleases(self.root / 'firmware', SENSOR)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            self.store, 'ingest-only', releases=self.releases, firmware_password=PASSWORD))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()
        self.tmp.cleanup()

    def request(self, path, auth='', body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        connection.request('GET' if body is None else 'POST', path, body, {'Authorization': auth})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    @staticmethod
    def auth(node=SENSOR):
        return 'Basic ' + base64.b64encode(f'{node}:{PASSWORD}'.encode()).decode()

    def test_private_manifest_and_image_authentication_withdrawal_and_corruption(self):
        path = '/usb-temperature/firmware/manifest.json'
        for auth in ('', 'Bearer ingest-only', self.auth('other'), 'caf\xe9'):
            self.assertEqual(self.request(path, auth)[0], 401)
        code, body = self.request(path, self.auth())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['release'], 0)
        binary = self.root / 'test.bin'
        binary.write_bytes(image())
        self.releases.publish(binary, 2, '1.0.1')
        self.assertEqual(self.request('/firmware/2.bin', self.auth()), (200, image()))
        self.assertEqual(self.request('/firmware/2.bin', 'Bearer ingest-only')[0], 401)
        self.assertEqual(self.request('/firmware/1.bin', self.auth())[0], 404)
        for path in ('/firmware/../catalog.json', '/collector.json', '/other/firmware/2.bin', '/firmware/2.bin?token=x'):
            self.assertEqual(self.request(path, self.auth())[0], 404)
        (self.releases.root / '2/firmware.bin').write_bytes(b'corrupt')
        self.assertEqual(self.request('/firmware/2.bin', self.auth())[0], 503)
        self.releases.withdraw()
        self.assertEqual(self.request('/firmware/2.bin', self.auth())[0], 404)

    def test_usb_readings_durable_duplicate_safe_and_separate_from_solar(self):
        body = json.dumps(reading()).encode()
        args = ('/usb-temperature/ingest', 'Bearer ingest-only', body)
        self.assertEqual(self.request(*args), (200, b'deadbeef-1'))
        snapshot = self.store.snapshot()
        self.assertEqual(self.request(*args), (200, b'deadbeef-1'))
        self.assertEqual(self.store.snapshot(), snapshot)
        self.assertEqual(self.request('/ingest', self.auth(), body)[0], 401)
        self.assertEqual(self.request('/ingest', 'Bearer ingest-only', json.dumps(sample()).encode())[0], 400)
        self.assertEqual(self.request('/solar-roof/ingest', 'Bearer ingest-only', body)[0], 404)
        recovered = Store(self.root / 'readings.sqlite3', SENSOR)
        try:
            self.assertEqual(recovered.snapshot(), snapshot)
        finally:
            recovered.db.close()

    def test_invalid_usb_and_update_diagnostics(self):
        for patch in (dict(report_interval_seconds=True), dict(report_interval_seconds=0), dict(sleep_seconds=60),
                      dict(firmware_release=True), dict(firmware_release=2147483648), dict(firmware_version='<script>'),
                      dict(update_result='unknown'), dict(firmware_checked_at=-1)):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(dict(reading(), **patch), SENSOR)


class UsbInstallTest(unittest.TestCase):
    def test_running_receiver_serves_updates_and_recovers_readings_after_restart(self):
        from test_receiver import free_port, receiver, request
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = install(Path(tmp), 'https://example.ts.net:10000/usb-temperature', Path(sys.executable))
            config = json.loads(path.read_text())
            config['http_port'] = free_port()
            config['dashboard_port'] = free_port()
            path.write_text(json.dumps(config))
            http_port, dashboard_port = config['http_port'], config['dashboard_port']
            with receiver(path, dashboard_port):
                self.assertEqual(request(http_port, '/firmware/manifest.json')[0], 401)
                self.assertEqual(request(dashboard_port, '/collector.json')[0], 404)
                self.assertEqual(request(dashboard_port, '/firmware/catalog.json')[0], 404)
                self.assertEqual(request(http_port, '/usb-temperature/ingest', json.dumps(reading()).encode(),
                                         config['ingest_token']), (200, b'deadbeef-1'))
                for _ in range(40):
                    feed = json.loads(request(dashboard_port, '/latest.json')[1])
                    if feed['count'] == 1:
                        break
                    time.sleep(.1)
                self.assertEqual(feed['count'], 1)
                self.assertEqual(feed['firmware_available']['release'], 0)
                receipt = feed['latest']['received_at']
            Path(config['snapshot']).unlink()
            with receiver(path, dashboard_port):
                feed = json.loads(request(dashboard_port, '/latest.json')[1])
                self.assertEqual(feed['count'], 1)
                self.assertEqual(feed['latest']['received_at'], receipt)

    def test_isolated_install_and_reinstall_preserve_private_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path, created = install(home, 'https://example.ts.net:10000/usb-temperature', Path(sys.executable))
            self.assertTrue(created)
            config = json.loads(path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(config['ingest_token'], config['firmware_password'])
            config['http_port'] = 9000
            path.write_text(json.dumps(config))
            _, created = install(home, 'https://example.ts.net:10000/usb-temperature', Path(sys.executable))
            self.assertFalse(created)
            self.assertEqual(json.loads(path.read_text()), config)
            page = (Path(config['snapshot']).parent / 'index.html').read_text()
            self.assertNotIn(config['firmware_password'], page)
            self.assertNotIn(config['ingest_token'], page)
            self.assertNotIn('Battery voltage', page)
            self.assertFalse((home / '.config/solar-sensor').exists())
            units = list((home / '.config/systemd/user').iterdir())
            self.assertEqual([p.name for p in units], ['usb-temperature-collector.service'])

    def test_rejects_solar_collision_and_bad_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            for sensor, url, port in [('solar-sensor', 'https://example.test/solar-sensor', 8792),
                                      (SENSOR, 'http://example.test/usb-temperature', 8792),
                                      (SENSOR, 'https://example.test/usb-temperature/', 8792),
                                      (SENSOR, 'https://example.test/usb-temperature', 8790)]:
                with self.subTest(sensor=sensor, url=url, port=port), self.assertRaises(ValueError):
                    install(Path(tmp), url, Path(sys.executable), sensor, port)

    def test_native_recovery_policy(self):
        source = Path(__file__).with_name('usb_update_policy_test.cpp')
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'policy-test'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
