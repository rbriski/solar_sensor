import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import transport_watchdog as w


def observation(now=1000, age=10):
    return {'checked_at': now, 'local': {'ok': True},
            'dns': [{'ok': True}, {'ok': True}],
            'public': [{'ok': True, 'network_failure': False}],
            'tailscale': {'running': True, 'route_configured': True, 'health': []},
            'feed': {'generated_at': now, 'latest': {'received_at': now-age,
                     'sleep_seconds': 30, 'event_id': 'deadbeef-1'}}}


def outage(now=1000):
    o = observation(now, age=250)
    o['public'] = [{'ok': False, 'network_failure': True},
                   {'ok': False, 'network_failure': True}]
    return o


class ClassificationTest(unittest.TestCase):
    def test_incident_replay(self):
        previous = {}
        for now, expected in [(1000, False), (1060, False), (1120, True)]:
            previous = w.evaluate(outage(now), previous)
            self.assertEqual(previous['recovery_recommended'], expected)
            self.assertEqual(previous['status'], 'public_route_failed')
        recovered = w.evaluate(observation(1180), previous)
        self.assertEqual(recovered['status'], 'healthy')
        self.assertEqual(recovered['failure_checks'], 0)
        self.assertFalse(recovered['recovery_recommended'])

    def test_silence_alone_never_recommends_reconnect(self):
        state = w.evaluate(observation(age=400), {})
        self.assertEqual(state['status'], 'sensor_overdue')
        self.assertEqual(state['failure_checks'], 0)

    def test_fresh_reading_inhibits_recovery(self):
        o = outage()
        o['feed']['latest']['received_at'] = 990
        self.assertEqual(w.evaluate(o, {})['failure_checks'], 0)

    def test_all_evidence_required(self):
        for change in [
            lambda o: o['local'].update(ok=False),
            lambda o: o['feed'].update(generated_at=900),
            lambda o: o['dns'][0].update(ok=False),
            lambda o: o['tailscale'].update(running=False),
            lambda o: o['tailscale'].update(route_configured=False),
            lambda o: o['tailscale'].update(health=['no internet']),
            lambda o: o['public'][0].update(ok=True, network_failure=False),
            lambda o: o['public'][0].update(network_failure=False, curl_exit=60),
            lambda o: o.update(public=[]),
        ]:
            o = outage()
            change(o)
            with self.subTest(observation=o):
                self.assertFalse(w.evaluate(o, {'checked_at': 940, 'failure_checks': 9})['recovery_recommended'])

    def test_bad_collector_time_cannot_be_live(self):
        for generated in (900, 1001, float('nan'), float('inf'), None, True):
            o = observation()
            o['feed']['generated_at'] = generated
            self.assertEqual(w.evaluate(o, {})['status'], 'collector_unavailable')

    def test_bad_receipt_is_not_silence_evidence(self):
        for received in (1001, None, float('inf'), float('-inf')):
            o = outage()
            o['feed']['latest']['received_at'] = received
            state = w.evaluate(o, {})
            self.assertIsNone(state['sensor_age_seconds'])
            self.assertEqual(state['failure_checks'], 0)

    def test_clock_rollback_and_monitor_gap_reset_failure_count(self):
        state = w.evaluate(outage(), {'checked_at': 1100, 'failure_checks': 5})
        self.assertEqual(state['status'], 'clock_changed')
        self.assertEqual(state['failure_checks'], 0)
        self.assertEqual(w.evaluate(outage(), {'checked_at': 800, 'failure_checks': 5})['failure_checks'], 1)

    def test_deployment_sleep_cadence_respected(self):
        o = outage()
        o['feed']['latest']['sleep_seconds'] = 300
        self.assertEqual(w.evaluate(o, {})['failure_checks'], 0)
        o['feed']['latest']['received_at'] = 340
        self.assertEqual(w.evaluate(o, {})['failure_checks'], 1)


class ProbeTest(unittest.TestCase):
    @patch.object(w, 'curl')
    def test_dns_rejects_tailnet_private_and_empty_answers(self, curl):
        for address in ('100.77.235.69', '127.0.0.1', '192.168.7.1', '::1'):
            curl.return_value = subprocess.CompletedProcess([], 0, json.dumps({
                'Status': 0, 'Answer': [{'type': 1, 'data': address}]}), '')
            self.assertFalse(w.resolve_public(w.RESOLVERS[0])['ok'])
        curl.return_value.stdout = '{"Status": 0}'
        self.assertFalse(w.resolve_public(w.RESOLVERS[0])['ok'])

    @patch.object(w, 'curl')
    def test_probe_preserves_tls_hostname_without_credentials_or_fake_reading(self, curl):
        curl.return_value = subprocess.CompletedProcess([], 0, 'Unauthorized\n401', '')
        self.assertTrue(w.probe('208.111.34.11')['ok'])
        url, args = curl.call_args.args
        self.assertEqual(url, w.PUBLIC_URL)
        self.assertIn(w.HOST + ':10000:208.111.34.11', args)
        self.assertNotIn('--insecure', args)
        self.assertNotIn('Authorization', ' '.join(args))
        self.assertEqual(args[args.index('--data')+1], '{}')

    @patch.object(w, 'curl')
    def test_certificate_error_and_wrong_backend_do_not_trigger_reconnect(self, curl):
        for exit_code, body in [(60, '\n000'), (0, 'Unauthorized\n404'), (0, 'wrong backend\n401')]:
            curl.return_value = subprocess.CompletedProcess([], exit_code, body, 'failed')
            result = w.probe('208.111.34.11')
            self.assertFalse(result['ok'])
            self.assertFalse(result['network_failure'])
        curl.return_value = subprocess.CompletedProcess([], 35, '\n000', 'TLS connection closed')
        self.assertTrue(w.probe('208.111.34.11')['network_failure'])

    def test_atomic_evidence_write_preserves_observations(self):
        o = outage()
        original = copy.deepcopy(o)
        result = w.evaluate(o, {})
        self.assertEqual(o, original)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'state.json'
            w.atomic_json(target, result)
            self.assertEqual(w.load_json(target), result)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)


class RecoveryTest(unittest.TestCase):
    def candidate(self, now=10000):
        return dict(w.evaluate(outage(now), {}), recovery_recommended=True,
                    failure_checks=3, healthy_checks=0)

    def test_requires_opt_in_and_is_latched_across_repeated_checks(self):
        result = self.candidate()
        self.assertFalse(w.plan_recovery(result, {}, False))
        self.assertTrue(w.plan_recovery(result, {}, True))
        following = self.candidate(14000)
        self.assertFalse(w.plan_recovery(following, result, True))
        self.assertTrue(following['incident_recovery_attempted'])

    def test_requires_five_healthy_checks_and_cooldown_before_another_attempt(self):
        previous = self.candidate()
        w.plan_recovery(previous, {}, True)
        for count in range(1, 6):
            current = dict(w.evaluate(observation(10000+count*60), previous), healthy_checks=count)
            self.assertFalse(w.plan_recovery(current, previous, True))
            self.assertEqual(current['incident_recovery_attempted'], count < 5)
            previous = current
        self.assertFalse(w.plan_recovery(self.candidate(11000), previous, True))
        self.assertTrue(w.plan_recovery(self.candidate(14000), previous, True))

    def test_cleanup_does_not_turn_on_intentionally_stopped_tailscale(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'command') as run:
            w.ensure_up(Path(directory))
            run.assert_not_called()

    def test_killed_recovery_leaves_marker_for_systemd_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'command') as run:
            path = Path(directory)
            w.atomic_json(path / 'needs-up.json', {'started_at': 1})
            run.side_effect = [subprocess.CompletedProcess([], 0, '', ''),
                               subprocess.CompletedProcess([], 0, '{"BackendState":"Running"}', '')]
            w.ensure_up(path)
            self.assertEqual(run.call_args_list[0].args[0], ['tailscale', 'up'])
            self.assertFalse((path / 'needs-up.json').exists())

    def test_failed_up_preserves_cleanup_marker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'command') as run:
            path = Path(directory)
            w.atomic_json(path / 'needs-up.json', {})
            run.return_value = subprocess.CompletedProcess([], 1, '', 'failed')
            with self.assertRaises(subprocess.CalledProcessError):
                w.ensure_up(path)
            self.assertTrue((path / 'needs-up.json').exists())

    @patch.dict(w.os.environ, {'SOLAR_FUNNEL_AUTO_RECOVERY': '1'})
    @patch.object(w.time, 'time', return_value=10000)
    def test_conditions_are_rechecked_before_reconnect(self, clock):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'observe') as observe, patch.object(w, 'command') as run:
            path = Path(directory)
            state = self.candidate()
            w.plan_recovery(state, {}, True)
            w.atomic_json(path / 'state.json', state)
            observe.return_value = observation(10001)
            w.recover(path)
            run.assert_not_called()
            self.assertEqual(w.load_json(path / 'state.json')['recovery_action'], 'skipped_conditions_changed')

    @patch.dict(w.os.environ, {'SOLAR_FUNNEL_AUTO_RECOVERY': '1'})
    @patch.object(w.time, 'time', return_value=10000)
    def test_up_is_attempted_even_when_down_times_out(self, clock):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'observe') as observe, patch.object(w, 'command') as run:
            path = Path(directory)
            state = self.candidate()
            w.plan_recovery(state, {}, True)
            w.atomic_json(path / 'state.json', state)
            observe.return_value = outage(10001)
            called = []
            def response(args, timeout=10):
                called.append(args)
                if args == ['tailscale', 'down']:
                    raise subprocess.TimeoutExpired(args, 10)
                payload = {'WantRunning': True} if args[-1] == 'prefs' else {'BackendState': 'Running'}
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), '')
            run.side_effect = response
            with self.assertRaises(subprocess.TimeoutExpired):
                w.recover(path)
            self.assertIn(['tailscale', 'up'], called)
            self.assertFalse((path / 'needs-up.json').exists())
            self.assertEqual(w.load_json(path / 'state.json')['recovery_action'], 'failed')


class EvidenceTest(unittest.TestCase):
    @patch.object(w, 'command')
    def test_private_evidence_excludes_ssh_commands_and_does_not_change_public_status(self, run):
        entries = [{'MESSAGE': 'Received error: PollNetMap: connection closed'},
                   {'MESSAGE': 'ssh-session: command includes control: netmap: private argument'},
                   {'MESSAGE': 'control: netmap: got new dial plan'}]
        run.return_value = subprocess.CompletedProcess([], 0, '\n'.join(map(json.dumps, entries)), '')
        result = w.evaluate(outage(), {})
        evidence = w.incident_evidence(result)
        self.assertEqual(len(evidence['tailscale_recent_messages']), 2)
        self.assertNotIn('tailscale_recent_messages', result)


if __name__ == '__main__':
    unittest.main()
