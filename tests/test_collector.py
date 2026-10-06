import json
import math
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import sys
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import collector as c

class ProjectionTests(unittest.TestCase):
    def event(self,payload,event_type='response_item'):
        return {'timestamp':datetime.now(timezone.utc).isoformat(),'type':event_type,'payload':payload}
    def test_numbers_and_missing_quota_are_not_zero(self):
        for invalid in [None,True,-1,float('inf'),float('nan'),'100']:
            self.assertIsNone(c.number(invalid))
        q=c.quota_windows({'rateLimits':{'primary':{'usedPercent':None},'secondary':{'usedPercent':120}}})
        self.assertIsNone(q[0]['remainingPercent']);self.assertEqual(q[1]['remainingPercent'],0)
    def test_new_quota_map_preferred_and_clamped(self):
        q=c.quota_windows({'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':7,'windowDurationMins':300,'resetsAt':123}}},'rateLimits':{'primary':{'usedPercent':50}}})
        self.assertEqual(q[0]['remainingPercent'],93);self.assertEqual(q[0]['durationMinutes'],300)
    def test_missing_daily_bucket_not_zero(self):
        x=c.codex_usage({'dailyUsageBuckets':[{'startDate':'2026-10-05','tokens':12}]},'2026-10-06')
        self.assertIsNone(x['todayTokens'])
    def test_secret_and_chat_fields_not_projected(self):
        secret='bcm_'+'confidential_fixture_value'
        self.assertEqual(c.project_event(self.event({'type':'message','text':secret})),[])
        self.assertEqual(c.project_event(self.event({'type':'function_call_output','output':secret})),[])
        r=c.project_event(self.event({'type':'function_call','name':'functions.exec','arguments':'await tools.exec_command({cmd:"'+secret+'"}); await tools.exec_command({cmd:"private text"})'}))
        self.assertEqual(len(r),1);self.assertEqual(r[0][1],'exec_command')
        self.assertNotIn(secret,json.dumps(r));self.assertNotIn('private text',json.dumps(r))
        self.assertEqual(c.safe_name(secret),'other')
    def test_tokens_project_only_counters(self):
        e=self.event({'type':'token_count','info':{'total_token_usage':{'total_tokens':100},'last_token_usage':{'total_tokens':10},'private':'ignored'},'rate_limits':{'private':'ignored'}},'event_msg')
        r=c.project_token_event(e);self.assertEqual(r[1:],(100,10));self.assertNotIn('ignored',json.dumps(r))
    def test_current_custom_code_tool_events_and_namespaces(self):
        e=self.event({'type':'custom_tool_call','name':'exec','input':'await tools.exec_command({cmd:"python3 -m unittest /private"})'})
        names={x[1] for x in c.project_event(e)}
        self.assertEqual(names,{'exec_command','command.tests'})
        e=self.event({'type':'function_call','name':'js','namespace':'mcp__cua_repl','arguments':'{"code":"private"}'})
        self.assertEqual(c.project_event(e)[0][1],'mcp__cua_repl.js')
    def test_command_categories_only_and_no_arguments_retained(self):
        cmd='rg --files /private/example && python3 -m unittest && git status'
        classes=c.command_classes(json.dumps({'cmd':cmd}))
        self.assertEqual(set(classes),{'command.search_files','command.tests','command.git_inspection'})
        self.assertNotIn('/private/example',json.dumps(classes))
        self.assertEqual(c.command_classes('not JSON'),[])
    def test_code_mode_categories_are_static_and_require_shell_tool(self):
        self.assertEqual(c.command_classes('"git status"',code_mode=True),[])
        classes=c.command_classes('await tools.exec_command({cmd:"./build.sh"})',code_mode=True)
        self.assertEqual(classes,['command.build'])
    def test_stale_events_rejected(self):
        e={'timestamp':'2020-01-01T00:00:00Z','type':'response_item','payload':{'type':'function_call','name':'read_file'}}
        self.assertEqual(c.project_event(e),[])
    def test_disallowed_rpc_never_sent(self):
        rpc=object.__new__(c.RPC)
        with self.assertRaises(c.Unavailable):rpc.call('turn/start',{'input':'private'})

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=c.Store(Path(self.temp.name)/'state')
    def tearDown(self):
        self.store.db.close();self.temp.cleanup()
    def test_projection_migration_rebuilds_only_own_event_categories(self):
        directory=self.store.directory
        self.store.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',('old','codex',int(time.time()),'js',0))
        self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('_projection_version','3'))
        self.store.set_subscription('codex','2026-11-01','renewal')
        self.store.db.close();self.store=c.Store(directory)
        self.assertEqual(self.store.patterns([]),[])
        self.assertEqual(self.store.settings()['codex']['date'],'2026-11-01')
    def test_settings_roundtrip_and_invalid_dates(self):
        self.store.set_subscription('codex','2026-11-01','renewal')
        self.assertEqual(self.store.settings()['codex']['date'],'2026-11-01')
        with self.assertRaises(ValueError):self.store.set_subscription('codex','2026-02-31','expiry')
        with self.assertRaises(ValueError):self.store.set_subscription('other','','none')
    def test_duplicate_days_and_stale_cache(self):
        p={'id':'codex','status':'ready','daily':[{'date':datetime.now().strftime('%Y-%m-%d'),'tokens':100}],'tokenSource':'native','todayTokens':100}
        self.store.persist(p);self.store.persist(p)
        self.assertEqual(len(self.store.history()),1)
        self.assertEqual(self.store.latest('codex')['status'],'stale')
    def test_private_permissions_and_symlink_rejected(self):
        if os.name=='nt':self.skipTest('POSIX modes; Windows uses inherited NTFS ACLs')
        self.assertEqual((self.store.directory.stat().st_mode & 0o777),0o700)
        self.assertEqual(((self.store.directory/'metrics.sqlite').stat().st_mode & 0o777),0o600)
        link=Path(self.temp.name)/'link';link.symlink_to(self.store.directory)
        with self.assertRaises(ValueError):c.Store(link)
    def test_rollout_dedup_incremental_tokens_and_no_text_retention(self):
        # Only fake files in a fake home. No native database or actual chat is touched.
        root=Path(self.temp.name);sessions=root/'.codex/sessions';sessions.mkdir(parents=True)
        path=sessions/'fixture.jsonl';now=datetime.now(timezone.utc).isoformat()
        def tokens(total,last):return {'timestamp':now,'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'total_tokens':total},'last_token_usage':{'total_tokens':last}}}}
        lines=[tokens(100,10),tokens(100,10),tokens(130,30),tokens(20,30),tokens(20,30),tokens(40,20),{'timestamp':now,'type':'response_item','payload':{'type':'function_call','name':'exec_command','arguments':'confidential fixture text'}}]
        path.write_text(''.join(json.dumps(x)+'\n' for x in lines))
        with patch('collector.Path.home',return_value=root):
            self.store.project_rollout({'id':'fixture','path':str(path)})
            self.store.project_rollout({'id':'fixture','path':str(path)})
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        self.assertEqual(self.store.local_tokens(day),60)
        self.assertEqual(self.store.patterns([])[0]['count'],1)
        dump='\n'.join(self.store.db.iterdump())
        self.assertNotIn('confidential fixture text',dump);self.assertNotIn(str(path),dump)
    def test_local_partial_history_does_not_overwrite_account_day(self):
        day=datetime.now().strftime('%Y-%m-%d')
        self.store.db.execute('INSERT INTO token_events VALUES (?,?,?)',('a',day,10))
        self.store.persist({'id':'codex','daily':[{'date':day,'tokens':100}],'tokenSource':'account','status':'ready'})
        self.store.persist_local_tokens();self.assertEqual(self.store.history()[0]['tokens'],100)

if __name__=='__main__':unittest.main()

import collector
class QuotaRegressionTests(unittest.TestCase):
    def test_main_quota_bucket_precedes_other_models(self):
        raw={'rateLimitsByLimitId':{'other':{'primary':{'usedPercent':2,'windowDurationMins':300}},'codex':{'primary':{'usedPercent':93,'windowDurationMins':300},'secondary':{'usedPercent':50,'windowDurationMins':10080}}}}
        result=collector.quota_windows(raw)
        self.assertEqual([x['bucket'] for x in result[:2]],['codex','codex']);self.assertEqual(result[0]['remainingPercent'],7)

    def test_fast_limits_does_not_request_tokens_or_threads(self):
        calls=[]
        class FakeRPC:
            def __init__(self,*args,**kwargs):pass
            def call(self,method,params=None):
                calls.append(method)
                return {'accountId':'synthetic','rateLimits':{'primary':{'usedPercent':93,'windowDurationMins':300}}} if method=='account/rateLimits/read' else {}
            def send(self,*args):pass
            def close(self):pass
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp, patch.object(collector,'RPC',FakeRPC):result,_=collector.collect_codex('2026-10-06',quota_only=True,directory=tmp)
        self.assertEqual(result['status'],'ready');self.assertIsNotNone(result['quotaObservedAt'])
        self.assertEqual(calls,['initialize','account/rateLimits/read'])

    def test_account_switch_preserves_general_history_and_clears_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=collector.Store(tmp)
            try:
                base={'id':'codex','accountScope':'a','daily':[{'date':'2026-10-06','tokens':120}],'status':'ready'}
                store.persist(base);store.set_subscription('codex','2026-12-01','renewal')
                store.persist(dict(base,accountScope='b',daily=[]))
                self.assertEqual(store.history()[0]['tokens'],120);self.assertNotIn('codex',store.settings());self.assertEqual(store.latest('codex')['accountScope'],'b')
            finally:store.db.close()

    def test_failed_read_does_not_show_previous_account_limits(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            store=collector.Store(tmp)
            store.persist({'id':'codex','name':'Codex','accountScope':'previous','status':'ready','daily':[{'date':'2026-10-06','tokens':100}],'quotas':[{'remainingPercent':8}],'sourceStatus':[]});store.db.close()
            import providers
            providers.atomic_json(Path(tmp)/'config.json',{'enabledProviders':['codex'],'localPatterns':False})
            unavailable={'id':'codex','name':'Codex','status':'unavailable','quotas':[],'daily':[],'sourceStatus':['native_unavailable']}
            with patch.object(collector,'collect_codex',return_value=(unavailable,[])):result=collector.snapshot(tmp)
            self.assertEqual(result['providers'][0]['quotas'],[]);self.assertEqual(result['history'][0]['tokens'],100);self.assertEqual(result['providers'][0]['status'],'unavailable')

    def test_account_history_sums_and_upserts_without_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=collector.Store(tmp)
            try:
                base={'id':'codex','accountScope':'a','daily':[{'date':'2026-10-06','tokens':120}],'status':'ready'}
                store.persist(base);store.persist(base)
                store.persist(dict(base,accountScope='b',daily=[{'date':'2026-10-06','tokens':30}]))
                self.assertEqual(store.history()[0]['tokens'],150)
                store.persist(dict(base,daily=[{'date':'2026-10-06','tokens':125}]))
                self.assertEqual(store.history()[0]['tokens'],155)
            finally:store.db.close()

    def test_manual_billing_restored_for_returning_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=collector.Store(tmp)
            try:
                base={'id':'codex','accountScope':'a','daily':[],'status':'ready'}
                store.persist(base);store.set_subscription('codex','2026-12-01','renewal');store.persist(dict(base,accountScope='b'));self.assertNotIn('codex',store.settings())
                store.persist(base);self.assertEqual(store.settings()['codex']['date'],'2026-12-01')
            finally:store.db.close()
