"""Golden synthetic cases. Measures bounded mechanics, never real-task semantic accuracy."""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from journal import Journal
from analytics import report

def evaluate():
    spec=json.loads((Path(__file__).resolve().parents[1]/'examples/analytics-cases.json').read_text())
    assert spec['synthetic'] is True
    results=[];tp=fp=fn=0;started=time.monotonic()
    for case in spec['cases']:
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp)
            try:
                epoch=time.time()-2000;mode=case.get('mode')
                for turn in range(case['turns']):
                    for i,(tool,command) in enumerate(case['steps']):
                        command=command[turn] if isinstance(command,list) else command
                        command=command.replace('{turn}',str(turn))
                        base=epoch+turn*20+i*2
                        if mode=='parallel':base=epoch+turn*20+i*.1
                        if mode=='outer-parallel':base=epoch+turn*20+(0 if i==0 else 2*i-1)
                        raw={'hook_event_name':'PreToolUse','session_id':'case','turn_id':None if mode=='unknown-turn' else str(turn),
                             'tool_use_id':str(turn)+'-'+str(i),'tool_name':tool,'tool_input':{'command':command} if command else {'path':'/invented/source.py'},
                             'cwd':'/invented/project','timestamp':base}
                        if mode=='actors':raw['agent_id']='actor'+str(i)
                        j.record('codex',raw)
                        if mode=='pending-barrier' and i==1:continue
                        failed=mode=='failed' or mode=='failure-barrier' and i==1
                        delta=-1 if mode=='invalid' and i==0 else 10 if mode=='outer-parallel' and i==0 else 1
                        response={'session_id':42} if mode=='running' and i==0 else {'exit_code':1 if failed else 0}
                        j.record('codex',dict(raw,hook_event_name='PostToolUse',timestamp=base+delta,tool_response=response))
                found={f['kind'] for f in report(j)['findings']};expected=set(case['expect'])
                tp+=len(found&expected);fp+=len(found-expected);fn+=len(expected-found)
                results.append({'case':case['id'],'expected':sorted(expected),'found':sorted(found),'passed':found==expected})
            finally:j.close()
    return {'syntheticOnly':True,'modelsCalled':0,'realJournalTouched':False,'cases':results,
            'truePositiveKinds':tp,'falsePositiveKinds':fp,'falseNegativeKinds':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'seconds':round(time.monotonic()-started,3),
            'scope':'14 labeled mechanics cases; not a benchmark of arbitrary code semantics or production savings'}

if __name__=='__main__':
    result=evaluate();print(json.dumps(result,indent=2))
    if not all(c['passed'] for c in result['cases']):raise SystemExit(1)
