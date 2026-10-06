import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import glm_quota as g
from compact_summary import provider_line

class GLMQuotaTests(unittest.TestCase):
    def row(self,unit=3,number=5,percentage=21.8,**extra):return {'type':'CREDIT_LIMIT','unit':unit,'number':number,'percentage':percentage,'nextResetTime':1791377280000,**extra}
    def raw(self,*rows):return {'code':200,'data':{'limits':list(rows)}}
    def test_windows_consumed_percentage_and_reset_milliseconds(self):
        rows=g.windows(self.raw(self.row(),self.row(6,1,35),self.row(5,1,90,type='TIME_LIMIT')))
        self.assertEqual([x['durationMinutes'] for x in rows],[300,10080])
        self.assertAlmostEqual(rows[0]['remainingPercent'],78.2)
        self.assertEqual(rows[1]['remainingPercent'],65)
        self.assertEqual(rows[0]['resetsAt'],1791377280)
        self.assertEqual(provider_line({'id':'glm','quotas':rows}),'GLM 5h 78% · 7d 65%')
    def test_native_success_envelopes(self):
        for code in [None,0,200]:
            self.assertEqual(len(g.windows(self.raw(self.row()) | {'code':code})),2)
        with self.assertRaises(ValueError):g.windows(self.raw(self.row()) | {'success':False})
    def test_missing_week_not_inferred_from_monthly_mcp(self):
        rows=g.windows(self.raw(self.row(),self.row(5,1,0,type='TIME_LIMIT')))
        self.assertIsNone(rows[1]['remainingPercent']);self.assertIsNone(rows[1]['resetsAt'])
    def test_zero_and_exhausted_are_known(self):
        rows=g.windows(self.raw(self.row(percentage=0),self.row(6,1,100)))
        self.assertEqual([r['remainingPercent'] for r in rows],[100,0])
    def test_bad_percentages_units_duplicates_are_unknown(self):
        for v in [True,-1,101,'25',float('nan'),float('inf')]:
            rows=g.windows(self.raw(self.row(percentage=v),self.row(6,1,10)))
            self.assertIsNone(rows[0]['remainingPercent'])
        rows=g.windows(self.raw(self.row(),self.row(),self.row(6,1,10)))
        self.assertIsNone(rows[0]['remainingPercent'])
        for row in [self.row(unit='3'),self.row(unit=True),self.row(number=True),self.row(type='TIME_LIMIT')]:
            with self.assertRaises(ValueError):g.windows(self.raw(row))
    def test_epoch_seconds_are_not_guessed_as_milliseconds(self):
        rows=g.windows(self.raw(self.row(nextResetTime=1791377280)))
        self.assertIsNone(rows[0]['resetsAt'])
    def test_reject_business_error_and_schema(self):
        for raw in [None,{}, {'code':401,'data':{'limits':[self.row()]}},self.raw(),{'code':True,'data':{'limits':[self.row()]}}]:
            with self.assertRaises(ValueError):g.windows(raw)
    def test_key_stays_in_protected_file_other_providers_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            from providers import atomic_json
            path=Path(tmp)/'Secrets.json';atomic_json(path,{'kimi':{'api_key':'fixture-kimi'}})
            self.assertEqual(g.save_key(tmp,'fixture-glm'),{'saved':True})
            if os.name!='nt':self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(g.save_key(tmp,''),{'saved':False})
            self.assertEqual(json.loads(path.read_text()),{'kimi':{'api_key':'fixture-kimi'}})
    def test_no_key_no_network_failure_clears_quota_and_drops_payload(self):
        with tempfile.TemporaryDirectory() as tmp,patch('providers.get_json') as get:
            self.assertEqual(g.collect(tmp)['quotaStatus'],'not-configured');get.assert_not_called()
            g.save_key(tmp,'fixture-glm');get.return_value=self.raw(self.row())
            result=g.collect(tmp);self.assertEqual(result['quotaStatus'],'ready');self.assertNotIn('fixture-glm',json.dumps(result))
            self.assertEqual(get.call_args.args[0],g.URL)
            get.side_effect=ValueError('private response fixture-glm')
            result=g.collect(tmp);self.assertEqual(result['quotas'],[]);self.assertIsNone(result['quotaObservedAt']);self.assertNotIn('fixture-glm',json.dumps(result))
    def test_key_and_file_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key in [None,'a\nb','a b','x'*4097]:
                with self.assertRaises(ValueError):g.save_key(tmp,key)
            if os.name!='nt':
                g.save_key(tmp,'fixture');os.chmod(Path(tmp)/'Secrets.json',0o644)
                self.assertEqual(g.collect(tmp)['quotaStatus'],'unavailable')
    def test_remote_quota_is_independent_of_missing_local_cli(self):
        import collector
        with tempfile.TemporaryDirectory() as tmp,patch('collector.zcode_paths',return_value=(Path(tmp)/'missing',Path(tmp)/'missing')),patch('glm_quota.collect',return_value={'quotas':g.windows(self.raw(self.row())),'quotaStatus':'ready','quotaObservedAt':123}):
            result=collector.collect_glm('2026-10-06',{'nodePath':str(Path(tmp)/'missing')},tmp)
            self.assertEqual(result['status'],'ready');self.assertIsNone(result['todayTokens']);self.assertEqual(len(result['quotas']),2)
    def test_missing_quota_does_not_break_local_tokens(self):
        import collector
        class RPC:
            def __init__(self,*a,**k):pass
            def call(self,*a):return {'summary':{'totalTokens':100},'heatmap':{'weeks':[{'days':[{'date':'2026-10-06','totalTokens':40}]}]}}
            def close(self):pass
        with tempfile.TemporaryDirectory() as tmp,patch('collector.RPC',RPC),patch.object(Path,'is_file',return_value=True),patch('glm_quota.collect',return_value={'quotas':[],'quotaStatus':'unavailable'}):
            result=collector.collect_glm('2026-10-06',{'nodePath':'fixture'},tmp)
            self.assertEqual(result['status'],'ready');self.assertEqual(result['todayTokens'],40);self.assertEqual(result['quotas'],[])
