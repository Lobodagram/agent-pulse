import json
from pathlib import Path
import tempfile
import time
import unittest
from diagnostics import diagnostic_report
from journal import Journal
from result_metadata import classify, response_evidence, stored_response_evidence


class ResponseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.tmp.name)/'state')

    def tearDown(self):
        self.j.close();self.tmp.cleanup()

    def event(self,call,phase,response=None,tool='Bash'):
        raw={'hook_event_name':phase,'session_id':'s','turn_id':call,'tool_use_id':call,
            'tool_name':tool,'tool_input':{'command':'git status'},'timestamp':time.time()-10,
            'tool_response':response,'responseEnvelope':{'PRIVATE':'PRIVATE'}}
        return self.j.record('codex',raw)

    def pair(self,call,response=None,tool='Bash'):
        self.event(call,'PreToolUse',tool=tool)
        self.event(call,'PostToolUse',response,tool)

    def test_missing_string_and_typed_result_are_separate_without_reclassification(self):
        self.pair('string','Process exited with code 0\nPRIVATE_STDOUT')
        self.pair('object',{'output':'PRIVATE_STDOUT'})
        self.pair('typed',{'exit_code':2,'output':'PRIVATE_STDOUT'})
        calls=self.j.calls();unknown=[c for c in calls if c['outcome']=='unknown']
        self.assertEqual(len(unknown),2)
        self.assertEqual({c['responseEnvelope']['responseKind'] for c in unknown},{'object','string'})
        self.assertTrue(all(c['outcomeSource']=='exit-not-reported' for c in unknown))
        self.assertEqual(next(c for c in calls if c['exitCode']==2)['outcome'],'failed')
        self.assertNotIn('PRIVATE',json.dumps(calls))

    def test_exit_field_shape_is_bounded_and_ignores_arbitrary_names(self):
        cases=[({},'absent'),({'exit_code':None},'null'),({'exitCode':True},'invalid'),
            ({'exit_code':0,'exitCode':1},'conflicting'),({'exit_code':0},'valid')]
        for response,expected in cases:
            response['PRIVATE_KEY']='PRIVATE_VALUE'
            result=response_evidence({'tool_response':response},'Bash','unknown')
            self.assertEqual(result['directExit'],expected)
            self.assertNotIn('PRIVATE',json.dumps(result))

    def test_no_stdout_or_text_json_recovers_an_exit(self):
        for raw in [{'tool_response':'{"exit_code":0,"output":"PRIVATE","wall_time_seconds":1}'},
                    {'tool_response':{'output':'exit_code:0 PRIVATE'}},
                    {'tool_output':{'exit_code':0,'PRIVATE':'PRIVATE'}}]:
            self.assertEqual(classify('PostToolUse',raw,'Bash')[0],'unknown')
            result=response_evidence(raw,'Bash','unknown')
            self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(response_evidence({},'Bash','unknown')['responseKind'],'missing')

    def test_valid_mcp_result_wrapper_and_limits_are_shape_only(self):
        block={'text':json.dumps({'output':'PRIVATE','exit_code':0,'wall_time_seconds':1})}
        raw={'tool_response':{'content':[block]*11}}
        result=response_evidence(raw,'Bash','unknown')
        self.assertEqual(result['codeModeWrappers'],10)
        self.assertEqual(result['contentItems'],11)
        self.assertTrue(result['contentLimitReached'])
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(classify('PostToolUse',raw,'Bash')[2],'result-limit-exceeded')

    def test_failure_signal_does_not_reconstruct_or_change_category(self):
        raw={'tool_response':{'isError':True,'content':[{'text':'ReferenceError: PRIVATE_STACK'}]}}
        result=response_evidence(raw,'mcp__node_repl__js','failed')
        self.assertEqual(result['failureCategorySource'],'reported-prefix')
        self.assertEqual(response_evidence(raw,'Bash','failed')['failureCategorySource'],'unreported')
        self.assertEqual(response_evidence(raw,'mcp__node_repl__js','success')['failureCategorySource'],'not-failure')

    def test_first_delivery_stays_explicit_on_result_upgrade(self):
        self.pair('one','PRIVATE')
        first=self.j.calls()[0]['responseEnvelope']
        self.event('one','PostToolUse',{'exit_code':0})
        c=self.j.calls()[0]
        self.assertEqual(c['outcome'],'success')
        self.assertEqual(c['responseEnvelope'],first)
        self.assertEqual(first['responseKind'],'string')

    def test_legacy_retry_never_backfills(self):
        self.pair('one',{'exit_code':0})
        self.j.db.execute('DELETE FROM response_envelope');self.j.db.commit()
        self.pair('one',{'exit_code':0})
        self.assertIsNone(self.j.calls()[0]['responseEnvelope'])
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM response_envelope').fetchone()[0],0)

    def test_pending_and_missing_start_use_only_terminal_evidence(self):
        self.event('pending','PreToolUse')
        self.event('orphan','PostToolUse','PRIVATE')
        calls=self.j.calls()
        self.assertIsNone(next(c for c in calls if c['outcome']=='pending')['responseEnvelope'])
        row=diagnostic_report(self.j)['resultEvidence'][0]
        self.assertEqual((row['calls'],row['finished'],row['missingFinish']),(2,1,1))
        self.assertEqual(row['unknownEnvelopeRecorded'],1)
        self.assertEqual(row['unknownByTool'],{'Bash':1})

    def test_corrupted_and_unknown_fields_are_not_exposed(self):
        good=response_evidence({'tool_response':{}},'Bash','unknown')
        self.assertEqual(stored_response_evidence(json.dumps(good)),good)
        for extra in [{'PRIVATE':'PRIVATE'},{'responseKind':['object']},{'contentItems':True},
                      {'failureCategorySource':'PRIVATE'},{'codeModeWrappers':11}]:
            self.assertIsNone(stored_response_evidence(json.dumps({**good,**extra})))
        self.pair('one',{})
        self.j.db.execute("UPDATE response_envelope SET data='PRIVATE'");self.j.db.commit()
        self.assertIsNone(self.j.calls()[0]['responseEnvelope'])

    def test_side_table_cleanup_and_original_contract(self):
        self.pair('one',{})
        self.assertEqual(len(self.j.db.execute('PRAGMA table_info(call_metadata)').fetchall()),3)
        self.j.db.execute('DELETE FROM observation');self.j.db.commit();self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM response_envelope').fetchone()[0],0)

    def test_failed_non_shell_has_shape_without_invented_error_cause(self):
        self.pair('node',{'isError':True,'content':[{'text':'PRIVATE failure text'}]},'mcp__node_repl__js')
        c=self.j.calls()[0]
        self.assertEqual(c['outcome'],'failed');self.assertEqual(c['failureClass'],'unknown')
        row=diagnostic_report(self.j)['toolGroups'][0]['failureEnvelope']
        self.assertEqual(row['recorded'],1)
        self.assertEqual(row['responseKinds'],{'object':1})
        self.assertEqual(row['categorySources'],{'unreported':1})
        self.assertNotIn('PRIVATE',json.dumps(row))


if __name__=='__main__':unittest.main()
