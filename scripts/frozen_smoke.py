#!/usr/bin/env python3
"""Check delivered helper bytes with invented events, without accounts/models."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

exe=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    base=[str(exe),'--state',tmp]
    for event in ['PreToolUse','PostToolUse']:
        raw={'hook_event_name':event,'session_id':'frozen-demo','turn_id':'demo-turn','tool_use_id':'one','tool_name':'Bash','tool_input':{'command':'python -m unittest discover'},'tool_response':{'exit_code':0}}
        r=subprocess.run(base+['hook','--provider','codex'],input=json.dumps(raw).encode(),capture_output=True,timeout=2,check=True)
        assert not r.stdout and not r.stderr,'hook must stay silent'
    r=subprocess.run(base+['journal'],capture_output=True,timeout=20,check=True)
    report=json.loads(r.stdout);assert report['calls']==1 and report['recentCalls'][0]['paired'] and report['recentCalls'][0]['outcome']=='success'
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'pulse_report','arguments':{}}}]
    r=subprocess.run(base+['mcp'],input=('\n'.join(json.dumps(x) for x in requests)+'\n').encode(),capture_output=True,timeout=20,check=True)
    responses=[json.loads(x) for x in r.stdout.splitlines()]
    assert responses[0]['result']['serverInfo']['version']=='0.4.1'
    assert json.loads(responses[1]['result']['content'][0]['text'])['calls']==1
print(json.dumps({'frozenHookJournalMcp':'passed','modelsCalled':0,'syntheticDataOnly':True}))
