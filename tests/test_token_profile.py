"""Invented token counters only; no native conversations or account reads."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import collector as c
from mcp_server import dispatch
from providers import atomic_json


class TokenProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=c.Store(self.root/'state');self.day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        self.path=self.root/'.codex/sessions/fixture.jsonl';self.path.parent.mkdir(parents=True)

    def tearDown(self):self.store.db.close();self.tmp.cleanup()

    def event(self, total, last, day=None):
        return {'timestamp':(day or self.day)+'T00:00:00Z','type':'event_msg','payload':{'type':'token_count','info':{
            'total_token_usage':self.vector(*total),'last_token_usage':self.vector(*last),'private':'PRIVATE_PAYLOAD'}}}

    def vector(self, i, o, cache):
        return {'input_tokens':i,'output_tokens':o,'cached_input_tokens':cache,'total_tokens':i+o,
                'reasoning_output_tokens':o,'private':'PRIVATE_PAYLOAD'}

    def project(self, events):
        with self.path.open('a') as f:
            for e in events:f.write(json.dumps(e)+'\n')
        with patch('collector.Path.home',return_value=self.root):self.store.project_rollout({'id':'PRIVATE_ID','path':str(self.path)},include_tools=False)
        return self.store.local_token_profile(self.day)

    def test_incremental_duplicate_and_restart_do_not_add_cache_twice(self):
        a=self.event((100,20,60),(50,10,30));b=self.event((140,30,80),(40,10,20))
        p=self.project([a,a,b,b]);self.assertEqual((p['inputTokens'],p['outputTokens'],p['cachedInputTokens']),(90,20,50))
        self.assertEqual(p['profiledTokens'],110);self.assertEqual(p['observedTokens'],110)
        self.assertAlmostEqual(p['cacheHitRate'],50/90);self.assertEqual(p['counterCoverageRate'],1)
        self.assertEqual(p['coverage'],'partial-local');self.assertIsNone(p['subscriptionSavings']);self.assertIsNone(p['modelRequests'])
        self.store.db.close();self.store=c.Store(self.root/'state')
        self.assertEqual(self.project([]),p)
        dump='\n'.join(self.store.db.iterdump());self.assertNotIn('PRIVATE_',dump);self.assertNotIn(str(self.path),dump)

    def test_missing_or_changed_schema_marks_coverage_without_zero_cache(self):
        a=self.event((100,20,60),(50,10,30));b=self.event((140,30,80),(40,10,20))
        del b['payload']['info']['total_token_usage']['cached_input_tokens']
        p=self.project([a,b]);self.assertEqual(p['profiledTokens'],60);self.assertEqual(p['observedTokens'],110)
        self.assertAlmostEqual(p['counterCoverageRate'],60/110);self.assertEqual(p['unprofiledEvents'],1)
        self.assertEqual(p['cachedInputTokens'],30)

    def test_reset_and_inconsistent_deltas_are_not_negative_or_complete(self):
        p=self.project([self.event((100,20,60),(50,10,30)),self.event((20,10,5),(20,10,5)),self.event((30,15,10),(10,5,5))])
        self.assertEqual((p['inputTokens'],p['outputTokens'],p['cachedInputTokens']),(60,15,35))
        self.assertEqual(p['profiledTokens'],p['observedTokens'])
        # Total grows but cache delta exceeds input delta: omit that breakdown.
        p=self.project([self.event((35,20,25),(5,5,2))]);self.assertEqual(p['profiledTokens'],75)
        self.assertEqual(p['observedTokens'],85);self.assertEqual(p['unprofiledEvents'],1)

    def test_midnight_does_not_attribute_previous_day_delta(self):
        yesterday=(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%d')
        p=self.project([self.event((100,20,60),(50,10,30),yesterday),self.event((200,50,100),(20,5,10))])
        self.assertEqual(p['profiledTokens'],25);self.assertEqual(p['observedTokens'],130)
        self.assertEqual((p['inputTokens'],p['outputTokens'],p['cachedInputTokens']),(20,5,10))
        self.assertLess(p['counterCoverageRate'],1)

    def test_invalid_payload_shapes_never_break_the_collector(self):
        for bad in [None,[],False,42,'PRIVATE_PAYLOAD']:
            e=self.event((100,20,60),(50,10,30));e['payload']['info']['total_token_usage']=bad
            self.assertIsNone(c.project_token_event(e));self.assertIsNone(c.project_token_breakdown(e))
        for invalid in [True,-1,1.5,10**16,'40']:
            e=self.event((100,20,60),(50,10,30));e['payload']['info']['total_token_usage']['cached_input_tokens']=invalid
            self.assertIsNone(c.project_token_breakdown(e))

    def test_empty_and_zero_counters_are_distinct(self):
        p=self.store.local_token_profile(self.day);self.assertIsNone(p['inputTokens']);self.assertIsNone(p['cacheHitRate'])
        p=self.project([self.event((0,0,0),(0,0,0))]);self.assertEqual(p['inputTokens'],0);self.assertIsNone(p['cacheHitRate'])

    def test_backlog_jump_never_uses_the_skipped_vector_baseline(self):
        self.project([self.event((100,20,60),(50,10,30))])
        with self.path.open('a') as f:
            f.write(json.dumps({'private':'x'*(5*1024*1024)})+'\n')
        p=self.project([self.event((10000,2000,6000),(50,10,30))])
        self.assertEqual((p['inputTokens'],p['outputTokens'],p['cachedInputTokens']),(100,20,60))
        self.assertEqual(p['profiledTokens'],120);self.assertEqual(p['observedTokens'],120)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM rollout_gaps').fetchone()[0],1)

    def test_scalar_only_existing_history_is_not_replayed_or_reclassified(self):
        self.store.db.execute('INSERT INTO token_events VALUES (?,?,?)',('legacy',self.day,1000));self.store.db.commit()
        p=self.project([self.event((100,20,60),(50,10,30))])
        self.assertEqual(p['profiledTokens'],60);self.assertEqual(p['observedTokens'],1060)
        self.assertEqual(p['unprofiledEvents'],1);self.assertLess(p['counterCoverageRate'],.06)

    def test_snapshot_keeps_account_total_separate_from_local_profile(self):
        p=self.project([self.event((100,20,60),(50,10,30))])
        atomic_json(self.root/'state'/'config.json',{'enabledProviders':['codex'],'localTokens':True})
        native={'id':'codex','name':'Codex','status':'ready','todayTokens':5000,'daily':[], 'quotas':[],'sourceStatus':[]}
        with patch.object(c,'collect_codex',return_value=(native,[])):
            snapshot=c.snapshot(self.root/'state')
        self.assertEqual(snapshot['providers'][0]['todayTokens'],5000)
        self.assertEqual(snapshot['providers'][0]['todayTokenCoverage'],'account-reported')
        self.assertEqual(snapshot['providers'][0]['localTokenProfile'],p)

    def test_mcp_reads_saved_counts_only_with_existing_opt_in(self):
        self.project([self.event((100,20,60),(50,10,30))])
        request={'method':'tools/call','params':{'name':'pulse_efficiency','arguments':{}}}
        with patch.object(c,'collect_codex',side_effect=AssertionError('MCP must not call native APIs')):
            data=json.loads(dispatch(request,self.root/'state')['content'][0]['text']);self.assertIsNone(data['localTokenProfile'])
            atomic_json(self.root/'state'/'config.json',{'enabledProviders':['codex'],'localTokens':True})
            data=json.loads(dispatch(request,self.root/'state')['content'][0]['text']);self.assertEqual(data['localTokenProfile']['cachedInputTokens'],30)
            atomic_json(self.root/'state'/'config.json',{'enabledProviders':['glm'],'localTokens':True})
            data=json.loads(dispatch(request,self.root/'state')['content'][0]['text']);self.assertIsNone(data['localTokenProfile'])
