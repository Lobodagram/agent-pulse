import json
from pathlib import Path
import tempfile
import time
import unittest
from analytics import report, compare
from journal import Journal
from model_evidence import model_history
from mcp_server import dispatch


class ModelEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(self.tmp.name);self.at=time.time()-100
    def tearDown(self):
        self.j.close();self.tmp.cleanup()
    def event(self,call,event,model=None,at=None,**extra):
        raw={'session_id':'s','turn_id':'t','tool_use_id':call,'hook_event_name':event,
             'tool_name':'Read','tool_input':{},'timestamp':self.at if at is None else at}
        if model is not None:raw['model']=model
        raw.update(extra);self.j.record('glm',raw)
    def pair(self,call,model=None,at=None,finish_model=None,**extra):
        at=self.at if at is None else at
        self.event(call,'PreToolUse',model,at,**extra)
        self.event(call,'PostToolUse',model if finish_model is None else finish_model,at+1,**extra)
    def history(self):return report(self.j)['sessions'][0]['modelHistory']
    def test_native_change_and_unknown_gap(self):
        self.pair('a','glm-5.3');self.pair('b','glm-5.3-flash',self.at+2)
        self.pair('c',at=self.at+4);self.pair('d','glm-5.3',self.at+6)
        h=self.history();self.assertEqual(h['reportedChanges'],1)
        self.assertEqual([s['transition'] for s in h['segments']],['first-observed','reported-change','unknown-gap','after-unknown'])
        self.assertEqual(h['unknownModelCalls'],1)
    def test_same_model_merges_only_observed_calls(self):
        for i in range(3):self.pair(str(i),'glm-5.3',self.at+i*2)
        h=self.history();self.assertEqual(len(h['segments']),1);self.assertEqual(h['segments'][0]['calls'],3)
        self.assertEqual(h['segments'][0]['lastObservedAt'],self.at+4)
    def test_session_start_is_not_inherited(self):
        self.event('lifecycle','SessionStart','glm-5.3');self.pair('a')
        self.assertEqual(self.j.calls()[0]['model'],'other');self.assertEqual(self.history()['knownModelCalls'],0)
    def test_finish_only_model_is_identified_and_labeled(self):
        self.event('a','PreToolUse');self.event('a','PostToolUse','glm-5.3',self.at+1)
        c=self.j.calls()[0];self.assertEqual(c['model'],'glm-5.3');self.assertEqual(c['modelSource'],'call-finish-only')
    def test_start_finish_conflict_unknown(self):
        self.pair('a','glm-5.3',finish_model='glm-5.3-flash')
        c=self.j.calls()[0];self.assertEqual(c['model'],'other');self.assertEqual(c['modelSource'],'conflicting-call-models')
    def test_duplicate_model_conflict_sticky(self):
        self.pair('a','glm-5.3');self.event('a','PreToolUse','glm-5.3-flash')
        self.event('a','PreToolUse','glm-5.3')
        c=self.j.calls()[0];self.assertEqual(c['model'],'other');self.assertEqual(c['modelSource'],'conflicting-event-models')
    def test_later_duplicate_clarifies_missing_field(self):
        self.pair('a');self.event('a','PostToolUse','glm-5.3',self.at+2)
        self.assertEqual(self.j.calls()[0]['modelSource'],'call-finish-only')
    def test_response_and_input_model_are_not_model_identity(self):
        self.event('a','PreToolUse',tool_input={'model':'glm-5.3'})
        self.event('a','PostToolUse',tool_response={'model':'glm-5.3','text':'glm-5.3-flash'},at=self.at+1)
        self.assertEqual(self.j.calls()[0]['model'],'other')
    def test_invalid_or_secret_identifier_not_retained(self):
        for i,model in enumerate(['GLM Flash','sk-'+'x'*30,{'name':'glm-5.3'},True]):
            self.pair(str(i),model,self.at+i*2)
        self.assertEqual(self.history()['knownModelCalls'],0)
        self.assertNotIn('sk-',Path(self.tmp.name,'journal.sqlite').read_bytes().decode('latin1'))
    def test_parallel_actor_models_not_changes(self):
        self.pair('a','glm-5.3',agent_id='one');self.pair('b','glm-5.3-flash',self.at+2,agent_id='two')
        self.assertEqual(self.history()['reportedChanges'],0)
    def test_overlapping_calls_not_switches(self):
        self.event('a','PreToolUse','glm-5.3');self.event('a','PostToolUse','glm-5.3',self.at+5)
        self.pair('b','glm-5.3-flash',self.at+2)
        h=self.history();self.assertEqual(h['reportedChanges'],0);self.assertEqual(h['segments'][1]['transition'],'overlapping-observations')
    def test_invalid_timing_not_model_switch(self):
        self.event('a','PreToolUse','glm-5.3');self.event('a','PostToolUse','glm-5.3',self.at-1)
        self.pair('b','glm-5.3-flash',self.at+2);self.assertEqual(self.history()['reportedChanges'],0)
    def test_outer_parallel_call_blocks_later_inner_switch(self):
        self.event('a','PreToolUse','glm-large');self.event('a','PostToolUse','glm-large',self.at+9)
        self.pair('b','glm-small',self.at+2);self.pair('c','glm-other',self.at+4)
        self.assertEqual(self.history()['reportedChanges'],0)
        self.assertEqual(self.history()['segments'][-1]['transition'],'overlapping-observations')
    def test_last_segments_bounded(self):
        for i in range(5):self.pair(str(i),'glm-a' if i%2 else 'glm-b',self.at+i*2)
        h=model_history(self.j.calls(),2);self.assertTrue(h['truncated']);self.assertEqual(len(h['segments']),2)
        self.assertEqual(h['segments'][-1]['firstObservedAt'],self.at+8);self.assertEqual(h['knownModelCalls'],5)
    def test_model_history_reaches_readonly_mcp_and_comparison(self):
        self.pair('a','glm-5.3');sid=self.j.calls()[0]['session'];self.j.annotate(sid,'work','accepted','before')
        r=dispatch({'method':'tools/call','params':{'name':'pulse_session','arguments':{'sessionId':sid}}},self.tmp.name)
        data=json.loads(r['content'][0]['text']);self.assertEqual(data['modelHistory']['knownModelCalls'],1)
        self.assertEqual(compare(self.j,'work','before','after')['groups']['before']['models'],['glm-5.3'])


if __name__=='__main__':unittest.main()
