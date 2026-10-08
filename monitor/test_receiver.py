"""Exercise a fresh installation and restart without MQTT or live services."""
import contextlib
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from install import install
from test_collector import sample

ROOT = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def request(port, path, body=None, token=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    conn.request('POST' if body is not None else 'GET', path, body, headers)
    response = conn.getresponse()
    value = response.status, response.read()
    conn.close()
    return value


@contextlib.contextmanager
def receiver(config, port):
    process = subprocess.Popen([sys.executable, str(ROOT/'collector.py'), '--config', str(config)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise AssertionError(process.stderr.read().decode())
            try:
                if request(port, '/latest.json')[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(.1)
        else:
            raise AssertionError('receiver did not start')
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stderr.close()


class ReceiverTest(unittest.TestCase):
    def test_fresh_install_delivers_and_recovers_without_broker(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _ = install(Path(tmp), 'https://example.ts.net:10000/solar-roof/ingest', Path(sys.executable))
            cfg = json.loads(config_path.read_text())
            cfg['http_port'] = free_port()
            cfg['dashboard_port'] = free_port()
            config_path.write_text(json.dumps(cfg))
            with receiver(config_path, cfg['dashboard_port']):
                self.assertEqual(request(cfg['http_port'], '/ingest', b'{}')[0], 401)
                self.assertEqual(request(cfg['dashboard_port'], '/collector.json')[0], 404)
                html = request(cfg['dashboard_port'], '/')[1]
                self.assertIn(b'transport-status.js', html)
                self.assertNotIn(cfg['ingest_token'].encode(), html)
                status, ack = request(cfg['http_port'], '/ingest', json.dumps(sample()).encode(), cfg['ingest_token'])
                self.assertEqual((status, ack.decode()), (200, sample()['event_id']))
                for _ in range(40):
                    feed = json.loads(request(cfg['dashboard_port'], '/latest.json')[1])
                    if feed['count'] == 1: break
                    time.sleep(.1)
                self.assertEqual(feed['count'], 1)
                self.assertFalse(feed['mqtt_enabled'])
                receipt = feed['latest']['received_at']
            # Remove stale snapshot so readiness proves the restarted process wrote it.
            Path(cfg['snapshot']).unlink()
            with receiver(config_path, cfg['dashboard_port']):
                feed = json.loads(request(cfg['dashboard_port'], '/latest.json')[1])
                self.assertEqual(feed['count'], 1)
                self.assertEqual(feed['latest']['received_at'], receipt)


if __name__ == '__main__': unittest.main()
