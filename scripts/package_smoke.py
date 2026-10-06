#!/usr/bin/env python3
"""Build/install the runtime wheel in temporary state; no native clients or model calls."""
import configparser
from email.parser import Parser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pulse_version import __version__
from scripts.public_export import export

def run(args,cwd,**kwargs):
    return subprocess.run(args,cwd=cwd,capture_output=True,check=True,timeout=90,**kwargs)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);wheels=tmp/'wheels';source=tmp/'source';export(source)
        run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(source)],tmp)
        wheel=next(wheels.glob('*.whl'))
        with zipfile.ZipFile(wheel) as z:
            names=z.namelist()
            assert not any(n.startswith(('scripts/','tests/')) for n in names)
            for name in ['hook_bridge.py','sanitizers.py','pulse_version.py']:
                assert name in names
            metadata=Parser().parsestr(z.read(next(n for n in names if n.endswith('/METADATA'))).decode())
            assert metadata['Version']==__version__ and metadata['Requires-Python']=='>=3.11'
            entry=configparser.ConfigParser();entry.read_string(z.read(next(n for n in names if n.endswith('/entry_points.txt'))).decode())
            assert entry['console_scripts']['agent-pulse']=='collector:main'
            assert entry['console_scripts']['agent-pulse-mcp']=='mcp_server:main'
            assert any(n.endswith('/LICENSE') for n in names) and any(n.endswith('/NOTICE') for n in names)
        env=tmp/'venv';run([sys.executable,'-m','venv',str(env)],tmp)
        scripts=env/('Scripts' if os.name=='nt' else 'bin')
        python=scripts/('python.exe' if os.name=='nt' else 'python')
        run([str(python),'-m','pip','install','--no-deps','--no-index',str(wheel)],tmp)
        cli=scripts/('agent-pulse.exe' if os.name=='nt' else 'agent-pulse')
        mcp=scripts/('agent-pulse-mcp.exe' if os.name=='nt' else 'agent-pulse-mcp')
        state=tmp/'state'
        run([str(cli),'catalog'],tmp)
        argv=json.loads(run([str(python),'-c',
             'import json,sys;from pathlib import Path;from instrumentation import command_argv;print(json.dumps(command_argv("codex",Path(sys.argv[1]))))',str(state)],tmp).stdout)
        raw={'hook_event_name':'PreToolUse','session_id':'wheel-demo','tool_use_id':'demo','tool_name':'Read'}
        for event in ['PreToolUse','PostToolUse']:
            raw['hook_event_name']=event;raw['tool_response']={'exit_code':0}
            result=run(argv,tmp,input=json.dumps(raw).encode());assert not result.stdout and not result.stderr
        report=json.loads(run([str(cli),'--state',str(state),'journal'],tmp).stdout)
        assert report['calls']==1 and report['recentCalls'][0]['paired']
        request=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})+'\n'
        response=json.loads(run([str(mcp),'--state',str(state)],tmp,input=request.encode()).stdout)
        assert response['result']['serverInfo']['version']==__version__
    print(json.dumps({'runtimeWheel':'passed','version':__version__,'devScriptsIncluded':False,
                      'isolatedHookAndEntryPoints':'passed','modelsCalled':0,'nativeConfigsChanged':False}))

if __name__=='__main__':main()
