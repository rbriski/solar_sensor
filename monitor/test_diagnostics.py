import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from collector import Store, validate
from test_collector import sample

ROOT = Path(__file__).resolve().parent


class DiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'diagnostics'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'diagnostics_test.cpp'), '-o', str(exe)], check=True)
            cls.diag = json.loads(subprocess.check_output([str(exe)], text=True))

    def test_roundtrip_and_duplicate_does_not_change_history(self):
        reading = dict(sample(), diagnostics=self.diag)
        validate(reading)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'readings.db'
            store = Store(path)
            self.assertTrue(store.add(reading, now=10))
            changed = copy.deepcopy(reading)
            changed['diagnostics']['history'] = []
            self.assertFalse(store.add(changed, now=20))
            store.db.close()
            store = Store(path)
            self.assertEqual(store.snapshot()['latest']['diagnostics'], self.diag)
            self.assertEqual(store.snapshot()['latest']['received_at'], 10)
            store.db.close()
        self.assertLess(len(json.dumps(reading)), 2048)

    def test_nvs_checkpoint_throttling_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'nvs'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'test_support'),
                            str(ROOT / 'diagnostics_nvs_test.cpp'), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_malformed_diagnostics(self):
        for patch in ({'version': True}, {'probe': 99}, {'probe': 1}, {'streak': -1},
                      {'storage_ok': 1}, {'history': [[20, 0]]}, {'history': [[20, 0, 1, 0, True]]},
                      {'history': [[99, 0, 1, 0, 0]]}, {'history': [[20, 0, 1, 0, 1]] * 5},
                      {'http': 600}, {'uptime': 2**32}, {'delivery': []}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(dict(sample(), diagnostics=dict(self.diag, **patch)))
        for d in (None, [], 'bad'):
            with self.assertRaises(ValueError): validate(dict(sample(), diagnostics=d))

    def test_old_firmware_and_probe_failure(self):
        validate(sample())
        validate(dict(sample(), temp_ok=False, temperature_c=None, temperature_f=None,
                      diagnostics=dict(self.diag, probe=4)))
