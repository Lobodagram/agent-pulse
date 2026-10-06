#!/usr/bin/env python3
"""Render this app's invented model timeline, never a live account screen."""
from pathlib import Path
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile

binary=Path(sys.argv[1]).resolve()
destination=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
if destination:destination.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);bundle=root/'AgentPulseModels.app'
    shutil.copytree(binary.parents[2],bundle)
    info=bundle/'Contents/Info.plist';values=plistlib.loads(info.read_bytes())
    values['CFBundleIdentifier']='app.agentpulse.modelsmoke';info.write_bytes(plistlib.dumps(values))
    subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,capture_output=True)
    for language in ('en','ru'):
        output=root/('models-'+language+'.png')
        subprocess.run([str(bundle/'Contents/MacOS/AgentPulse'),'--fixture',str(Path('examples/demo.json').resolve()),
                        '--view','analysis-small','--tab','sessions','--model-demo','--language',language,'--snapshot',str(output)],
                       check=True,capture_output=True,timeout=20)
        r=json.loads(output.with_suffix('.png.json').read_text())
        assert r['fixtureMode'] and r['capturedSize']==[620,520] and output.stat().st_size>100
        if destination:
            shutil.copy2(output,destination/output.name)
            shutil.copy2(output.with_suffix('.png.json'),destination/(output.name+'.json'))
print('PASS: own EN/RU model-history fixture renders at minimum analytics size; visual review still required')
