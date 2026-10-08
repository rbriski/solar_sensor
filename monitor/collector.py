#!/usr/bin/env python3
"""Persist authenticated HTTPS readings; optionally relay MQTT; write UI snapshots."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import functools
from http.server import SimpleHTTPRequestHandler
import paho.mqtt.client as mqtt

TOPIC = 'pool/solar-roof/temperature'
ACK_TOPIC = 'pool/solar-roof/ack'
SENSOR = 'roof-solar-reference'


def validate(data):
    if not isinstance(data, dict) or data.get('sensor') != SENSOR:
        raise ValueError('unknown sensor')
    if not isinstance(data.get('event_id'), str) or not re.fullmatch(r'[0-9a-f]{8}-[0-9]+', data['event_id']):
        raise ValueError('invalid event ID')
    if type(data.get('temp_ok')) is not bool:
        raise ValueError('invalid temperature status')
    for field, low, high in [('boot_count', 1, 4294967295), ('wifi_rssi_dbm', -127, 0), ('sleep_seconds', 1, 3600), ('reset_reason', 0, 100)]:
        if type(data.get(field)) is not int or not low <= data[field] <= high:
            raise ValueError('invalid ' + field)
    if data['temp_ok']:
        for key, lo, hi in [('temperature_c', -55, 125), ('temperature_f', -67, 257)]:
            v = data.get(key)
            if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError('invalid ' + key)
        if abs(data['temperature_f'] - (data['temperature_c'] * 1.8 + 32)) > 0.05:
            raise ValueError('inconsistent temperature units')
    elif data.get('temperature_c') is not None or data.get('temperature_f') is not None:
        raise ValueError('failed sensor must publish null temperatures')
    if not isinstance(data.get('sensor_rom'), str) or not re.fullmatch('[0-9A-F]{16}|', data['sensor_rom']):
        raise ValueError('invalid sensor ROM')
    # Older firmware/history may omit all battery fields.
    battery_fields = {'battery_ok', 'battery_v', 'battery_adc_mv'}
    if battery_fields.intersection(data):
        if not battery_fields.issubset(data) or type(data['battery_ok']) is not bool:
            raise ValueError('invalid battery status')
        adc = data['battery_adc_mv']
        if type(adc) not in (int, float) or not math.isfinite(adc) or not 0 <= adc <= 3300:
            raise ValueError('invalid battery ADC')
        voltage = data['battery_v']
        if data['battery_ok']:
            if type(voltage) not in (int, float) or not math.isfinite(voltage) or not 2 <= voltage <= 4.5:
                raise ValueError('invalid battery voltage')
            if abs(voltage - adc * 0.002) > 0.005:
                raise ValueError('inconsistent battery divider voltage')
        elif voltage is not None:
            raise ValueError('failed battery reading must publish null voltage')
    return data


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS readings (event_id TEXT PRIMARY KEY, received_at REAL NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()
        self.lock = threading.Lock()

    def add(self, data, now=None):
        validate(data)
        with self.lock:
            cur = self.db.execute('INSERT OR IGNORE INTO readings VALUES (?, ?, ?)',
                                  (data['event_id'], time.time() if now is None else now, json.dumps(data)))
            self.db.commit()
            return cur.rowcount == 1

    def snapshot(self):
        with self.lock:
            rows = self.db.execute('SELECT received_at,payload FROM readings ORDER BY received_at DESC LIMIT 240').fetchall()
            count = self.db.execute('SELECT COUNT(*) FROM readings').fetchone()[0]
        history = [dict(json.loads(payload), received_at=ts) for ts, payload in reversed(rows)]
        return {'count': count, 'latest': history[-1] if history else None, 'history': history}


def atomic_json(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, allow_nan=False))
    tmp.replace(path)


def make_handler(store, token, publish=None):
    """Construct the ingest-only HTTP endpoint; it never serves static files."""
    if not isinstance(token, str) or not token or token == 'CHANGE_ME':
        raise ValueError('Set a nonempty private ingest_token')

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, code, body):
            encoded = body.encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            self.reply(404, 'Not found')

        def do_POST(self):
            if self.path not in ('/ingest', '/solar-roof/ingest'):
                self.reply(404, 'Not found')
                return
            # compare_digest(str, str) rejects non-ASCII; bytes also handles a
            # malformed header without raising an uncaught exception.
            expected = ('Bearer ' + token).encode('utf-8')
            supplied = self.headers.get('Authorization', '').encode('utf-8')
            if not hmac.compare_digest(supplied, expected):
                self.reply(401, 'Unauthorized')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 2048:
                    self.reply(413, 'Invalid body size')
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('incomplete body')
                data = validate(json.loads(body))
                inserted = store.add(data)
            except (ValueError, TypeError, UnicodeError):
                self.reply(400, 'Invalid reading')
                return
            except sqlite3.Error:
                self.reply(503, 'Storage unavailable')
                return
            if inserted:
                if publish is not None:
                    try:
                        publish(data)
                    except Exception as exc:
                        # Durable HTTPS acknowledgement is independent of MQTT.
                        print('Downstream publish failed:', type(exc).__name__, flush=True)
                print('HTTPS stored', data['event_id'], 'temperature_f=', data.get('temperature_f'), flush=True)
            self.reply(200, data['event_id'])

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    database = Path(cfg['database']).expanduser()
    database.parent.mkdir(parents=True, exist_ok=True)
    store = Store(database)
    output = Path(cfg['snapshot']).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    mqtt_enabled = cfg.get('mqtt_enabled', bool(cfg.get('username')))
    state = {'broker_connected': False, 'mqtt_enabled': mqtt_enabled, 'last_error': None}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='solar-roof-collector')
    if cfg.get('username'):
        client.username_pw_set(cfg['username'], cfg.get('password'))
    client.reconnect_delay_set(1, 10)

    def on_connect(c, userdata, flags, reason, properties):
        state['broker_connected'] = not reason.is_failure
        if not reason.is_failure:
            c.subscribe(TOPIC, qos=1)
        print('MQTT connection:', reason, flush=True)

    def on_disconnect(c, userdata, flags, reason, properties):
        state['broker_connected'] = False

    def on_message(c, userdata, msg):
        # A retained replay must never acquire a new receipt time or count as live.
        if msg.retain:
            return
        try:
            if len(msg.payload) > 2048:
                raise ValueError('oversized payload')
            data = validate(json.loads(msg.payload))
            inserted = store.add(data)
            c.publish(ACK_TOPIC, data['event_id'], qos=1, retain=False)
            state['last_error'] = None
            if inserted:
                print('Stored', data['event_id'], 'temperature_f=', data.get('temperature_f'), flush=True)
        except (ValueError, TypeError, sqlite3.Error) as exc:
            state['last_error'] = str(exc)
            print('Rejected reading:', exc, flush=True)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    if mqtt_enabled:
        client.connect_async(cfg.get('host', '127.0.0.1'), cfg.get('port', 1883), 30)
        client.loop_start()
    publish = (lambda data: client.publish(TOPIC, json.dumps(data), qos=1, retain=True)) if mqtt_enabled else None
    server = ThreadingHTTPServer(('127.0.0.1', cfg.get('http_port', 8790)), make_handler(store, cfg['ingest_token'], publish))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    dashboard = None
    if cfg.get('dashboard_port'):
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(output.parent))
        dashboard = ThreadingHTTPServer(('127.0.0.1', cfg['dashboard_port']), handler)
        threading.Thread(target=dashboard.serve_forever, daemon=True).start()
    try:
        while True:
            snapshot = store.snapshot()
            snapshot.update(state)
            snapshot['generated_at'] = time.time()
            atomic_json(output, snapshot)
            time.sleep(2)
    finally:
        server.shutdown()
        server.server_close()
        if dashboard:
            dashboard.shutdown()
            dashboard.server_close()
        if mqtt_enabled:
            client.disconnect()
            client.loop_stop()
        store.db.close()


if __name__ == '__main__':
    main()
