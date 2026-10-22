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
from firmware_releases import FirmwareReleases, authorized, sensor_name

TOPIC = 'pool/solar-roof/temperature'
ACK_TOPIC = 'pool/solar-roof/ack'
SENSOR = 'roof-solar-reference'


def validate(data, sensor=SENSOR):
    if not isinstance(data, dict) or data.get('sensor') != sensor:
        raise ValueError('unknown sensor')
    if not isinstance(data.get('event_id'), str) or not re.fullmatch(r'[0-9a-f]{8}-[0-9]+', data['event_id']):
        raise ValueError('invalid event ID')
    if type(data.get('temp_ok')) is not bool:
        raise ValueError('invalid temperature status')
    usb = data.get('power_mode') == 'usb'
    for field, low, high in [('boot_count', 1, 4294967295), ('wifi_rssi_dbm', -127, 0), ('sleep_seconds', 0 if usb else 1, 3600), ('reset_reason', 0, 100)]:
        if type(data.get(field)) is not int or not low <= data[field] <= high:
            raise ValueError('invalid ' + field)
    if usb:
        if data['sleep_seconds'] != 0 or type(data.get('report_interval_seconds')) is not int or not 10 <= data['report_interval_seconds'] <= 3600:
            raise ValueError('invalid USB reporting interval')
    for field, low, high in [('firmware_release', 1, 2147483647), ('attempted_release', 0, 2147483647),
                             ('firmware_checked_at', 0, 4294967295), ('sample_sequence', 1, 4294967295)]:
        if field in data and (type(data[field]) is not int or not low <= data[field] <= high):
            raise ValueError('invalid ' + field)
    if 'firmware_version' in data and (not isinstance(data['firmware_version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?', data['firmware_version']) or len(data['firmware_version']) > 40):
        raise ValueError('invalid firmware_version')
    if 'update_result' in data and data['update_result'] not in ('none', 'installed', 'failed', 'rolled_back', 'check_failed', 'installing'):
        raise ValueError('invalid update_result')
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
    if 'diagnostics' in data:
        d = data['diagnostics']
        if not isinstance(d, dict) or type(d.get('version')) is not int or d.get('version') != 1:
            raise ValueError('invalid diagnostics version')
        for key in ('devices', 'streak', 'last_good', 'boots', 'uptime', 'wifi_disconnects', 'transitions'):
            if type(d.get(key)) is not int or not 0 <= d[key] <= 4294967295:
                raise ValueError('invalid diagnostics ' + key)
        for key, choices in [('probe', range(5)), ('delivery', (10, 11, 12, 13, 14, 99))]:
            if type(d.get(key)) is not int or d[key] not in choices:
                raise ValueError('invalid diagnostics ' + key)
        if (d['probe'] == 0) != data['temp_ok']:
            raise ValueError('inconsistent probe diagnostics')
        if type(d.get('http')) is not int or not -32768 <= d['http'] <= 599:
            raise ValueError('invalid diagnostics http')
        for key in ('storage_ok', 'pending'):
            if type(d.get(key)) is not bool:
                raise ValueError('invalid diagnostics ' + key)
        history = d.get('history')
        if not isinstance(history, list) or len(history) > 4:
            raise ValueError('invalid diagnostics history')
        for event in history:
            if (not isinstance(event, list) or len(event) != 5 or
                    any(type(v) is not int or not 0 <= v <= 4294967295 for v in event) or
                    event[0] not in (0, 1, 2, 3, 4, 10, 11, 12, 13, 14, 20, 21)):
                raise ValueError('invalid diagnostics event')
    return data


class Store:
    def __init__(self, path, sensor=SENSOR):
        self.sensor = sensor_name(sensor)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS readings (event_id TEXT PRIMARY KEY, received_at REAL NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()
        self.lock = threading.Lock()

    def add(self, data, now=None):
        validate(data, self.sensor)
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


def make_handler(store, token, publish=None, releases=None, firmware_password=''):
    """Construct the ingest-only HTTP endpoint; it never serves static files."""
    if not isinstance(token, str) or not token or token == 'CHANGE_ME':
        raise ValueError('Set a nonempty private ingest_token')
    prefix = '/solar-roof' if store.sensor == SENSOR else '/' + store.sensor
    if releases is not None and (not isinstance(firmware_password, str) or len(firmware_password) < 24):
        raise ValueError('Set a separate firmware_password of at least 24 characters')

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
            path = self.path
            if path.startswith(prefix + '/'):
                path = path[len(prefix):]
            match = re.fullmatch(r'/firmware/(manifest\.json|[1-9][0-9]{0,9}\.bin)', path)
            if releases is None or not match:
                self.reply(404, 'Not found')
                return
            if not authorized(self.headers.get('Authorization', ''), store.sensor, firmware_password):
                self.reply(401, 'Unauthorized')
                return
            try:
                manifest = match[1] == 'manifest.json'
                body = (json.dumps(releases.manifest()).encode() if manifest
                        else releases.image(int(match[1][:-4])))
                if body is None:
                    self.reply(404, 'Not found')
                    return
            except (OSError, ValueError, KeyError):
                self.reply(503, 'Firmware unavailable')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json' if manifest else 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path not in ('/ingest', prefix + '/ingest'):
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
                data = validate(json.loads(body), store.sensor)
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
    sensor = sensor_name(cfg.get('sensor', SENSOR))
    store = Store(database, sensor)
    output = Path(cfg['snapshot']).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    releases = None
    if cfg.get('firmware_root'):
        firmware_root = Path(cfg['firmware_root']).expanduser().resolve()
        if firmware_root == output.parent.resolve() or output.parent.resolve() in firmware_root.parents:
            raise ValueError('firmware_root must be outside the dashboard public directory')
        releases = FirmwareReleases(firmware_root, sensor)
    topic = cfg.get('mqtt_topic', TOPIC if sensor == SENSOR else 'sensors/' + sensor + '/temperature')
    ack_topic = cfg.get('mqtt_ack_topic', ACK_TOPIC if sensor == SENSOR else 'sensors/' + sensor + '/ack')
    mqtt_enabled = cfg.get('mqtt_enabled', bool(cfg.get('username')))
    state = {'broker_connected': False, 'mqtt_enabled': mqtt_enabled, 'last_error': None}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id='solar-roof-collector' if sensor == SENSOR else sensor + '-collector')
    if cfg.get('username'):
        client.username_pw_set(cfg['username'], cfg.get('password'))
    client.reconnect_delay_set(1, 10)

    def on_connect(c, userdata, flags, reason, properties):
        state['broker_connected'] = not reason.is_failure
        if not reason.is_failure:
            c.subscribe(topic, qos=1)
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
            data = validate(json.loads(msg.payload), sensor)
            inserted = store.add(data)
            c.publish(ack_topic, data['event_id'], qos=1, retain=False)
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
    publish = (lambda data: client.publish(topic, json.dumps(data), qos=1, retain=True)) if mqtt_enabled else None
    server = ThreadingHTTPServer(('127.0.0.1', cfg.get('http_port', 8790)), make_handler(
        store, cfg['ingest_token'], publish, releases, cfg.get('firmware_password', '')))
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
            if releases is not None:
                try:
                    snapshot['firmware_available'] = releases.manifest()
                except (OSError, ValueError, KeyError):
                    snapshot['firmware_available'] = None
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
