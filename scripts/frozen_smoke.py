#!/usr/bin/env python3
"""Check delivered helper bytes with invented events, without accounts/models."""
import json
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pulse_version import __version__
exe=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    base=[str(exe),'--state',tmp]
    start=time.time()-2
    spec={'runId':'a'*32,'provider':'codex','operation':'workflow-check','version':__version__,'startedAt':start,'status':'started'}
    for value in [spec,dict(spec,status='success',endedAt=start+1,gates={'unit-tests':'passed'})]:
        r=subprocess.run(base+['journal','--action','check','--metadata',json.dumps(value)],capture_output=True,timeout=5,check=True)
        assert json.loads(r.stdout)['saved'] and not r.stderr
    r=subprocess.run(base+['journal','--action','checks'],capture_output=True,timeout=5,check=True)
    checks=json.loads(r.stdout);assert checks['runs']==checks['knownResults']==checks['startsObserved']==1 and checks['nativeOutcomesChanged']==0
    r=subprocess.run(base+['journal','--action','health'],capture_output=True,timeout=5,check=True)
    health=json.loads(r.stdout);assert health['integrity']=='ok' and health['analysisEventLimit']==100000
    target=Path(tmp)/'backup'/'journal.sqlite'
    r=subprocess.run(base+['journal','--action','backup','--file',str(target)],capture_output=True,timeout=10,check=True)
    assert json.loads(r.stdout)['includesCredentials'] is False and target.exists()
    r=subprocess.run(base+['journal','--action','backup','--file',str(target)],capture_output=True,timeout=5)
    assert r.returncode==1
print(json.dumps({'explicitReceiptsStorageAndExclusiveBackup':'passed'}))
with tempfile.TemporaryDirectory() as tmp:
    base=[str(exe),'--state',tmp]
    for event in ['PreToolUse','PostToolUse']:
        raw={'hook_event_name':event,'session_id':'frozen-demo','turn_id':'demo-turn','tool_use_id':'one','tool_name':'Bash','tool_input':{'command':'python -m unittest discover'},'tool_response':{'exit_code':0},'model':'demo-model'}
        r=subprocess.run(base+['hook','--provider','codex'],input=json.dumps(raw).encode(),capture_output=True,timeout=2,check=True)
        assert not r.stdout and not r.stderr,'hook must stay silent'
    r=subprocess.run(base+['journal'],capture_output=True,timeout=20,check=True)
    report=json.loads(r.stdout);assert report['calls']==1 and report['recentCalls'][0]['paired'] and report['recentCalls'][0]['outcome']=='success'
    assert report['recentCalls'][0]['model']=='demo-model' and report['modelHistory']['knownModelCalls']==1
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'pulse_report','arguments':{}}},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'pulse_review_pack','arguments':{'language':'ru'}}},{'jsonrpc':'2.0','id':4,'method':'tools/list','params':{}}]
    r=subprocess.run(base+['mcp'],input=('\n'.join(json.dumps(x) for x in requests)+'\n').encode(),capture_output=True,timeout=20,check=True)
    responses=[json.loads(x) for x in r.stdout.splitlines()]
    assert responses[0]['result']['serverInfo']['version']==__version__
    assert json.loads(responses[1]['result']['content'][0]['text'])['calls']==1
    assert 'пакет проверки' in json.loads(responses[2]['result']['content'][0]['text'])['markdown']
    assert {t['name'] for t in responses[3]['result']['tools']}=={'pulse_report','pulse_session','pulse_evidence','pulse_compare','pulse_review_pack','pulse_settings','pulse_efficiency','pulse_compare_tasks','pulse_collection_health','pulse_check_receipts'}
    # Exercise the actual packaged control path with a different process holding
    # its lock. No test events/settings enter a real user's state.
    busy={'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'pulse_configure','arguments':{'changes':{'metricMode':'today'}}}}
    with (Path(tmp)/'.config.lock').open('w+b') as lock:
        lock.write(b'0');lock.flush();lock.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        r=subprocess.run(base+['mcp','--allow-control'],input=(json.dumps(busy)+'\n'+json.dumps({'jsonrpc':'2.0','id':6,'method':'ping'})+'\n').encode(),capture_output=True,timeout=10,check=True)
        assert not r.stderr
        responses=[json.loads(x) for x in r.stdout.splitlines()]
        assert responses[0]=={'jsonrpc':'2.0','id':5,'result':{'content':[{'type':'text','text':'{"error":"config_busy","retryable":true}'}],'isError':True}}
        assert responses[1]=={'jsonrpc':'2.0','id':6,'result':{}}
        assert not (Path(tmp)/'config.json').exists()
    r=subprocess.run(base+['mcp','--allow-control'],input=(json.dumps(busy)+'\n').encode(),capture_output=True,timeout=10,check=True)
    assert not r.stderr
    assert not json.loads(r.stdout)['result']['isError']
    assert json.loads((Path(tmp)/'config.json').read_text())['metricMode']=='today'
    for call,response in [('invalid-result',{'exit_code':0,'content':[{'type':'text','text':json.dumps({'output':'PRIVATE_RESULT_CANARY','wall_time_seconds':1,'exit_code':True})}]}),
                          ('bounded-result',{'exit_code':0,'content':[{'type':'text','text':'demo'}]*11})]:
        for event in ['PreToolUse','PostToolUse']:
            raw={'hook_event_name':event,'session_id':'frozen-demo','turn_id':'demo-turn','tool_use_id':call,'tool_name':'Bash','tool_input':{'command':'git status'},'tool_response':response}
            r=subprocess.run(base+['hook','--provider','codex'],input=json.dumps(raw).encode(),capture_output=True,timeout=2,check=True)
            assert not r.stdout and not r.stderr
    r=subprocess.run(base+['journal'],capture_output=True,timeout=20,check=True)
    report=json.loads(r.stdout)
    assert report['calls']==3
    assert sorted(c['outcome'] for c in report['recentCalls'])==['success','unknown','unknown']
    assert {c['outcomeSource'] for c in report['recentCalls']}=={'structured-exit','conflicting-or-invalid-exit','result-limit-exceeded'}
    assert 'PRIVATE_RESULT_CANARY' not in r.stdout.decode()
    efficiency_requests=[
        ('pulse_register_asset',{'provider':'codex','assetId':'demo-release-helper','version':'1.0.0','kind':'skill'}),
        ('pulse_record_usage',{'provider':'codex','sessionId':'frozen-demo','turnId':'demo-turn','input':100,'cached_input':50,'output':20,'modelRequests':1,'complete':True}),
        ('pulse_record_task',{'provider':'codex','taskId':'fixture-task','label':'release-check','variant':'after','criterion':'checks-v1','outcome':'accepted','callIds':[c['id'] for c in report['recentCalls']],'assetId':'demo-release-helper','version':'1.0.0','applied':True}),
        ('pulse_efficiency',{})]
    requests=[{'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':name,'arguments':args}} for i,(name,args) in enumerate(efficiency_requests)]
    result=subprocess.run(base+['mcp','--allow-control'],input=('\n'.join(json.dumps(x) for x in requests)+'\n').encode(),capture_output=True,timeout=20,check=True)
    replies=[json.loads(x) for x in result.stdout.splitlines()]
    assert len(replies)==4 and all('result' in x and not x['result']['isError'] for x in replies)
    card=json.loads(replies[-1]['result']['content'][0]['text'])['assets'][0]
    assert card['tokensPerAccepted']==120 and card['cacheHitRate']==.5 and card['modelRequests']==1
    assert card['subscriptionSavings'] is None and not card['causalClaim']
    parallel=[str(exe),'--state',str(Path(tmp)/'parallel-first-start')]
    def first_pair(index):
        for event in ('PreToolUse','PostToolUse'):
            raw={'hook_event_name':event,'session_id':'parallel-demo','turn_id':'demo',
                 'tool_use_id':str(index),'tool_name':'Bash','tool_input':{'command':'git status'},
                 'tool_response':{'exit_code':0}}
            result=subprocess.run(parallel+['hook','--provider','codex'],input=json.dumps(raw).encode(),
                                  capture_output=True,timeout=2,check=True)
            assert not result.stdout and not result.stderr
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(first_pair,range(4)))
    result=subprocess.run(parallel+['journal'],capture_output=True,timeout=20,check=True)
    concurrent_report=json.loads(result.stdout)
    assert concurrent_report['calls']==4 and all(c['paired'] and c['outcome']=='success' for c in concurrent_report['recentCalls'])
    assert (Path(tmp)/'parallel-first-start'/'.journal-key.lock').read_bytes()==b''
print(json.dumps({'frozenHookJournalMcp':'passed','versionTaskUsageRoundtrip':'passed','mcpConfigBusyRetry':'passed','conservativeResultMetadata':'passed','concurrentFirstHooks':'passed','modelsCalled':0,'syntheticDataOnly':True}))

# Kimi Code native hook schema and inverse removal in throwaway native home only.
with tempfile.TemporaryDirectory() as tmp:
    state=Path(tmp)/'pulse';home=Path(tmp)/'native-home'
    config=home/'.kimi-code/config.toml';config.parent.mkdir(parents=True)
    original=b'# existing user setting\n[providers.custom]\napi_key="PRIVATE_NATIVE_CANARY"'
    config.write_bytes(original)
    base=[sys.argv[1],'--state',str(state)]
    for action in ['install','install']:
        r=subprocess.run(base+['hooks','--provider','kimi','--action',action,'--observer-home',str(home)],capture_output=True,timeout=5,check=True)
        assert b'PRIVATE' not in r.stdout and not r.stderr
    import tomllib
    hooks=tomllib.loads(config.read_text())['hooks'];assert len(hooks)==8
    for event in ['PreToolUse','PostToolUse']:
        raw={'hook_event_name':event,'session_id':'kimi-fixture','turn_id':7,'tool_call_id':'native-call','tool_name':'Shell','tool_input':{'command':'git status'},'tool_output':'PRIVATE_RESULT_CANARY'}
        r=subprocess.run(base+['hook','--provider','kimi'],input=json.dumps(raw).encode(),capture_output=True,timeout=2,check=True)
        assert not r.stdout and not r.stderr
    r=subprocess.run(base+['journal'],capture_output=True,timeout=20,check=True)
    report=json.loads(r.stdout);assert report['calls']==1 and report['recentCalls'][0]['outcome']=='unknown'
    assert b'PRIVATE' not in r.stdout
    r=subprocess.run(base+['hooks','--provider','kimi','--action','remove','--observer-home',str(home)],capture_output=True,timeout=5,check=True)
    assert config.read_bytes()==original and b'PRIVATE' not in r.stdout
print(json.dumps({'kimiNativeSchemaAndInverse':'passed'}))
