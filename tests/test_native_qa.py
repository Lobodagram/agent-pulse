import json
from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.native_qa import artifacts, input_identity, reuse, run


class NativeQATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = self.root/'AgentPulseFixture.app'
        self.binary = self.bundle/'Contents/MacOS/AgentPulse'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'demo-binary')
        (self.bundle/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'app.agentpulse.demo'}))
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def fixture_runner(self, command, **kwargs):
        self.calls.append(command)
        dest = Path(command[-1])
        (dest/'demo.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'x'*120)
        (dest/'demo.png.json').write_text(json.dumps({'fixtureMode': True}))
        return SimpleNamespace(returncode=0, stdout='synthetic', stderr='')

    def test_verified_cache_reuse_and_missing_receipt_invalidation(self):
        with patch('scripts.native_qa.sys.platform', 'darwin'):
            first = run(self.binary, self.root/'one', ['models'], runner=self.fixture_runner)
            second = run(self.binary, self.root/'two', ['models'], self.root/'one/receipt.json', runner=self.fixture_runner)
            self.assertEqual(len(self.calls), 1)
            self.assertTrue(second['suites'][0]['reused'])
            self.assertEqual(first['status'], 'passed')
            (self.root/'one/models/demo.png.json').unlink()
            third = run(self.binary, self.root/'three', ['models'], self.root/'one/receipt.json', runner=self.fixture_runner)
            self.assertFalse(third['suites'][0]['reused'])
            self.assertEqual(len(self.calls), 2)

    def test_bundle_environment_fixture_artifact_or_suite_changes_invalidate(self):
        with patch('scripts.native_qa.sys.platform', 'darwin'):
            first = run(self.binary, self.root/'one', ['models'], runner=self.fixture_runner)
        identity = first['inputs']
        for key in ['bundleSha256', 'fixtureSha256', 'python', 'platform', 'runnerSha256']:
            altered = dict(identity, **{key: 'changed'})
            self.assertIsNone(reuse(first, 'models', altered, self.root/'one'))
        altered = dict(identity, suiteScripts=dict(identity['suiteScripts'], models='changed'))
        self.assertIsNone(reuse(first, 'models', altered, self.root/'one'))
        (self.root/'one/models/demo.png').write_bytes(b'changed')
        self.assertIsNone(reuse(first, 'models', identity, self.root/'one'))

    def test_failure_not_cached_and_remaining_suites_continue(self):
        def failed(command, **kwargs):
            if 'model_ui_smoke.py' in command[1]:
                return SimpleNamespace(returncode=1, stdout='', stderr='synthetic failure')
            return self.fixture_runner(command, **kwargs)
        with patch('scripts.native_qa.sys.platform', 'darwin'):
            first = run(self.binary, self.root/'one', ['models', 'charts'], runner=failed)
        self.assertEqual([r['status'] for r in first['suites']], ['failed', 'passed'])
        self.assertEqual(first['status'], 'failed')
        self.assertIsNone(reuse(first, 'models', first['inputs'], self.root/'one'))

    def test_changed_input_during_run_invalidates_passed_receipt(self):
        def changing(command, **kwargs):
            self.binary.write_bytes(b'changed-in-run')
            return self.fixture_runner(command, **kwargs)
        with patch('scripts.native_qa.sys.platform', 'darwin'):
            result = run(self.binary, self.root/'one', ['models'], runner=changing)
        self.assertFalse(result['inputStable'])
        self.assertEqual(result['suites'][0]['status'], 'invalidated')

    def test_external_bundle_links_live_artifacts_and_old_output_rejected(self):
        external = self.root/'external'
        external.write_bytes(b'private')
        (self.bundle/'Contents/link').symlink_to(external)
        with self.assertRaises(ValueError):
            input_identity(self.binary)
        (self.bundle/'Contents/link').unlink()
        dest = self.root/'artifacts';dest.mkdir()
        (dest/'demo.png').write_bytes(b'x'*128)
        (dest/'demo.png.json').write_text(json.dumps({'fixtureMode': False}))
        with self.assertRaises(ValueError):
            artifacts(dest)
        with patch('scripts.native_qa.sys.platform', 'darwin'), self.assertRaises(ValueError):
            run(self.binary, dest, ['models'], runner=self.fixture_runner)

    def test_unsafe_cached_path_and_unselected_suite_rejected(self):
        with patch('scripts.native_qa.sys.platform', 'darwin'):
            result = run(self.binary, self.root/'one', ['models'], runner=self.fixture_runner)
        result['suites'][0]['artifacts'][0]['path'] = '../external.png'
        self.assertIsNone(reuse(result, 'models', result['inputs'], self.root/'one'))
        with patch('scripts.native_qa.sys.platform', 'darwin'), self.assertRaises(ValueError):
            run(self.binary, self.root/'two', ['unknown'], runner=self.fixture_runner)
