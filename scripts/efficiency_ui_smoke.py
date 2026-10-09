#!/usr/bin/env python3
"""Own-window synthetic usefulness renders; never writes reviews to live state."""
import copy
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

binary=Path(sys.argv[1]).resolve();destination=Path(sys.argv[2]).resolve()
destination.mkdir(parents=True,exist_ok=True)
demo=json.loads(Path('examples/demo.json').read_text())
card={'provider':'codex','assetId':'demo-release-helper','version':'1.0.0','kind':'skill','findingId':'',
      'tasks':6,'accepted':4,'reviewed':6,'usageCompleteTasks':6,'nativeUses':0,'nativeIdentityUses':0,
      'declaredUses':6,'observedCalls':12,'knownResults':10,'tokensPerAccepted':1800,
      'cacheHitRate':.6,'medianElapsedMs':12000,'elapsedTasks':6,'modelRequests':12}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);bundle=root/'AgentPulseEfficiency.app'
    shutil.copytree(binary.parents[2],bundle)
    info=bundle/'Contents/Info.plist';values=plistlib.loads(info.read_bytes());values['CFBundleIdentifier']='app.agentpulse.efficiencysmoke'
    info.write_bytes(plistlib.dumps(values));subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,capture_output=True)
    count=0
    for state in ('empty','partial','populated'):
        fixture=copy.deepcopy(demo);row=copy.deepcopy(card)
        if state=='partial':row.update(usageCompleteTasks=0,tokensPerAccepted=None,cacheHitRate=None,modelRequests=None)
        fixture['analytics']['efficiency']={'assets':[] if state=='empty' else [row],'totalTasks':0 if state=='empty' else 6,'tasksTruncated':False}
        fixture['analytics']['quality']={'outcomeSources':{'exit-not-reported':2,'structured-exit':10}}
        path=root/(state+'.json');path.write_text(json.dumps(fixture))
        for language in ('en','ru'):
            for mode,size in [('analysis-small',[620,520]),('analysis-large',[900,700])]:
                output=destination/f'{state}-{mode}-{language}.png'
                subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(path),'--view',mode,
                                '--tab','capabilities','--language',language,'--snapshot',str(output)],check=True,capture_output=True,timeout=20)
                receipt=json.loads(output.with_suffix('.png.json').read_text())
                assert receipt['fixtureMode'] and receipt['capturedSize']==size
                count+=1
    for tab in ('capabilities','sessions','compare'):
        for language in ('en','ru'):
            output=destination/f'form-{tab}-{language}.png'
            subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(root/'empty.json'),'--view','analysis-small',
                            '--tab',tab,'--efficiency-demo','--language',language,'--snapshot',str(output)]+(['--session-demo'] if tab=='sessions' else []),check=True,capture_output=True,timeout=20)
            assert json.loads(output.with_suffix('.png.json').read_text())['fixtureMode'];count+=1
    (destination/'ui-checks.json').write_text(json.dumps({'syntheticOnly':True,'modelsCalled':0,'liveStateWritten':False,'renders':count,'visualInspectionRequired':True},indent=2))
print(json.dumps({'ownWindowRenders':count,'syntheticOnly':True}))
