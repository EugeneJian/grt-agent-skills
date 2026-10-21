"""Per-computer initialization must preserve sessions and unrelated profiles."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import setup_cloud


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name)/'profiles.json'
        self.session = Path(self.temp.name)/'cloud-auth.json'
        self.url = 'https://example.supabase.co'

    def initialize(self, **kwargs):
        return setup_cloud.initialize(self.config, self.url, session_path=self.session, **kwargs)

    def test_new_host_has_only_public_seed_and_cloud_default(self):
        self.initialize(key='sb_publishable_test')
        self.assertEqual(json.loads(self.session.read_text()),
                         {'project_url': self.url, 'apikey': 'sb_publishable_test'})
        self.assertEqual(json.loads(self.config.read_text())['default_profile'], 'cloud')
        if os.name != 'nt':
            self.assertEqual(self.session.stat().st_mode & 0o777, 0o600)

    def test_repeat_install_preserves_device_session_and_local_profile(self):
        self.initialize(key='sb_publishable_test')
        session = json.loads(self.session.read_text())
        session.update(access_token='fake-device-access', refresh_token='fake-device-refresh')
        self.session.write_text(json.dumps(session))
        before = self.session.read_bytes()
        config = json.loads(self.config.read_text())
        config['profiles']['local'] = {'engine': 'postgres', 'service': 'validation'}
        self.config.write_text(json.dumps(config))
        self.initialize(key='sb_publishable_replacement')
        self.assertEqual(self.session.read_bytes(), before)
        self.assertEqual(json.loads(self.config.read_text())['profiles']['local'],
                         {'engine': 'postgres', 'service': 'validation'})

    def test_wrong_project_does_not_modify_files(self):
        self.initialize(key='sb_publishable_test')
        before = [self.config.read_bytes(), self.session.read_bytes()]
        with self.assertRaises(ValueError):
            setup_cloud.initialize(self.config, 'https://different.supabase.co',
                                   key='sb_publishable_test', session_path=self.session)
        self.assertEqual(before, [self.config.read_bytes(), self.session.read_bytes()])

    def test_secret_key_and_employee_jwt_rejected_before_writes(self):
        for key in ('sb_secret_test', 'not-a-public-key', 'test.eyJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.signature'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.initialize(key=key)
            self.assertFalse(self.config.exists())
            self.assertFalse(self.session.exists())

    def test_invalid_origin_does_not_write(self):
        for url in ('http://example.supabase.co', self.url+'/auth/v1', 'https://name:password@example.org'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                setup_cloud.initialize(self.config, url, key='sb_publishable_test', session_path=self.session)
            self.assertFalse(self.config.exists())

    def test_different_session_path_is_not_overwritten(self):
        self.initialize(key='sb_publishable_test')
        other = self.session.with_name('other.json')
        with self.assertRaises(ValueError):
            setup_cloud.initialize(self.config, self.url, key='sb_publishable_test', session_path=other)
        self.assertFalse(other.exists())


if __name__ == '__main__':
    unittest.main()

class PreserveDefault(unittest.TestCase):
    def test_existing_intranet_default_survives_optional_cloud_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'profiles.json';session=root/'session.json'
            config.write_text(json.dumps({'default_profile':'intranet','profiles':{'intranet':{'engine':'mssql_rd_delivery'}}}))
            result=setup_cloud.initialize(config,'https://test.supabase.co',key='sb_publishable_test',session_path=session)
            self.assertEqual(result['default_profile'],'intranet')
            self.assertEqual(json.loads(config.read_text())['default_profile'],'intranet')
