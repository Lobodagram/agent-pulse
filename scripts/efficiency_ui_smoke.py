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
      'declaredUses':4,'observedCalls':12,'knownResults':10,'tokensPerAccepted':1800,
      'cacheHitRate':.6,'medianElapsedMs':12000,'elapsedTasks':6,'modelRequests':12,
      'eligibleTasks':5,'eligibilityKnownTasks':6,'eligibilityUnknownTasks':0,'usedEligibleTasks':4,'adoptionKnownTasks':5,
      'adoptionRate':.8,'nonUseReasons':{'unavailable':1},'lifecycle':'accepted-awaiting-comparison',
      'observedCallsPerAccepted':3,'modelRequestsPerAccepted':3}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);bundle=root/'AgentPulseEfficiency.app'
    shutil.copytree(binary.parents[2],bundle)
    info=bundle/'Contents/Info.plist';values=plistlib.loads(info.read_bytes());values['CFBundleIdentifier']='app.agentpulse.efficiencysmoke'
    info.write_bytes(plistlib.dumps(values));subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,capture_output=True)
    count=0
    for state in ('empty','partial','populated'):
        fixture=copy.deepcopy(demo);row=copy.deepcopy(card)
        if state=='partial':row.update(usageCompleteTasks=0,tokensPerAccepted=None,cacheHitRate=None,modelRequests=None,
                                      eligibleTasks=5,eligibilityKnownTasks=5,eligibilityUnknownTasks=1,adoptionKnownTasks=4,adoptionRate=None,nonUseReasons={},modelRequestsPerAccepted=None)
        fixture['analytics']['efficiency']={'assets':[] if state=='empty' else [row],'totalTasks':0 if state=='empty' else 6,'tasksTruncated':False}
        fixture['analytics']['quality']={'outcomeSources':{'exit-not-reported':2,'structured-exit':10}}
        if state=='populated':
            candidate=next(f for f in fixture['analytics']['findings'] if f['provider']=='codex')
            candidate.update(reviewStatus='dismissed',reviewReason='required-check')
            fixture['analytics']['findingReviews']=[{'findingId':candidate['id'],'provider':'codex','title':candidate['title'],'titleRu':candidate['titleRu'],
                'status':'dismissed','reason':'required-check','recheckState':'not-requested','windowHours':24,'afterWindowEndsAt':fixture['generatedAt'],
                'lifecycle':'dismissed','linkedVersions':[]}]
            other=next(f for f in fixture['analytics']['findings'] if f['provider']=='codex' and f['id']!=candidate['id'])
            other.update(reviewStatus='open',reviewReason='confirmed-pattern')
            row['findingId']=other['id']
            fixture['analytics']['findingReviews'].insert(0,{'findingId':other['id'],'provider':'codex','title':other['title'],'titleRu':other['titleRu'],
                'status':'open','reason':'confirmed-pattern','recheckState':'not-requested','windowHours':24,'afterWindowEndsAt':fixture['generatedAt'],
                'lifecycle':row['lifecycle'],'linkedVersions':[{'assetId':row['assetId'],'version':row['version'],'tasks':6,'accepted':4,'declaredUses':4}]})
        path=root/(state+'.json');path.write_text(json.dumps(fixture))
        for language in ('en','ru'):
            for mode,size in [('analysis-small',[620,520]),('analysis-large',[900,700])]:
                output=destination/f'{state}-{mode}-{language}.png'
                subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(path),'--view',mode,
                                '--tab','capabilities','--language',language,'--snapshot',str(output)],check=True,capture_output=True,timeout=20)
                receipt=json.loads(output.with_suffix('.png.json').read_text())
                assert receipt['fixtureMode'] and receipt['capturedSize']==size
                count+=1
    for tab in ('capabilities','sessions','compare','workflows'):
        for language in ('en','ru'):
            output=destination/f'form-{tab}-{language}.png'
            subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(root/('populated.json' if tab in ('sessions','workflows') else 'empty.json')),'--view','analysis-small',
                            '--tab',tab,'--efficiency-demo','--language',language,'--snapshot',str(output)]+(['--session-demo','--task-assessment-demo'] if tab=='sessions' else []),check=True,capture_output=True,timeout=20)
            assert json.loads(output.with_suffix('.png.json').read_text())['fixtureMode'];count+=1
    helper=copy.deepcopy(demo)
    helper['analytics']['checkRuns']={'runs':8,'knownResults':4,'knownResultRate':.5,'pendingRuns':2,'conflicts':1,'finishWithoutStart':1,
        'operationVersionsTruncated':False,'byOperationVersion':[
            {'provider':'codex','operation':'workflow-check','version':'1.0.0','runs':6,'knownResults':4,
             'successes':3,'failures':1,'successRate':.75,'pendingRuns':1,'staleRuns':1,'conflicts':1,'finishWithoutStart':1,
             'timedRuns':3,'medianElapsedMs':1500},
            {'provider':'glm','operation':'mesh-topology','version':'2.0.0','runs':2,'knownResults':0,
             'successes':0,'failures':0,'successRate':None,'pendingRuns':1,'staleRuns':0,'conflicts':0,'finishWithoutStart':0,
             'timedRuns':0,'medianElapsedMs':None}]}
    path=root/'helpers.json';path.write_text(json.dumps(helper))
    for language in ('en','ru'):
        for mode,size in [('analysis-small',[620,520]),('analysis-large',[900,700])]:
            output=destination/f'helpers-{mode}-{language}.png'
            subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(path),'--view',mode,
                            '--tab','overview','--helper-metrics-demo','--language',language,'--snapshot',str(output)],check=True,capture_output=True,timeout=20)
            receipt=json.loads(output.with_suffix('.png.json').read_text())
            assert receipt['fixtureMode'] and receipt['capturedSize']==size;count+=1
    (destination/'ui-checks.json').write_text(json.dumps({'syntheticOnly':True,'modelsCalled':0,'liveStateWritten':False,'renders':count,'visualInspectionRequired':True},indent=2))
print(json.dumps({'ownWindowRenders':count,'syntheticOnly':True}))
