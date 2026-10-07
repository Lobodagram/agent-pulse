#!/usr/bin/env python3
"""Own-window daily token chart fixtures; no live accounts or telemetry writes."""
from pathlib import Path
import json, plistlib, shutil, subprocess, sys, tempfile

binary=Path(sys.argv[1]).resolve()
destination=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
if destination:destination.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);bundle=root/'AgentPulseCharts.app'
    shutil.copytree(binary.parents[2],bundle,symlinks=True)
    info=bundle/'Contents/Info.plist';values=plistlib.loads(info.read_bytes())
    values['CFBundleIdentifier']='app.agentpulse.chartsmoke';info.write_bytes(plistlib.dumps(values))
    subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,capture_output=True)
    for name,language,mode in [('tokens-en','en','analysis'),('tokens-ru','ru','analysis-small'),('tokens-large','ru','analysis-small'),('tokens-zero','en','analysis-small'),('tokens-empty','ru','analysis-small')]:
        data=json.loads(Path('examples/demo.json').read_text(encoding='utf-8'))
        if name=='tokens-large':
            for row in data['history']:row['tokens']*=3000
        if name=='tokens-zero':
            for row in data['history']:row['tokens']=0
        if name=='tokens-empty':data['history']=[]
        fixture=root/'fixture.json';fixture.write_text(json.dumps(data),encoding='utf-8');output=root/(name+'.png')
        subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(fixture),'--view',mode,'--tab','tokens','--language',language,'--snapshot',str(output)],check=True,capture_output=True,timeout=20)
        r=json.loads(output.with_suffix('.png.json').read_text())
        assert r['fixtureMode'] and r['capturedSize']==([620,520] if mode=='analysis-small' else [760,620])
        assert output.stat().st_size>100
        if destination:
            shutil.copy2(output,destination/output.name)
            shutil.copy2(output.with_suffix('.png.json'),destination/(output.name+'.json'))
print('PASS: EN/RU daily chart, large/zero/missing counters at target sizes; visual and pointer acceptance separate')
