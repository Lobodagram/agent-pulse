import json
import unittest

from result_metadata import classify


def wrapped(code):
    return {'type':'text','text':json.dumps({'output':'PRIVATE_RESULT_CANARY','wall_time_seconds':1,'exit_code':code})}


class ResultMetadataTests(unittest.TestCase):
    def test_structured_mcp_shell_exit_and_process_polling(self):
        self.assertEqual(classify('PostToolUse',{'tool_response':{'structuredContent':{'exit_code':0}}},'Bash'),('success',0,'structured-exit'))
        self.assertEqual(classify('PostToolUse',{'tool_response':{'exit_code':0,'structuredContent':{'exit_code':1}}},'Bash')[0],'unknown')
        self.assertEqual(classify('PostToolUse',{'tool_response':{'structuredContent':{'session_id':42}}},'functions.write_stdin'),('unknown',None,'running-process'))
        self.assertEqual(classify('PostToolUse',{'tool_response':{'output':'exit_code: 0'}},'functions.write_stdin')[0],'unknown')

    def test_invalid_wrapped_exit_cannot_hide_behind_valid_exit(self):
        for code in (True, '0', 300, -300, 0.5):
            for response in ({'exit_code':0,'content':[wrapped(code)]},
                             {'content':[wrapped(0),wrapped(code)]}):
                with self.subTest(code=code,response=response):
                    self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash'),
                                     ('unknown',None,'conflicting-or-invalid-exit'))

    def test_bounded_content_does_not_skip_possible_conflict(self):
        response={'content':[wrapped(0)]+[{'type':'text','text':'irrelevant'}]*9+[wrapped(1)]}
        self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash'),
                         ('unknown',None,'result-limit-exceeded'))

    def test_valid_single_wrapper_and_direct_agreement(self):
        for code in (0,2,-1):
            for response in ({'content':[wrapped(code)]},{'exit_code':code,'content':[wrapped(code)]}):
                self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash'),
                                 ('success' if code==0 else 'failed',code,'code-mode-result'))

    def test_explicit_failure_still_wins_over_invalid_wrapper(self):
        response={'isError':True,'exit_code':0,'content':[wrapped(True)]}
        self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash')[0],'failed')

    def test_arbitrary_output_and_non_shell_json_not_parsed(self):
        self.assertEqual(classify('PostToolUse',{'tool_response':wrapped(0)['text']},'Bash'),
                         ('unknown',None,'exit-not-reported'))
        self.assertEqual(classify('PostToolUse',{'tool_response':{'content':[wrapped(True)]}},'Read'),
                         ('success',None,'completed-non-shell'))

    def test_oversize_block_and_null_exit_keep_unknown(self):
        response={'exit_code':0,'content':[{'type':'text','text':'x'*(128*1024+1)}]}
        self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash'),
                         ('unknown',None,'result-limit-exceeded'))
        self.assertEqual(classify('PostToolUse',{'tool_response':{'content':[wrapped(None)]}},'Bash')[0], 'unknown')

    def test_projected_unknown_is_private_and_cannot_confirm_skill_load(self):
        from pathlib import Path
        import tempfile
        from journal import Journal
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(Path(tmp)/'state')
            try:
                raw={'session_id':'demo','turn_id':'demo-turn','tool_use_id':'demo-call',
                     'tool_name':'Bash','tool_input':{'command':'cat skills/demo/SKILL.md'},
                     'tool_response':{'exit_code':0,'content':[wrapped(True)]}}
                for event in ('PreToolUse','PostToolUse'):j.record('codex',dict(raw,hook_event_name=event))
                call=j.calls()[0]
                self.assertTrue(call['paired'])
                self.assertEqual(call['outcome'],'unknown')
                self.assertEqual(call['outcomeSource'],'conflicting-or-invalid-exit')
                for table in ('observation','call_metadata','capability_evidence','capability_source'):
                    for row in j.db.execute('SELECT * FROM '+table):
                        self.assertNotIn('PRIVATE_RESULT_CANARY',str(tuple(row)))
                self.assertEqual(j.db.execute('SELECT count(*) FROM capability_evidence').fetchone()[0],0)
            finally:j.close()
