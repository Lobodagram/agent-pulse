import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import providers as p
import collector as c

class AdapterTests(unittest.TestCase):
    def test_claude_context_not_spend_and_private_fields_discarded(self):
        data=p.claude_statusline({'context_window':{'total_input_tokens':120,'total_output_tokens':30},'rate_limits':{'five_hour':{'used_percentage':25,'resets_at':123}},'transcript_path':'private/path','session_name':'private conversation','cwd':'private/path'})
        self.assertEqual(data['contextTokens'],150);self.assertIsNone(data['todayTokens']);self.assertEqual(data['quotas'][0]['remainingPercent'],75)
        self.assertNotIn('private',json.dumps(data))
    def test_import_numbers_names_and_freshness(self):
        data=p.normalized({'todayTokens':True,'tools':[{'name':'Bearer-PRIVATE','count':12},{'name':'read_file','count':2,'arguments':'PRIVATE'}],'observedAt':time.time()},'cursor')
        self.assertIsNone(data['todayTokens']);self.assertEqual(len(data['tools']),1);self.assertNotIn('PRIVATE',json.dumps(data))
        self.assertEqual(p.normalized({'observedAt':1},'cursor')['status'],'stale')
        self.assertEqual(p.normalized({'observedAt':time.time()+1000},'cursor')['status'],'stale')
    def test_missing_lists_do_not_become_zero(self):
        r=p.normalized({'quotas':None,'daily':None,'tools':None},'kimi')
        self.assertIsNone(r['todayTokens']);self.assertEqual(r['quotas'],[])
    def test_kimi_quota_units_not_tokens(self):
        r=p.kimi_quotas({'usage':{'limit':100,'used':30,'reset_at':'2027-01-03T00:00:00Z'},'limits':[{'detail':{'limit':20,'remaining':10}}]})
        self.assertEqual(r['quotas'][0]['remainingPercent'],70);self.assertEqual(r['quotas'][1]['remainingPercent'],50)
        self.assertIsNone(r['todayTokens'])
    def test_qwen_actual_daily_and_heatmap_contract(self):
        r=p.qwen_dashboard({'summary':{'totalTokens':100,'sessions':2},'daily':[{'date':'2027-01-01','tokens':100}], 'heatmap':{'2027-01-01':{'tokens':99},'2026-12-31':{'tokens':20}},'skills':[{'name':'review','count':3}]})
        self.assertEqual(r['todayTokens'],100);self.assertEqual(len(r['daily']),2);self.assertEqual(next(x['tokens'] for x in r['daily'] if x['date']=='2027-01-01'),100)
        self.assertEqual(r['tools'][0]['name'],'skill.review');self.assertEqual(r['quotas'],[])
    def test_qwen_external_redirect_and_secret_source_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch('providers.get_json') as request:
            r=p.collect_extra('qwen',d,{'qwenBaseUrl':'https://external.example'})
            self.assertEqual(r['status'],'unavailable');request.assert_not_called()
            r=p.collect_extra('qwen',d,{'qwenBaseUrl':'http://user:pass@127.0.0.1:5000'})
            self.assertEqual(r['status'],'unavailable');request.assert_not_called()
        self.assertIsNone(p.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_config_default_no_local_event_read(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(p.load_config(d)['localPatterns'])
            p.atomic_json(Path(d)/'config.json',{'enabledProviders':['cursor','cursor'],'localPatterns':False})
            self.assertEqual(p.load_config(d)['enabledProviders'],['cursor'])
    def test_snapshot_selected_providers_and_no_codex_start(self):
        with tempfile.TemporaryDirectory() as d,patch('collector.collect_codex') as codex,patch('collector.collect_glm') as glm:
            p.atomic_json(Path(d)/'config.json',{'enabledProviders':['cursor'],'localPatterns':False})
            p.atomic_json(Path(d)/'imports/cursor.json',{'todayTokens':10,'observedAt':time.time()})
            r=c.snapshot(d);self.assertEqual([x['id'] for x in r['providers']],['cursor']);self.assertEqual(r['providers'][0]['todayTokens'],10)
            codex.assert_not_called();glm.assert_not_called()
    def test_crossplatform_rpc_bounded_transport(self):
        program='import sys,json\nfor line in sys.stdin:\n x=json.loads(line); print(json.dumps({"id":x["id"],"result":{"ok":True}}),flush=True)'
        r=c.RPC([sys.executable,'-u','-c',program],timeout=2)
        try:self.assertTrue(r.call('initialize')['ok'])
        finally:r.close()
        self.assertIsNotNone(r.p.poll())
    def test_native_rpc_timeout_cleanup(self):
        r=c.RPC([sys.executable,'-u','-c','import time;time.sleep(10)'],timeout=.1)
        try:
            with self.assertRaises(c.Unavailable):r.call('initialize')
        finally:r.close()
        self.assertIsNotNone(r.p.poll())
