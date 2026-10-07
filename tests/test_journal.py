import concurrent.futures
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from journal import Journal, command_shape, MAX_INPUT
from analytics import report, compare
import instrumentation
from mcp_server import dispatch
from scripts.hook_bridge import receive

def held_schema_initialization(state,entered,release):
    import journal
    connect=journal.sqlite3.connect
    def delayed(*args,**kwargs):
        entered.set()
        if not release.wait(5):raise TimeoutError('test_release')
        return connect(*args,**kwargs)
    with patch('journal.sqlite3.connect',side_effect=delayed):
        j=Journal(state);j.close()

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name)/'state';self.j=Journal(self.state);self.clock=time.time()-100
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def event(self,event,call='c',session='s',turn='t',tool='Bash',args=None,at=None,**extra):
        raw={'hook_event_name':event,'session_id':session,'turn_id':turn,'cwd':self.tmp.name,'tool_use_id':call,'tool_name':tool,'tool_input':args or {'command':'git status'},'timestamp':self.clock if at is None else at};raw.update(extra)
        return self.j.record('codex',raw)
    def pair(self,call='c',session='s',turn='t',tool='Bash',args=None,at=None,failed=False):
        at=self.clock if at is None else at
        self.event('PreToolUse',call,session,turn,tool,args,at)
        self.event('PostToolUse',call,session,turn,tool,args,at+1,tool_response={'exit_code':1 if failed else 0})
    def test_invalid_event_timestamp_rejected(self):
        with self.assertRaises(ValueError):self.event('PreToolUse',at=1)
        with self.assertRaises(ValueError):self.event('PreToolUse',at='bad')
    def test_read_content_exit_marker_not_failure(self):
        self.event('PreToolUse',tool='Read');self.event('PostToolUse',tool='Read',tool_response={'content':[{'text':'code example: "exit_code": 1'}]})
        self.assertEqual(self.j.calls()[0]['outcome'],'success')
    def test_retention_cap_and_live_boundary_preserved(self):
        self.event('UserPromptSubmit');self.pair()
        self.j.prune();self.assertEqual(self.j.db.execute('SELECT count(*) FROM live_turn').fetchone()[0],1)
        with patch('journal.MAX_EVENTS',1):self.j.prune()
        self.assertEqual(self.j.stats()['events'],1)
    def test_pair_duration_and_exit(self):
        self.pair();c=self.j.calls()[0];self.assertTrue(c['paired']);self.assertEqual(c['durationMs'],1000);self.assertEqual(c['outcome'],'success');self.assertEqual(c['durationSource'],'hook-wall')
    def test_duplicate_delivery(self):
        self.pair();self.pair();self.assertEqual(self.j.stats()['events'],2);self.assertEqual(len(self.j.calls()),1)
    def test_finish_before_start(self):
        self.event('PostToolUse',at=self.clock+2,tool_response={'exit_code':0});self.event('PreToolUse');self.assertEqual(self.j.calls()[0]['durationMs'],2000)
    def test_incomplete_pair_not_success(self):
        self.event('PreToolUse');self.assertEqual(self.j.calls()[0]['outcome'],'pending');self.assertFalse(self.j.calls()[0]['paired'])
    def test_shell_running_process_unknown(self):
        self.event('PreToolUse');self.event('PostToolUse',tool_response={'session_id':42});self.assertEqual(self.j.calls()[0]['outcome'],'unknown')
    def test_failure_not_hidden(self):
        self.event('PreToolUse');self.event('PostToolUseFailure',error='private error');self.assertEqual(self.j.calls()[0]['outcome'],'failed')
    def test_error_flag_wins_over_zero_exit(self):
        self.event('PreToolUse');self.event('PostToolUse',tool_response={'isError':True,'exit_code':0})
        self.assertEqual(self.j.calls()[0]['outcome'],'failed')
    def test_native_duration_preferred(self):
        self.event('PreToolUse');self.event('PostToolUse',durationMs=23,tool_response={'exit_code':0});c=self.j.calls()[0];self.assertEqual(c['durationMs'],23);self.assertEqual(c['durationSource'],'native')
    def test_negative_duration_unknown(self):
        self.event('PreToolUse',at=self.clock+1);self.event('PostToolUse',at=self.clock);self.assertIsNone(self.j.calls()[0]['durationMs'])
    def test_payload_privacy(self):
        secret='SENTINEL_Confidential_123456789';self.pair(args={'command':'cat /private/'+secret},session=secret,turn=secret)
        self.event('UserPromptSubmit',prompt=secret,transcript_path='/private/'+secret)
        data=json.dumps(report(self.j));self.assertNotIn(secret,data)
        for row in self.j.db.execute('SELECT * FROM observation'):self.assertNotIn(secret,str(tuple(row)))
    def test_no_raw_code_or_flags_in_template(self):
        for cmd in ['python -c "confidential_code()"','cat secret-file','rg password --token=secret','echo hello; cat secret','node $PRIVATE']:
            shape=command_shape(cmd)[1];self.assertNotIn('confidential',shape);self.assertNotIn('secret',shape);self.assertNotIn('PRIVATE',shape)
    def test_command_category_conservative(self):
        self.assertEqual(command_shape('echo test')[0],'shell');self.assertEqual(command_shape('python -m unittest discover')[0],'test');self.assertEqual(command_shape('git status && pytest')[0],'shell')
    def test_sequence_three_turns(self):
        for n in range(3):
            for i,(tool,args) in enumerate([('Read',{'path':'x'}),('Edit',{'path':'x'}),('Bash',{'command':'pytest'})]):self.pair(str(n)+str(i),turn=str(n),tool=tool,args=args,at=self.clock+n*10+i*2)
        f=[f for f in report(self.j)['findings'] if f['kind']=='sequence'];self.assertEqual(len(f),1);self.assertEqual(f[0]['sequence'],['read','edit','test']);self.assertEqual(f[0]['occurrences'],3);self.assertIsNone(f[0]['measuredTokenSavings'])
    def test_parallel_calls_not_sequence(self):
        for n in range(3):
            self.pair(str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*5)
            self.pair(str(n)+'b',turn=str(n),tool='Edit',at=self.clock+n*5+.1)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_failure_breaks_sequence(self):
        for n in range(3):
            self.pair(str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*10)
            self.pair(str(n)+'bad',turn=str(n),at=self.clock+n*10+2,failed=True)
            self.pair(str(n)+'b',turn=str(n),tool='Edit',at=self.clock+n*10+4)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_invalid_timeline_not_sequence(self):
        for n in range(3):
            self.event('PreToolUse',str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*10+1)
            self.event('PostToolUse',str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*10)
            self.pair(str(n)+'b',turn=str(n),tool='Edit',at=self.clock+n*10+2)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_unknown_turn_not_sequence(self):
        for n in range(3):
            self.pair(str(n)+'a',turn=None,tool='Read',at=self.clock+n*5)
            self.pair(str(n)+'b',turn=None,tool='Edit',at=self.clock+n*5+2)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_actor_lanes_isolated(self):
        for n in range(3):
            for event,at in [('PreToolUse',0),('PostToolUse',1)]:self.event(event,str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*5+at,agent_id='a',tool_response={'exit_code':0})
            for event,at in [('PreToolUse',2),('PostToolUse',3)]:self.event(event,str(n)+'b',turn=str(n),tool='Edit',at=self.clock+n*5+at,agent_id='b',tool_response={'exit_code':0})
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_failed_retries_recommend_fix(self):
        for n in range(3):self.pair(str(n),turn=str(n),failed=True,at=self.clock+n*2)
        f=report(self.j)['findings'][0];self.assertEqual(f['kind'],'retry');self.assertEqual(f['action'],'fix')
    def test_inventory_unknown_not_missing(self):
        for n in range(4):self.pair(str(n),turn=str(n),at=self.clock+n*2)
        self.assertEqual(report(self.j)['findings'][0]['inventoryStatus'],'inventory_unknown')
    def test_inventory_configured_not_live(self):
        self.j.import_inventory([{'provider':'codex','id':'test-skill','kind':'skill','category':'inspect','status':'configured'}])
        for n in range(4):self.pair(str(n),turn=str(n),at=self.clock+n*2)
        self.assertEqual(report(self.j)['findings'][0]['inventoryStatus'],'configured_unverified')
    def test_inventory_atomic_invalid(self):
        entry={'provider':'codex','id':'skill','kind':'skill','category':'test','status':'configured'};self.j.import_inventory([entry])
        with self.assertRaises(ValueError):self.j.import_inventory([dict(entry,id='bad name')])
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM inventory').fetchone()[0],1)
    def test_inventory_timestamp_preserved(self):
        self.j.import_inventory([{'provider':'glm','id':'skill','kind':'skill','category':'test','status':'configured','observed':123}]);self.assertEqual(self.j.db.execute('SELECT observed FROM inventory').fetchone()[0],123)
    def test_usage_requires_native_values(self):
        with self.assertRaises(ValueError):self.j.usage('codex','s','t',{})
        with self.assertRaises(ValueError):self.j.usage('codex','s','t',{'input':2,'cached_input':3})
        self.pair();self.j.usage('codex','s','t',{'input':10,'cached_input':2,'output':4});r=report(self.j);self.assertEqual(r['sessions'][0]['reportedInputTokens'],10)
    def test_missing_token_component_stays_unknown(self):
        self.pair();self.j.usage('codex','s','t',{'output':4})
        s=report(self.j)['sessions'][0]
        self.assertIsNone(s['reportedInputTokens']);self.assertEqual(s['reportedOutputTokens'],4)
    def test_usage_same_turn_multiple_sources_not_added(self):
        self.pair()
        for source in ['native-turn','import']:self.j.usage('codex','s','t',{'input':10,'output':4},source)
        s=report(self.j)['sessions'][0]
        self.assertEqual(s['reportedInputTokens'],10);self.assertEqual(s['usageTurns'],1)
    def test_usage_conflicting_sources_unknown(self):
        self.pair();self.j.usage('codex','s','t',{'input':10,'output':4});self.j.usage('codex','s','t',{'input':12,'output':4},'import')
        s=report(self.j)['sessions'][0]
        self.assertIsNone(s['reportedInputTokens']);self.assertEqual(s['reportedOutputTokens'],4)
    def test_pending_call_breaks_sequence(self):
        for n in range(3):
            self.pair(str(n)+'a',turn=str(n),tool='Read',at=self.clock+n*10)
            self.event('PreToolUse',str(n)+'pending',turn=str(n),at=self.clock+n*10+2)
            self.pair(str(n)+'b',turn=str(n),tool='Edit',at=self.clock+n*10+4)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_lifecycle_only_is_not_tool_receiving(self):
        self.event('SessionStart')
        c=report(self.j,['codex'])['coverage'][0]
        self.assertEqual(c['state'],'lifecycle-only');self.assertEqual(c['pairedCalls'],0)
    def test_comparison_quality_not_ignored(self):
        for v in ['before','after']:
            for n in range(3):
                sid=v+str(n);self.pair(session=sid);hashed=self.j.digest('session',['codex',sid]);self.j.annotate(hashed,'task', 'accepted' if v=='before' else 'failed',v)
        c=compare(self.j,'task','before','after');self.assertEqual(c['confidence'],'observational');self.assertEqual(c['groups']['after']['failedOrRework'],3);self.assertIsNone(c['tokenSavings']);self.assertFalse(c['causalClaim'])
    def test_bad_key_not_overwritten(self):
        p=self.state/'Secrets.json';d=json.loads(p.read_text());d['journalHmacKey']='invalid';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):Journal(self.state)
        self.assertEqual(json.loads(p.read_text())['journalHmacKey'],'invalid')
    def test_concurrent_first_processes_same_key(self):
        state=Path(self.tmp.name)/'concurrent';code='from journal import Journal;import sys;j=Journal(sys.argv[1]);print(j.digest("x","y"));j.close()'
        def run(_):return subprocess.check_output([sys.executable,'-c',code,str(state)],text=True).strip()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:values=list(pool.map(run,range(4)))
        self.assertEqual(len(set(values)),1)
    def test_key_lock_bytes_unchanged_across_reopening(self):
        lock=self.state/'.journal-key.lock'
        self.assertEqual(lock.read_bytes(),b'')
        for content in (b'',b'legacy-marker'):
            lock.write_bytes(content)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                def reopen(_):
                    j=Journal(self.state)
                    try:return j.digest('test','same-key')
                    finally:j.close()
                values=list(pool.map(reopen,range(4)))
            self.assertEqual(len(set(values)),1)
            self.assertEqual(lock.read_bytes(),content)
    def test_key_lock_stays_held_through_schema_initialization(self):
        state=Path(self.tmp.name)/'initializing'
        ctx=multiprocessing.get_context('spawn');entered=ctx.Event();release=ctx.Event()
        worker=ctx.Process(target=held_schema_initialization,args=(str(state),entered,release));worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with (state/'.journal-key.lock').open('r+b') as lock:
                if os.name=='nt':
                    import msvcrt
                    with self.assertRaises(OSError):msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    with self.assertRaises(BlockingIOError):fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:
            release.set();worker.join(8)
            if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,0)
        self.assertEqual((state/'.journal-key.lock').read_bytes(),b'')
    def test_silent_fail_open(self):
        with patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertFalse(receive('codex',self.state,io.BytesIO(b'invalid')));self.assertFalse(receive('codex',self.state,io.BytesIO(b'x'*(MAX_INPUT+1))));self.assertEqual(out.getvalue(),'')
    def test_cli_hook_silent(self):
        r=subprocess.run([sys.executable,'collector.py','--state',str(self.state),'hook','--provider','codex'],input=b'not JSON',capture_output=True);self.assertEqual(r.returncode,0);self.assertEqual(r.stdout,b'');self.assertEqual(r.stderr,b'')
    def test_mcp_only_read_tools(self):
        self.assertEqual({t['name'] for t in dispatch({'method':'tools/list'},self.state)['tools']},{'pulse_report','pulse_session','pulse_evidence','pulse_compare','pulse_review_pack','pulse_settings'})
        with self.assertRaises(ValueError):dispatch({'method':'tools/call','params':{'name':'execute','arguments':{'command':'x'}}},self.state)
        with self.assertRaises(ValueError):dispatch({'method':'tools/call','params':{'name':'pulse_session','arguments':{'sessionId':'../private'}}},self.state)
    def test_mcp_malformed_no_old_id_reuse(self):
        r=subprocess.run([sys.executable,'collector.py','--state',str(self.state),'mcp'],input=b'{"id":1,"method":"ping"}\nBAD\n{"id":2,"method":"tools/list"}\n',capture_output=True)
        rows=[json.loads(x) for x in r.stdout.splitlines()];self.assertEqual([x['id'] for x in rows],[1,2])
    def test_hook_configuration_preserves_and_idempotent(self):
        for provider in ['codex','glm','claude']:
            path=instrumentation.native_path(provider,self.tmp.name);path.parent.mkdir(parents=True,exist_ok=True)
            existing={'type':'command','command':'existing-audit'}
            hookmap={'PreToolUse':[{'matcher':'Bash','hooks':[existing]}]}
            original={'privateCredential':'sentinel','hooks':{'enabled':True,'events':hookmap} if provider=='glm' else hookmap}
            path.write_text(json.dumps(original))
            instrumentation.configure_hooks(provider,self.state,home=self.tmp.name);instrumentation.configure_hooks(provider,self.state,home=self.tmp.name)
            d=json.loads(path.read_text());mapping=d['hooks']['events'] if provider=='glm' else d['hooks'];self.assertEqual(len(mapping['PreToolUse']),2);self.assertEqual(d['privateCredential'],'sentinel')
            instrumentation.configure_hooks(provider,self.state,False,home=self.tmp.name);self.assertEqual(json.loads(path.read_text()),original)
    def test_frozen_hook_idempotent(self):
        for provider in ['codex','glm']:
            with patch.object(instrumentation,'command_argv',return_value=['/opt/pulse-collector','--state',str(self.state),'hook','--provider',provider]):
                instrumentation.configure_hooks(provider,self.state,home=self.tmp.name);instrumentation.configure_hooks(provider,self.state,home=self.tmp.name)
                path=instrumentation.native_path(provider,self.tmp.name);d=json.loads(path.read_text());m=d['hooks']['events'] if provider=='glm' else d['hooks'];self.assertEqual(len(m['PreToolUse']),1)
                instrumentation.configure_hooks(provider,self.state,False,home=self.tmp.name);d=json.loads(path.read_text());m=d['hooks'].get('events',{}) if provider=='glm' else d['hooks'];self.assertNotIn('PreToolUse',m)
    def test_inventory_scan_never_reads_skill(self):
        root=Path(self.tmp.name)/'skills';(root/'test-check').mkdir(parents=True);(root/'test-check/SKILL.md').write_text('private instructions')
        rows=instrumentation.scan_inventory('codex',[root]);self.assertEqual(rows[0]['status'],'configured');self.assertNotIn('private',json.dumps(rows))

if __name__=='__main__':unittest.main()
