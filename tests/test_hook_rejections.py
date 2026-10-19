"""Early hook failures remain silent and retain counters, never payloads."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hook_bridge import receive
from journal import Journal, MAX_INPUT
from analytics import report


class HookRejectionTests(unittest.TestCase):
    def test_early_rejections_count_once_without_payloads(self):
        sentinel = b'PRIVATE_HOOK_INPUT_CANARY'
        inputs = [b'{'+sentinel, b'"'+sentinel+b'\xff"',
                  sentinel+b'x'*(MAX_INPUT+1), b'[]', b'{}']
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'state'
            for index, body in enumerate(inputs, 1):
                with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertFalse(receive('codex', state, io.BytesIO(body)))
                self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))
                j = Journal(state)
                try:
                    self.assertEqual(j.db.execute("SELECT rejected FROM health WHERE provider='codex'").fetchone()[0], index)
                    self.assertEqual(j.db.execute('SELECT count(*) FROM observation').fetchone()[0], 0)
                finally:
                    j.close()
            self.assertFalse(any(sentinel in f.read_bytes() for f in state.rglob('*') if f.is_file()))

    def test_rejected_only_client_visible_without_invented_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(receive('codex', tmp, io.BytesIO(b'bad')))
            j = Journal(tmp)
            try:
                coverage = report(j)['coverage']
                self.assertEqual(len(coverage), 1)
                self.assertEqual((coverage[0]['provider'], coverage[0]['rejected'], coverage[0]['calls']), ('codex', 1, 0))
                self.assertEqual(coverage[0]['state'], 'not-observed')
                self.assertIsNone(coverage[0]['lastEventAt'])
                self.assertEqual(report(j, ['glm'])['coverage'][0]['rejected'], 0)
                self.assertEqual(report(j, [])['coverage'], [])
            finally:
                j.close()

    def test_bounded_read_and_input_io_failure(self):
        class BrokenStream:
            def read(self, size):
                self.size = size
                raise OSError('private stream failure')
        stream = BrokenStream()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(receive('glm', tmp, stream))
            self.assertEqual(stream.size, MAX_INPUT+1)
            j = Journal(tmp)
            try:
                self.assertEqual(j.db.execute("SELECT rejected FROM health WHERE provider='glm'").fetchone()[0], 1)
            finally:
                j.close()

    def test_storage_unavailable_does_not_retry_or_escape(self):
        with patch('hook_bridge.Journal', side_effect=OSError('private storage')) as factory:
            self.assertFalse(receive('codex', Path('/unused'), io.BytesIO(b'bad')))
            factory.assert_called_once()

    def test_counter_and_close_failure_stay_fail_open(self):
        with patch('hook_bridge.Journal') as factory:
            factory.return_value.reject.side_effect = OSError('counter')
            factory.return_value.close.side_effect = OSError('close')
            self.assertFalse(receive('codex', Path('/unused'), io.BytesIO(b'bad')))

    def test_valid_pair_after_rejection_preserves_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(receive('codex', tmp, io.BytesIO(b'bad')))
            for event in ('PreToolUse', 'PostToolUse'):
                raw = {'session_id':'fixture', 'tool_use_id':'one', 'tool_name':'Bash',
                       'hook_event_name':event, 'tool_input':{'command':'true'}, 'tool_response':{'exit_code':7}}
                self.assertTrue(receive('codex', tmp, io.BytesIO(json.dumps(raw).encode())))
            j = Journal(tmp)
            try:
                call = j.calls()[0]
                self.assertTrue(call['paired'])
                self.assertEqual((call['outcome'], call['exitCode']), ('failed', 7))
                self.assertEqual(j.db.execute("SELECT rejected FROM health WHERE provider='codex'").fetchone()[0], 1)
            finally:
                j.close()

    def test_cli_and_compatibility_share_early_rejection_counters(self):
        for entry in ('collector.py', 'scripts/hook_bridge.py'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as tmp:
                for body in (b'bad', b'x'*(MAX_INPUT+1), b'\xff'):
                    args = [sys.executable, entry, '--state', tmp]
                    if entry == 'collector.py':
                        args.append('hook')
                    args += ['--provider', 'codex']
                    result = subprocess.run(args, input=body, capture_output=True, timeout=5)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                j = Journal(tmp)
                try:
                    self.assertEqual(j.db.execute("SELECT rejected FROM health WHERE provider='codex'").fetchone()[0], 3)
                    self.assertEqual(j.db.execute('SELECT count(*) FROM observation').fetchone()[0], 0)
                finally:
                    j.close()
