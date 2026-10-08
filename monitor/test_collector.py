import tempfile
import unittest
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from collector import Store, validate, make_handler


def sample():
    return dict(sensor='roof-solar-reference', event_id='deadbeef-1', temp_ok=True,
                temperature_c=25, temperature_f=77, boot_count=1, wifi_rssi_dbm=-60,
                sleep_seconds=30, reset_reason=1, sensor_rom='280664CA00000080')


class StorageTest(unittest.TestCase):
    def test_duplicate_keeps_original_freshness_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'readings.sqlite3'
            store = Store(path)
            self.assertTrue(store.add(sample(), now=10))
            self.assertFalse(store.add(sample(), now=20))
            store.db.close()
            recovered = Store(path).snapshot()
            self.assertEqual(recovered['count'], 1)
            self.assertEqual(recovered['latest']['received_at'], 10)

    def test_sensor_error_does_not_invent_temperature(self):
        d = sample(); d.update(temp_ok=False, temperature_c=None, temperature_f=None)
        validate(d)
        d['temperature_f'] = -196.6
        with self.assertRaises(ValueError): validate(d)

    def test_battery_persists_with_temperature(self):
        d = dict(sample(), battery_ok=True, battery_v=3.84, battery_adc_mv=1920)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'battery.sqlite3')
            store.add(d, now=100)
            self.assertEqual(store.snapshot()['latest']['battery_v'], 3.84)
            store.db.close()
        validate(sample())  # Old firmware remains compatible.
        validate(dict(sample(), battery_ok=False, battery_v=None, battery_adc_mv=0))

    def test_invalid_battery_fields(self):
        base = dict(sample(), battery_ok=True, battery_v=3.84, battery_adc_mv=1920)
        for patch in [dict(battery_ok='true'), dict(battery_v=True),
                      dict(battery_v=float('nan')), dict(battery_v=5),
                      dict(battery_adc_mv=float('inf')), dict(battery_adc_mv=True),
                      dict(battery_v=3.5), dict(battery_ok=False)]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(dict(base, **patch))
        with self.assertRaises(ValueError):
            validate(dict(sample(), battery_ok=True))

    def test_rejects_bad_payloads(self):
        for patch in [dict(temperature_c=float('nan')), dict(temperature_f=88),
                      dict(event_id='bad'), dict(boot_count=True), dict(temp_ok='true'),
                      dict(sensor='other'), dict(sleep_seconds=0)]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(dict(sample(), **patch))


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'readings.sqlite3')
        self.published = []
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store, 'private-token', self.publish))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def publish(self, data):
        self.published.append(data)
        raise RuntimeError('broker unavailable')

    def request(self, body=b'', token='private-token', path='/ingest', method='POST'):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        conn.request(method, path, body, {'Authorization': 'Bearer ' + token})
        response = conn.getresponse()
        result = response.status, response.read().decode()
        conn.close()
        return result

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()
        self.tmp.cleanup()

    def test_ack_is_durable_and_duplicate_does_not_republish(self):
        body = json.dumps(sample()).encode()
        self.assertEqual(self.request(body), (200, sample()['event_id']))
        saved = self.store.snapshot()
        self.assertEqual(saved['count'], 1)
        self.assertEqual(self.request(body, path='/solar-roof/ingest'), (200, sample()['event_id']))
        self.assertEqual(self.store.snapshot(), saved)
        self.assertEqual(len(self.published), 1)  # Failing downstream broker does not affect acknowledgement.
        independent = Store(Path(self.tmp.name) / 'readings.sqlite3')
        self.assertEqual(independent.snapshot(), saved)
        independent.db.close()

    def test_auth_validation_and_file_isolation(self):
        body = json.dumps(sample()).encode()
        self.assertEqual(self.request(body, token='wrong')[0], 401)
        self.assertEqual(self.request(body, token='caf\xe9')[0], 401)
        self.assertEqual(self.request(b'not json')[0], 400)
        self.assertEqual(self.request(b'\xff')[0], 400)
        self.assertEqual(self.request(b'x' * 2049)[0], 413)
        self.assertEqual(self.request(body, path='/other')[0], 404)
        self.assertEqual(self.request(path='/latest.json', method='GET')[0], 404)
        self.assertEqual(self.request(path='/collector.json', method='GET')[0], 404)
        self.assertEqual(self.store.snapshot()['count'], 0)

    def test_no_ack_on_storage_failure(self):
        self.store.db.close()
        self.assertEqual(self.request(json.dumps(sample()).encode())[0], 503)


if __name__ == '__main__': unittest.main()
