#!/usr/bin/env python3
"""Check delivered helper bytes with invented events, without accounts/models."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pulse_version import __version__
exe=Path(sys.argv[1]).resolve()
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
    assert len(responses[3]['result']['tools'])==6
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
print(json.dumps({'frozenHookJournalMcp':'passed','mcpConfigBusyRetry':'passed','conservativeResultMetadata':'passed','modelsCalled':0,'syntheticDataOnly':True}))
