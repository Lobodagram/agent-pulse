import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from command_profile import profile, RECOGNITION_REASONS
from diagnostics import diagnostic_report
from journal import Journal
from pulse_version import __version__


class RecognitionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self.tmp.name)/'state')

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def event(self, phase, command='git status', call='one', tool='Bash'):
        raw = {'session_id': 'demo', 'turn_id': call, 'tool_use_id': call,
               'tool_name': tool, 'tool_input': {'command': command},
               'collectorVersion': 'PRIVATE_CLIENT_SUPPLIED_VERSION',
               'timestamp': time.time()-10, 'hook_event_name': phase}
        if phase != 'PreToolUse':
            raw['timestamp'] += 1
            raw['tool_response'] = {'exit_code': 0}
        self.j.record('glm', raw)

    def pair(self, command, call='one', tool='Bash'):
        self.event('PreToolUse', command, call, tool)
        self.event('PostToolUse', command, call, tool)

    def test_reasons_are_fixed_and_unknown_commands_remain_unknown(self):
        cases = [(None, 'missing-command'), ('', 'missing-command'), ('python3 '+'x'*32769, 'command-size-limit'),
                 ('python3 - <<PY\nPRIVATE_BODY', 'unsupported-heredoc'),
                 ('cat $(PRIVATE_CODE)', 'shell-substitution'), ('git status\n'*66, 'line-count-limit'),
                 ('git status >', 'unsupported-redirection'), ('cat "PRIVATE', 'incomplete-quoting'),
                 ('git status & PRIVATE_TOOL', 'chain-parse-or-limit'), ('PRIVATE_TOOL PRIVATE_PATH', 'unrecognized-invocation'),
                 ('git status ; PRIVATE_TOOL PRIVATE_CODE', 'partial-chain')]
        for command, expected in cases:
            with self.subTest(expected=expected):
                result = profile(command)
                self.assertEqual(result['recognitionReason'], expected)
                self.assertIn(result['recognitionReason'], RECOGNITION_REASONS)
                self.assertNotIn('PRIVATE', json.dumps(result))

    def test_terminal_heredoc_does_not_classify_opaque_body(self):
        result = profile("python3 - <<'PY'\nPRIVATE_CODE=$(PRIVATE)\nPY\n")
        self.assertEqual(result['recognitionReason'], 'classified')
        self.assertEqual(result['operations'][0]['family'], 'python-stdin')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_future_calls_report_actual_collector_version_not_native_model_version(self):
        self.pair('cat $(PRIVATE_CODE)')
        call = self.j.calls()[0]
        self.assertEqual(call['recognitionReason'], 'shell-substitution')
        self.assertEqual(call['collectorVersion'], __version__)
        self.assertEqual(call['collectorVersionCoverage'], 'complete')
        self.assertEqual(call['model'], 'other')
        self.assertEqual(call['operation'], 'unknown')
        diag = diagnostic_report(self.j)
        self.assertEqual(diag['commandCoverage'][0]['unknownReasons'], {'shell-substitution': 1})
        self.assertEqual(diag['collectorVersions'][0]['versions'], {__version__: 1})
        for table in ['observation','call_metadata','collection_metadata']:
            self.assertNotIn('PRIVATE', str([tuple(r) for r in self.j.db.execute('SELECT * FROM '+table)]))

    def test_legacy_rows_and_retries_are_never_backfilled(self):
        self.pair('PRIVATE_TOOL PRIVATE_CODE')
        self.j.db.execute('DELETE FROM collection_metadata');self.j.db.commit()
        self.pair('PRIVATE_TOOL PRIVATE_CODE')  # Identical delivery retry, not a new operation.
        call = self.j.calls()[0]
        self.assertEqual(call['collectorVersion'], 'unknown')
        self.assertEqual(call['collectorVersionCoverage'], 'not-recorded')
        self.assertEqual(call['recognitionReason'], 'not-recorded')
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM collection_metadata').fetchone()[0], 0)
        self.assertEqual(len(self.j.db.execute('PRAGMA table_info(call_metadata)').fetchall()), 3)

    def test_mixed_versions_and_missing_phase_metadata_remain_explicit(self):
        self.event('PreToolUse')
        with patch('pulse_version.__version__', '9.9.9'):
            self.event('PostToolUse')
        call = self.j.calls()[0]
        self.assertEqual(call['collectorVersion'], 'mixed')
        self.assertEqual(call['collectorVersions'], [__version__, '9.9.9'])
        self.j.db.execute("DELETE FROM collection_metadata WHERE event IN (SELECT id FROM observation WHERE phase='start')")
        self.j.db.commit()
        call = self.j.calls()[0]
        self.assertEqual(call['collectorVersionCoverage'], 'partial')
        self.assertEqual(call['collectorVersion'], 'unknown')
        self.assertEqual(call['recognitionReason'], 'not-recorded')

    def test_pending_non_shell_and_pruning_have_no_false_command_reason(self):
        self.event('PreToolUse', command='PRIVATE_CODE', tool='Read')
        call = self.j.calls()[0]
        self.assertEqual(call['recognitionReason'], 'not-shell')
        self.assertEqual(call['outcome'], 'pending')
        self.j.db.execute('DELETE FROM observation');self.j.db.commit();self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM collection_metadata').fetchone()[0], 0)

    def test_matching_new_retry_does_not_change_original_capture_version(self):
        self.pair('git status')
        with patch('pulse_version.__version__', '0.14.5'):
            self.pair('git status')
        self.assertEqual(self.j.calls()[0]['collectorVersion'], __version__)
