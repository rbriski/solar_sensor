#!/usr/bin/env python3
"""Check the sensor's public delivery path without submitting sensor readings."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.parse


PUBLIC_URL = os.environ.get('SOLAR_PUBLIC_URL', 'https://receiver.example.ts.net:10000/solar-roof/ingest')
_PUBLIC = urllib.parse.urlsplit(PUBLIC_URL)
HOST = _PUBLIC.hostname
PORT = _PUBLIC.port or 443
LOCAL_URL = os.environ.get('SOLAR_LOCAL_URL', 'http://127.0.0.1:8790/ingest')
ROUTE_PATH = os.environ.get('SOLAR_FUNNEL_PATH', '/solar-roof')
LOCAL_PROXY = LOCAL_URL.removesuffix('/ingest')
SNAPSHOT = Path(os.environ.get('SOLAR_SNAPSHOT', str(Path.home()/'.local/share/solar-sensor/public/latest.json'))).expanduser()
PUBLIC_STATUS = SNAPSHOT.with_name('transport-health.json')
STATE_DIR = Path.home() / '.local/share/solar-sensor/transport'
RESOLVERS = ('https://dns.google/resolve', 'https://cloudflare-dns.com/dns-query')
NETWORK_ERRORS = {5, 6, 7, 28, 35, 52, 55, 56}


def command(args, timeout=10):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def curl(url, extra=()):
    return command([
        'curl', '--silent', '--show-error', '--noproxy', '*',
        '--connect-timeout', '3', '--max-time', '7',
        '--max-filesize', '65536', *extra, url,
    ])


def resolve_public(resolver):
    """Use public DNS, not MagicDNS's working-but-irrelevant 100.x address."""
    try:
        url = resolver + '?' + urllib.parse.urlencode({'name': HOST, 'type': 'A'})
        result = curl(url, ('--fail', '--header', 'Accept: application/dns-json'))
        if result.returncode:
            raise ValueError(f'DNS HTTPS request failed (curl {result.returncode})')
        reply = json.loads(result.stdout)
        if reply.get('Status') != 0:
            raise ValueError('DNS lookup did not succeed')
        addresses = sorted({a['data'] for a in reply.get('Answer', []) if a.get('type') == 1})
        if not addresses or len(addresses) > 4:
            raise ValueError('Missing or excessive public DNS addresses')
        if any(not ipaddress.IPv4Address(ip).is_global for ip in addresses):
            raise ValueError('DNS returned a non-public address')
        return {'resolver': resolver, 'ok': True, 'addresses': addresses}
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        return {'resolver': resolver, 'ok': False, 'addresses': [], 'error': str(exc)}


def probe(ip=None):
    """An unauthenticated POST must get the collector's 401, with valid TLS."""
    extra = ['--request', 'POST', '--header', 'Content-Type: application/json',
             '--data', '{}', '--write-out', '\n%{http_code}']
    if ip:
        extra += ['--resolve', f'{HOST}:{PORT}:{ip}']
    try:
        r = curl(PUBLIC_URL if ip else LOCAL_URL, extra)
        body, _, status = r.stdout.rpartition('\n')
        code = int(status) if status.isdigit() else 0
        return {'ip': ip, 'ok': r.returncode == 0 and code == 401 and body == 'Unauthorized',
                'http_status': code, 'curl_exit': r.returncode,
                'network_failure': r.returncode in NETWORK_ERRORS and code == 0,
                'error': r.stderr.strip()[:350]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {'ip': ip, 'ok': False, 'network_failure': False, 'error': str(exc)}


def load_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def tailscale_status():
    try:
        r = command(['tailscale', 'status', '--json'])
        if r.returncode:
            return {'running': False, 'error': 'Tailscale status unavailable'}
        d = json.loads(r.stdout)
        cfg = json.loads(command(['tailscale', 'serve', 'status', '--json']).stdout)
        hostport = f'{HOST}:{PORT}'
        handler = cfg.get('Web', {}).get(hostport, {}).get('Handlers', {}).get(ROUTE_PATH, {})
        return {'running': d.get('BackendState') == 'Running',
                'health': d.get('Health') or [],
                'route_configured': cfg.get('AllowFunnel', {}).get(hostport) is True
                and handler.get('Proxy') == LOCAL_PROXY}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'running': False, 'error': 'Tailscale status unavailable'}


def observe():
    with ThreadPoolExecutor(max_workers=8) as pool:
        local_future = pool.submit(probe)
        ts_future = pool.submit(tailscale_status)
        dns = list(pool.map(resolve_public, RESOLVERS))
        addresses = sorted({ip for d in dns for ip in d['addresses']})
        public = list(pool.map(probe, addresses))
        local, ts = local_future.result(), ts_future.result()
    return {'checked_at': time.time(), 'local': local, 'dns': dns, 'public': public,
            'tailscale': ts, 'feed': load_json(SNAPSHOT)}


def evaluate(observation, previous):
    now = observation['checked_at']
    feed = observation['feed']
    latest = feed.get('latest') or {}
    generated = feed.get('generated_at')
    received = latest.get('received_at')
    interval = latest.get('sleep_seconds', 30)
    valid_time = lambda t: type(t) in (int, float) and math.isfinite(t) and 0 <= now - t
    feed_live = valid_time(generated) and now - generated <= 20
    age = now - received if valid_time(received) else None
    interval = interval if type(interval) is int and 1 <= interval <= 3600 else 30
    overdue_after = max(180, interval * 2 + 60)
    overdue = age is not None and age >= overdue_after
    public = observation['public']
    dns_ok = len(observation['dns']) == 2 and all(d['ok'] for d in observation['dns'])
    local_ok = observation['local']['ok'] and feed_live
    public_ok = bool(public) and all(p['ok'] for p in public)
    ts = observation['tailscale']
    config_ok = ts.get('running') and ts.get('route_configured') and not ts.get('health')
    clock_ok = now >= previous.get('checked_at', 0)
    failed_path = bool(public) and all(p.get('network_failure') for p in public)
    eligible = bool(clock_ok and local_ok and dns_ok and config_ok and overdue and failed_path)
    continuous = 0 < now - previous.get('checked_at', 0) <= 150
    failures = previous.get('failure_checks', 0) + 1 if eligible and continuous else int(eligible)
    healthy = local_ok and dns_ok and public_ok and age is not None and not overdue
    healthy_checks = previous.get('healthy_checks', 0) + 1 if healthy and continuous else int(healthy)
    if not clock_ok:
        status, message = 'clock_changed', 'Receiver clock moved backwards; recovery is inhibited.'
    elif not local_ok:
        status, message = 'collector_unavailable', 'The collector or its status feed is not responding.'
    elif not dns_ok:
        status, message = 'dns_unavailable', 'Public DNS checks are incomplete; the route cannot be confirmed.'
    elif not public_ok:
        status = 'public_route_degraded' if any(p['ok'] for p in public) else 'public_route_failed'
        message = 'The public HTTPS delivery route is failing. The collector is responding locally.'
    elif age is None:
        status, message = 'waiting', 'Public delivery route is healthy; waiting for a sensor reading.'
    elif overdue:
        status, message = 'sensor_overdue', 'Public delivery route is healthy, but the sensor has not reported recently.'
    else:
        status, message = 'healthy', 'Public delivery route and recent sensor delivery are healthy.'
    return {'schema_version': 1, 'checked_at': now, 'status': status, 'message': message,
            'sensor_age_seconds': age, 'overdue_after_seconds': overdue_after,
            'last_event_id': latest.get('event_id'), 'local': observation['local'],
            'dns': observation['dns'], 'public': public, 'tailscale': ts,
            'failure_checks': failures, 'healthy_checks': healthy_checks,
            'recovery_recommended': failures >= 3,
            'recovery_mode': 'monitor_only',
            'last_healthy_at': now if healthy else previous.get('last_healthy_at')}


def atomic_json(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), mode)
            json.dump(data, f, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def plan_recovery(result, previous, enabled):
    """Persist one attempt per incident, with an additional one-hour cooldown."""
    for key in ('incident_recovery_attempted', 'last_recovery_at', 'recovery_action', 'recovery_error'):
        if key in previous:
            result[key] = previous[key]
    if result['healthy_checks'] >= 5:
        result.update(incident_recovery_attempted=False, recovery_action=None, recovery_error=None)
    result['recovery_mode'] = 'automatic' if enabled else 'monitor_only'
    cooled_down = result['checked_at'] - previous.get('last_recovery_at', -3600) >= 3600
    attempt = bool(enabled and result['recovery_recommended'] and cooled_down
                   and not result.get('incident_recovery_attempted', False))
    if attempt:
        result.update(incident_recovery_attempted=True, last_recovery_at=result['checked_at'],
                      recovery_action='queued', recovery_error=None)
    return attempt


def ensure_up(state_dir):
    """Called in finally AND systemd ExecStopPost, including after process kill."""
    pending = state_dir / 'needs-up.json'
    if pending.exists():
        command(['tailscale', 'up'], timeout=20).check_returncode()
        status = json.loads(command(['tailscale', 'status', '--json']).stdout)
        if status.get('BackendState') != 'Running':
            raise RuntimeError('Tailscale has not returned to Running')
        pending.unlink()


def incident_evidence(result):
    """Keep relevant daemon messages privately, excluding SSH command logs."""
    evidence = dict(result)
    prefixes = ('Received error: PollNetMap:', 'control: netmap:', 'control: controlhttp:',
                'Hostinfo.IngressEnabled', 'Hostinfo.WireIngress', 'peerapi: ingress:',
                'health(', 'http: proxy error:', 'http: TLS handshake error')
    try:
        r = command(['journalctl', '-u', 'tailscaled', '--since', '5 minutes ago',
                     '--no-pager', '-n', '200', '--output=json'], timeout=8)
        messages = []
        for line in r.stdout.splitlines():
            entry = json.loads(line)
            message = entry.get('MESSAGE', '')
            if isinstance(message, str) and message.startswith(prefixes):
                messages.append({'timestamp_us': entry.get('__REALTIME_TIMESTAMP'), 'message': message})
        evidence['tailscale_recent_messages'] = messages
        evidence['journal_available'] = r.returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        evidence['journal_available'] = False
    return evidence


def recover(state_dir):
    state_path = state_dir / 'state.json'
    previous = load_json(state_path)
    age = time.time() - previous.get('last_recovery_at', 0)
    if (os.environ.get('SOLAR_FUNNEL_AUTO_RECOVERY') != '1' or
            previous.get('recovery_action') != 'queued' or not 0 <= age <= 120):
        return
    # Recheck live evidence before interrupting any connection.
    current = evaluate(observe(), previous)
    if not current['recovery_recommended']:
        previous['recovery_action'] = 'skipped_conditions_changed'
        atomic_json(state_path, previous)
        return
    prefs = json.loads(command(['tailscale', 'debug', 'prefs']).stdout)
    routes = json.loads(command(['tailscale', 'serve', 'status', '--json']).stdout)
    if not prefs.get('WantRunning') or prefs.get('ShieldsUp'):
        return
    atomic_json(state_dir / 'needs-up.json', {'started_at': time.time()})
    try:
        try:
            command(['tailscale', 'down'], timeout=10).check_returncode()
        finally:
            ensure_up(state_dir)
        if prefs != json.loads(command(['tailscale', 'debug', 'prefs']).stdout):
            raise RuntimeError('Tailscale preferences changed during recovery; review required')
        if routes != json.loads(command(['tailscale', 'serve', 'status', '--json']).stdout):
            raise RuntimeError('Tailscale routes changed during recovery; review required')
        previous['recovery_action'] = 'reconnected_awaiting_sensor'
        previous['recovery_error'] = None
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        previous['recovery_action'] = 'failed'
        previous['recovery_error'] = str(exc)[:350]
        raise
    finally:
        atomic_json(state_path, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=STATE_DIR)
    parser.add_argument('--output', type=Path, default=PUBLIC_STATUS)
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--ensure-up', action='store_true')
    args = parser.parse_args()
    if not args.ensure_up and (not HOST or _PUBLIC.scheme != 'https' or 'example.ts.net' in HOST):
        parser.error('Set SOLAR_PUBLIC_URL to this receiver\'s HTTPS ingestion URL')
    args.state_dir.mkdir(parents=True, exist_ok=True)
    # Cleanup must not lose a race with the next monitor invocation's lock.
    if args.ensure_up:
        ensure_up(args.state_dir)
        return
    with (args.state_dir / 'lock').open('a') as lock:
        # The queued recovery may start before its caller has released the lock.
        fcntl.flock(lock, fcntl.LOCK_EX | (0 if args.recover else fcntl.LOCK_NB))
        if args.recover:
            recover(args.state_dir)
            return
        previous = load_json(args.state_dir / 'state.json')
        result = evaluate(observe(), previous)
        attempt = plan_recovery(result, previous, os.environ.get('SOLAR_FUNNEL_AUTO_RECOVERY') == '1')
        changed = (result['status'], result['recovery_recommended']) != (
            previous.get('status'), previous.get('recovery_recommended'))
        atomic_json(args.state_dir / 'state.json', result)
        atomic_json(args.output, result, 0o644)
        if attempt:
            # Durable latch is written BEFORE queueing the interrupting action.
            # A separate unit guarantees ExecStopPost even if recovery is killed.
            try:
                command(['systemctl', '--user', 'start', '--no-block',
                         'solar-sensor-transport-recover.service']).check_returncode()
            except (OSError, subprocess.SubprocessError) as exc:
                result.update(recovery_action='queue_failed', recovery_error=str(exc)[:350])
                atomic_json(args.state_dir / 'state.json', result)
                atomic_json(args.output, result, 0o644)
        if changed:
            # Separate evidence for diagnosis; never add invented sensor samples.
            stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(result['checked_at']))
            atomic_json(args.state_dir / 'events' / (stamp + '.json'), incident_evidence(result))
        print(json.dumps({k: result[k] for k in ('checked_at', 'status', 'failure_checks',
                                               'recovery_recommended', 'last_event_id')}), flush=True)


if __name__ == '__main__':
    main()
