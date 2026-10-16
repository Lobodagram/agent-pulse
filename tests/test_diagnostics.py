from pathlib import Path
from datetime import datetime, timezone
import json
import tempfile
import time
import unittest
from journal import Journal
from diagnostics import diagnostic_report
from analytics import report
from review_pack import markdown_pack
from mcp_server import dispatch


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self.tmp.name) / 'state')
        self.n = 0

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def pair(self, response, at=None, provider='glm', tool='mcp__node_repl__js', paired=True):
        self.n += 1
        raw = {'session_id': 's', 'turn_id': str(self.n), 'tool_use_id': str(self.n),
               'tool_name': tool, 'tool_input': {'code': 'PRIVATE_BODY_'+str(self.n)},
               'timestamp': at or time.time()-100}
        if paired:
            self.j.record(provider, dict(raw, hook_event_name='PreToolUse'))
        self.j.record(provider, dict(raw, hook_event_name='PostToolUse',
                                    tool_response=response, timestamp=raw['timestamp']+1))

    def test_different_failed_inputs_are_visible_without_claiming_same_cause(self):
        for _ in range(3):
            self.pair({'isError': True, 'content': [{'text': 'PRIVATE_ERROR'}]})
        for _ in range(2):
            self.pair({})
        result = diagnostic_report(self.j)
        row = result['failureGroups'][0]
        self.assertEqual((row['failed'], row['knownOutcomes'], row['distinctFailedInputs']), (3, 5, 3))
        self.assertEqual(row['observedFailureRate'], .6)
        self.assertFalse(row['sameCauseConfirmed'])
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertNotIn('PRIVATE_', '\n'.join(str(tuple(r)) for r in self.j.db.execute('SELECT * FROM observation')))
        self.assertIn('Семейства ошибок', markdown_pack(report(self.j), 'ru'))

    def test_unknown_shell_does_not_turn_into_success_or_failure_rate(self):
        for _ in range(4):
            self.pair('Process exited with code 0', provider='codex', tool='Bash')
        row = diagnostic_report(self.j)['toolGroups'][0]
        self.assertEqual((row['knownOutcomes'], row['unknown']), (0, 4))
        self.assertIsNone(row['observedFailureRate'])
        self.assertEqual(row['outcomeCoverage'], 0)

    def test_future_failure_classes_are_bounded_and_reported_not_reconstructed(self):
        self.pair({'isError':True,'content':[{'text':'ReferenceError: PRIVATE_STACK'}]})
        self.pair({'isError':True,'error':{'code':'MODULE_NOT_FOUND','message':'PRIVATE_STACK'}})
        self.pair({'isError':True,'content':[{'text':'body says TypeError: PRIVATE_STACK'}]})
        row=diagnostic_report(self.j)['failureGroups'][0]
        self.assertEqual(row['failureClasses'], {'reference':1,'module-not-found':1,'unknown':1})
        for table in ('observation','call_metadata','failure_metadata'):
            for record in self.j.db.execute('SELECT * FROM '+table):self.assertNotIn('PRIVATE_',str(tuple(record)))
        self.assertNotIn('PRIVATE_',json.dumps(row))

    def test_success_and_shell_stdout_never_supply_failure_categories(self):
        self.pair({'content':[{'text':'TypeError: PRIVATE_STACK'}]})
        self.pair({'exit_code':1,'content':[{'text':'ReferenceError: PRIVATE_STACK'}]},provider='codex',tool='Bash')
        self.assertEqual([c['failureClass'] for c in self.j.calls()],['unknown','unknown'])

    def test_conflicting_reported_categories_and_legacy_outcomes(self):
        self.pair({'isError':True,'error':{'name':'TypeError','code':'MODULE_NOT_FOUND'}})
        self.assertEqual(self.j.calls()[0]['failureClass'],'conflicting')
        self.j.db.execute('DELETE FROM failure_metadata');self.j.db.commit()
        self.assertEqual(self.j.calls()[0]['failureClass'],'unknown')
        # Old collectors keep their original 3-column metadata insert contract.
        self.assertEqual(len(self.j.db.execute('PRAGMA table_info(call_metadata)').fetchall()),3)
        self.j.db.execute('DELETE FROM observation');self.j.db.commit();self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM failure_metadata').fetchone()[0],0)

    def test_unpaired_failures_do_not_enter_the_known_paired_denominator(self):
        self.pair({'isError': True}, paired=False)
        row = diagnostic_report(self.j)['toolGroups'][0]
        self.assertEqual((row['unpaired'], row['knownOutcomes'], row['failed']), (1, 0, 0))
        self.assertIsNone(row['observedFailureRate'])

    def test_local_day_uses_start_time_and_full_retained_selection(self):
        midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # UTC-2 local midnight is UTC 02:00; all test times precede now.
        start = midnight.timestamp()+2*3600
        if start > time.time()-200:
            start -= 86400
        day = datetime.fromtimestamp(start-2*3600, timezone.utc).date().isoformat()
        self.pair({}, at=start-1)
        for n in range(125):
            self.pair({}, at=start+n)
        result = diagnostic_report(self.j, day=day, utc_offset_minutes=-120)
        self.assertEqual(result['calls'], 125)
        self.assertEqual(result['period']['utcOffsetMinutes'], -120)

    def test_invalid_period_is_rejected(self):
        for day, offset in [('20261010', 0), ('2026-02-30', 0), (None, 120), ('2026-10-10', True), ('2026-10-10', 841)]:
            with self.subTest(day=day, offset=offset), self.assertRaises(ValueError):
                diagnostic_report(self.j, day=day, utc_offset_minutes=offset)

    def test_inventory_age_is_not_connection_availability(self):
        self.j.import_inventory([{'provider': 'glm', 'id': 'test-check', 'kind': 'skill', 'category': 'test',
                                  'status': 'configured', 'observed': time.time()-8*86400}])
        row = diagnostic_report(self.j)['inventoryHealth'][0]
        self.assertEqual(row['state'], 'partly-stale')
        self.assertFalse(row['liveAvailabilityVerified'])
        self.assertEqual(diagnostic_report(self.j, providers=['codex'])['inventoryHealth'][0]['state'], 'unscanned')

    def test_mcp_diagnostics_read_only_contract(self):
        self.pair({'isError': True})
        result = dispatch({'method':'tools/call','params':{'name':'pulse_diagnostics','arguments':{}}}, self.j.state)
        self.assertFalse(result.get('isError', False))
        self.assertNotIn('PRIVATE_', json.dumps(result))
        with self.assertRaises(ValueError):
            dispatch({'method':'tools/call','params':{'name':'pulse_diagnostics','arguments':{'utcOffsetMinutes':True}}}, self.j.state)


if __name__ == '__main__':
    unittest.main()
