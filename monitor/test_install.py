import json
from pathlib import Path
import tempfile
import unittest

from install import install


class InstallTest(unittest.TestCase):
    def test_fresh_install_is_private_and_reinstall_keeps_settings(self):
        with tempfile.TemporaryDirectory(prefix='solar install ') as tmp:
            home = Path(tmp) / 'user $name%'
            python = home / '.venv/bin/python'
            path, created = install(home, 'https://example.ts.net:10000/solar-roof/ingest', python)
            self.assertTrue(created)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            config = json.loads(path.read_text())
            self.assertGreater(len(config['ingest_token']), 30)
            self.assertFalse(config['mqtt_enabled'])
            self.assertNotIn('password', config)
            # User changes must survive updates, including a non-default feed name.
            config['snapshot'] = str(home / 'custom/feed.json')
            path.write_text(json.dumps(config))
            env = path.with_name('transport-watchdog.env')
            old_env = env.read_text().replace('AUTO_RECOVERY=0', 'AUTO_RECOVERY=1')
            env.write_text(old_env)
            _, created = install(home, 'https://different.ts.net:10000/solar-roof/ingest', python)
            self.assertFalse(created)
            self.assertEqual(json.loads(path.read_text()), config)
            self.assertEqual(env.read_text(), old_env)
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)
            self.assertTrue((home / 'custom/index.html').is_file())
            self.assertIn('"feed.json?t="', (home / 'custom/index.html').read_text())
            unit = (home / '.config/systemd/user/solar-sensor-collector.service').read_text()
            self.assertIn('$$name%%', unit)
            self.assertNotIn('@PYTHON@', unit)
            watchdog = (home / '.config/systemd/user/solar-sensor-transport.service').read_text()
            env_line = next(line for line in watchdog.splitlines() if line.startswith('EnvironmentFile='))
            self.assertIn('$name%%', env_line)
            self.assertNotIn('$$name', env_line)
            self.assertTrue(env_line.startswith('EnvironmentFile=/'))

    def test_env_path_retains_literal_special_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'user $name%'
            path, _ = install(home, 'https://example.ts.net:10000/solar-roof/ingest', Path('/usr/bin/python3'))
            env = path.with_name('transport-watchdog.env').read_text()
            self.assertIn(str(home), env)
            self.assertNotIn('$$', env)
            self.assertNotIn('%%', env)

    def test_bad_public_url_does_not_create_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for url in ('http://x/solar-roof/ingest', 'https://x:9000/solar-roof/ingest',
                        'https://x/wrong', 'https://u:p@x/solar-roof/ingest',
                        'https://x/solar-roof/ingest\nINJECT=1'):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    install(home, url, Path('/usr/bin/python3'))
            self.assertFalse((home / '.config').exists())


if __name__ == '__main__': unittest.main()
