#!/usr/bin/env python3
"""Generate deterministic invented evidence; never reads accounts or native logs."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from journal import Journal
from analytics import report

def demo():
    epoch=1801396800.0
    with tempfile.TemporaryDirectory() as tmp, patch('time.time',return_value=epoch):
        j=Journal(tmp)
        try:
            for provider in ['codex','glm']:
                j.import_inventory([dict(r) for r in j.db.execute('SELECT * FROM inventory')]+[{'provider':provider,'id':'verify-module','kind':'skill','category':'test','status':'configured','locator':'/invented/verify-module/SKILL.md'},{'provider':provider,'id':'local-checks','kind':'mcp','category':'test','status':'configured'}])
                for n in range(3):
                    for i,(tool,args) in enumerate([('Read',{'path':'/invented/verify-module/SKILL.md'}),('Edit',{'path':'module.py'}),('Bash',{'command':'python -m unittest discover'}),('Skill',{'skill':'verify-module'}),('mcp__local-checks__verify',{})]):
                        at=epoch-240+n*30+i*4
                        for event,dt in [('PreToolUse',0),('PostToolUse',1)]:
                            raw={'hook_event_name':event,'session_id':provider+str(n),'turn_id':str(n),'tool_use_id':str(i),'tool_name':tool,'tool_input':args,'cwd':'/invented/demo','timestamp':at+dt,'tool_response':{'exit_code':0},'model':'demo-model'}
                            j.record(provider,raw)
                    sid=j.digest('session',[provider,provider+str(n)]);j.annotate(sid,'verify-module','accepted','before')
            for n in range(3):
                for event,dt in [('PreToolUse',0),('PostToolUse',1)]:
                    j.record('glm',{'hook_event_name':event,'session_id':'retry-demo','turn_id':str(n),'tool_use_id':str(n),'tool_name':'Bash','tool_input':{'command':'npm run build'},'cwd':'/invented/demo','timestamp':epoch-30+n*3+dt,'tool_response':{'exit_code':1}})
            return report(j,['codex','glm'])
        finally:j.close()

if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'examples/demo.json';raw=json.loads(path.read_text());raw['analytics']=demo()
    for p in raw['providers']:
        if p.get('quotas'):p['quotaObservedAt']=raw['generatedAt']
    path.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
