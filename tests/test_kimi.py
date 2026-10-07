import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import collector
import instrumentation
from journal import Journal
import provider_secrets
import providers

def save_provider(state,provider):
    provider_secrets.save_key(state,'fixture-'+provider,provider)

class KimiTests(unittest.TestCase):
    def test_declared_windows_and_zero_quota_not_tokens(self):
        p=providers.kimi_quotas({'usage':{'limit':100,'used':100},'limits':[{'window':{'duration':5,'timeUnit':'HOUR'},'detail':{'limit':20,'remaining':10,'reset_at':'2030-01-01T00:00:00Z'}}]})
        self.assertEqual([q['durationMinutes'] for q in p['quotas']],[10080,300])
        self.assertEqual([q['remainingPercent'] for q in p['quotas']],[0,50])
        self.assertIsNone(p['todayTokens']);self.assertEqual(p['todayTokenCoverage'],'not-reported')
    def test_ambiguous_invalid_quota_and_reset_remain_unknown(self):
        for detail in [{'limit':True,'remaining':5},{'limit':10,'used':20},{'limit':10,'used':3,'remaining':9}]:
            self.assertEqual(providers.kimi_quotas({'usage':detail})['status'],'unavailable')
        p=providers.kimi_quotas({'usage':{'limit':10,'used':0,'reset_at':'2030-01-01T00:00:00'},'limits':[{'window':{'duration':True,'timeUnit':'HOUR'},'detail':{'limit':10,'used':2}}]})
        self.assertIsNone(p['quotas'][0]['resetsAt']);self.assertIsNone(p['quotas'][1]['durationMinutes'])
        p=providers.kimi_quotas({'limits':[{'duration':300,'timeUnit':'MINUTE','limit':10,'used':1}]*2})
        self.assertTrue(all(q['remainingPercent'] is None for q in p['quotas']))
    def test_opt_in_key_request_and_fail_closed_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch('providers.get_json') as get:
            self.assertEqual(providers.collect_extra('kimi',tmp,{})['status'],'unavailable');get.assert_not_called()
            provider_secrets.save_key(tmp,'fixture-kimi','kimi')
            get.return_value={'usage':{'limit':10,'used':3}}
            providers.patch_config(tmp,{'enabledProviders':['kimi']})
            result=collector.snapshot(tmp);self.assertEqual(result['providers'][0]['quotas'][0]['remainingPercent'],70)
            self.assertEqual(get.call_args.args[0],'https://api.kimi.com/coding/v1/usages')
            get.side_effect=ValueError('PRIVATE_QUOTA_PAYLOAD')
            result=collector.snapshot(tmp)['providers'][0]
            self.assertEqual(result['status'],'unavailable');self.assertEqual(result['quotas'],[])
            self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('fixture-kimi',json.dumps(result))
    def test_conflicting_window_and_oversized_suffix_cannot_establish_quota(self):
        for raw in [
            {'limits':[{'window':{'duration':5,'timeUnit':'HOUR'},'detail':{'duration':7,'timeUnit':'DAY','limit':10,'used':0}}]},
            {'limits':[{'duration':300,'timeUnit':'MINUTE','limit':10,'used':0}]*9},
        ]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):providers.kimi_quotas(raw)
    def test_explicit_region_is_allowlisted_and_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp,patch('providers.get_json') as get:
            provider_secrets.save_key(tmp,'fixture-kimi','kimi','global')
            get.return_value={'usage':{'limit':10,'used':2}}
            self.assertEqual(providers.collect_extra('kimi',tmp,{})['status'],'ready')
            self.assertEqual(get.call_args.args[0],'https://api.kimi.ai/coding/v1/usages')
            get.reset_mock();get.side_effect=ValueError('PRIVATE')
            self.assertEqual(providers.collect_extra('kimi',tmp,{})['status'],'unavailable')
            self.assertEqual(get.call_count,1)
            with self.assertRaises(ValueError):provider_secrets.save_key(tmp,'fixture-kimi','kimi','untrusted.example')
    def test_toml_install_idempotent_remove_preserves_native_bytes(self):
        for ending in ('','\n','\r\n'):
            with self.subTest(ending=repr(ending)),tempfile.TemporaryDirectory() as tmp:
                path=instrumentation.native_path('kimi',tmp);path.parent.mkdir()
                original=('# preserved comment\n[[hooks]]\nevent="Stop"\ncommand="existing-audit"\n[providers.custom]\napi_key="PRIVATE_NATIVE_CANARY"'+ending).encode()
                path.write_bytes(original)
                state=Path(tmp)/'pulse'
                instrumentation.configure_hooks('kimi',state,home=tmp)
                first=path.read_bytes();instrumentation.configure_hooks('kimi',state,home=tmp)
                self.assertEqual(path.read_bytes(),first)
                hooks=tomllib.loads(first.decode())['hooks'];self.assertEqual(len(hooks),9)
                self.assertEqual(hooks[0]['command'],'existing-audit')
                self.assertTrue(all(set(h)=={'event','command','timeout'} and h['timeout']==2 for h in hooks[1:]))
                instrumentation.configure_hooks('kimi',state,False,home=tmp)
                self.assertEqual(path.read_bytes(),original)
                self.assertEqual([x.name for x in path.parent.iterdir()],['config.toml'])
    def test_invalid_toml_and_symlink_are_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=instrumentation.native_path('kimi',tmp);path.parent.mkdir();path.write_bytes(b'broken = [')
            with self.assertRaises(ValueError):instrumentation.configure_hooks('kimi',Path(tmp)/'pulse',home=tmp)
            self.assertEqual(path.read_bytes(),b'broken = [')
            path.write_text(instrumentation.KIMI_BEGIN)
            with self.assertRaises(ValueError):instrumentation.configure_hooks('kimi',Path(tmp)/'pulse',home=tmp)
            if os.name!='nt':
                path.unlink();target=Path(tmp)/'untouched';target.write_text('')
                path.symlink_to(target)
                with self.assertRaises(ValueError):instrumentation.configure_hooks('kimi',Path(tmp)/'pulse',home=tmp)
                self.assertEqual(target.read_text(),'')
    def test_native_snake_call_id_pairing_turn_id_and_payload_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp)
            try:
                for event in ['PreToolUse','PostToolUse']:
                    j.record('kimi',{'hook_event_name':event,'session_id':'native-session','turn_id':42,'tool_call_id':'call-1','tool_name':'Shell','tool_input':{'command':'git status'},'tool_output':'PRIVATE_OUTPUT_CANARY','prompt':'PRIVATE_PROMPT_CANARY'})
                rows=j.db.execute('SELECT phase,turn_source,outcome,model FROM observation').fetchall()
                self.assertEqual({r['phase'] for r in rows},{'start','finish'})
                self.assertTrue(all(r['turn_source']=='native' and r['model']=='other' for r in rows))
                self.assertEqual(next(r['outcome'] for r in rows if r['phase']=='finish'),'unknown')
                self.assertNotIn('PRIVATE', '\n'.join(j.db.iterdump()))
            finally:j.close()
    def test_concurrent_key_updates_preserve_journal_and_other_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp);key=j.key;j.close()
            ctx=multiprocessing.get_context('spawn');workers=[ctx.Process(target=save_provider,args=(tmp,p)) for p in ['glm','kimi']]
            for p in workers:p.start()
            for p in workers:p.join(10);self.assertEqual(p.exitcode,0)
            raw=provider_secrets.secrets(tmp);self.assertEqual(set(raw),{'glm','kimi','journalHmacKey'})
            j=Journal(tmp);self.assertEqual(j.key,key);j.close()
            provider_secrets.save_key(tmp,'','kimi')
            self.assertEqual(set(provider_secrets.secrets(tmp)),{'glm','journalHmacKey'})
            with self.assertRaises(ValueError):provider_secrets.save_key(tmp,'fixture','unknown')
