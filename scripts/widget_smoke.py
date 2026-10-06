#!/usr/bin/env python3
"""Own-window Mac fixture checks; no live accounts, peers or global screen capture."""
from pathlib import Path
import json,subprocess,sys,tempfile,shutil,plistlib
binary=Path(sys.argv[1]).resolve();fixture=Path('examples/demo.json').resolve()
destination=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
if destination:destination.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    demo=Path(tmp)/'demo.json';shutil.copyfile(fixture,demo)
    bundle=Path(tmp)/'AgentPulseFixture.app';shutil.copytree(binary.parents[2],bundle)
    info=bundle/'Contents/Info.plist';settings=plistlib.loads(info.read_bytes());settings['CFBundleIdentifier']='app.agentpulse.widgetsmoke';info.write_bytes(plistlib.dumps(settings))
    subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for mode,width,height in [('compact',288,216),('expanded',288,344),('resize-check',348,261),('menu-popover',288,216),('menu-bar',288,216),('two-quotas',288,216),('expanded-two-quotas',288,344),('pending',288,216),('compact-en',288,216)]:
        out=Path(tmp)/(mode+'.png')
        data=json.loads(fixture.read_text())
        if mode in ('two-quotas','expanded-two-quotas'):data['providers'][1]['quotas']=data['providers'][0]['quotas']
        if mode=='pending':data['providers'][0].update(todayTokens=None,todayTokenStatus='account-day-pending')
        demo.write_text(json.dumps(data))
        view='expanded' if mode=='expanded-two-quotas' else mode if mode not in ('two-quotas','pending','compact-en') else 'compact'
        args=['open','-n','-W',str(bundle),'--args','--fixture',str(demo),'--language','en' if mode=='compact-en' else 'ru','--scale','.8','--view',view,'--snapshot',str(out)]
        if mode.startswith('menu'):args.append('--menu-only')
        subprocess.run(args,check=True,timeout=20)
        r=json.loads(out.with_suffix('.png.json').read_text())
        assert abs(r['panelWidth']-width)<.01 and abs(r['panelHeight']-height)<.01,r
        assert r['fixtureMode'] and out.stat().st_size>100,r
        if mode=='menu-popover':assert r['popoverShown'],r
        if mode.startswith('menu'):assert r['displayMode']=='menu' and not r['visibleBefore'] and r['menuTitle'],r
        if destination:
            shutil.copy2(out,destination/out.name);shutil.copy2(out.with_suffix('.png.json'),destination/(out.name+'.json'))
print('PASS: minimum compact/detail, resize handler, menu-only launch, actual popover and status-button rendering')
