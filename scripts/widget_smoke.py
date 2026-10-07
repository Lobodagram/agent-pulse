#!/usr/bin/env python3
"""Own-window Mac fixture checks; no live accounts, peers or global screen capture."""
from pathlib import Path
import json,subprocess,sys,tempfile,shutil,plistlib,os,signal,time
binary=Path(sys.argv[1]).resolve();fixture=Path('examples/demo.json').resolve()
destination=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
if destination:destination.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    demo=Path(tmp)/'demo.json';shutil.copyfile(fixture,demo)
    bundle=Path(tmp)/'AgentPulseFixture.app';shutil.copytree(binary.parents[2],bundle)
    info=bundle/'Contents/Info.plist';settings=plistlib.loads(info.read_bytes());settings['CFBundleIdentifier']='app.agentpulse.widgetsmoke';info.write_bytes(plistlib.dumps(settings))
    subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for mode,width,height in [('compact',288,216),('expanded',288,344),('resize-check',348,261),('menu-widget',288,216),('menu-bar',288,216),('menu-next',288,216),('menu-timer',288,216),('menu-active',288,216),('menu-fallback',288,216),('two-quotas',288,216),('expanded-two-quotas',288,344),('pending',288,216),('compact-en',288,216),('single-instance',288,216),('window-focus',288,216),('today',288,216),('today-en',288,216),('today-two-quotas',288,216),('today-pending',288,216),('glm-menu-quotas',288,216),('kimi-quotas',288,216),('kimi-menu-quotas',288,216)]:
        out=Path(tmp)/(mode+'.png')
        data=json.loads(fixture.read_text())
        if mode in ('two-quotas','expanded-two-quotas','today-two-quotas','glm-menu-quotas'):data['providers'][1]['quotas']=data['providers'][0]['quotas']
        if mode in ('kimi-quotas','kimi-menu-quotas'):
            data['providers']=[data['providers'][0]]
            data['providers'][0].update(id='kimi',name='Kimi Code',todayTokens=None,todayTokenCoverage='not-reported')
        if mode in ('pending','today-pending'):data['providers'][0].update(todayTokens=None,todayTokenStatus='account-day-pending')
        if mode in ('menu-next','menu-timer','menu-active','menu-fallback'):data['providers'][1]['quotas']=[]
        demo.write_text(json.dumps(data))
        view='menu-bar' if mode in ('menu-next','menu-timer','menu-active','menu-fallback') else 'expanded' if mode=='expanded-two-quotas' else mode if mode not in ('two-quotas','pending','compact-en','single-instance') else 'compact'
        if mode.startswith('today') or mode=='glm-menu-quotas':view='compact' if mode.startswith('today') else 'menu-bar'
        ready=Path(tmp)/(mode+'.ready')
        executable=bundle/'Contents/MacOS/AgentPulse'
        args=[str(executable),'--fixture',str(demo),'--language','en' if mode in ('compact-en','today-en') else 'ru','--scale','.8','--metric-mode','limits','--view',view,'--snapshot',str(out),'--ready-file',str(ready)]
        if mode.startswith('today'):args[args.index('--metric-mode')+1]='today'
        if mode=='glm-menu-quotas':args+=['--menu-only','--status-page','1']
        if mode=='kimi-menu-quotas':args+=['--menu-only'];args[args.index('--view')+1]='menu-bar'
        if mode=='kimi-quotas':args[args.index('--view')+1]='compact'
        if mode.startswith('menu'):args.append('--menu-only')
        # Focus/restore is a window test, independent of GPU chart rendering.
        # Set the initial tab before view construction on headless Intel runners.
        if mode=='window-focus':args+=['--tab','workflows']
        if mode=='menu-next':args+=['--status-page','1']
        if mode=='menu-timer':args.append('--rotation-check')
        if mode=='menu-active':args+=['--active-app','dev.zcode.app']
        if mode=='menu-fallback':args+=['--active-app','unknown.app','--status-page','1']
        try:
            if mode=='single-instance':
                first=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                until=time.monotonic()+10
                while not ready.exists() and first.poll() is None and time.monotonic()<until:time.sleep(.02)
                assert ready.exists(),'Fixture did not initialize'
                subprocess.run([str(executable)],check=True,timeout=10,capture_output=True,text=True)
                stdout,stderr=first.communicate(timeout=15)
                assert first.returncode==0,(mode,first.returncode,stderr[-4000:])
                assert out.with_suffix('.png.json').exists(),'First instance must finish its own fixture capture'
            else:
                result=subprocess.run(args,timeout=20,capture_output=True,text=True)
                assert result.returncode==0,(mode,result.returncode,result.stderr[-4000:])
                assert out.with_suffix('.png.json').exists(),(mode,'missing report',result.stderr[-4000:])
        finally:
            expected=(bundle/'Contents/MacOS/AgentPulse').resolve()
            for row in subprocess.check_output(['ps','-axo','pid=,comm='],text=True).splitlines():
                parts=row.strip().split(None,1)
                if len(parts)==2 and Path(parts[1]).resolve()==expected:
                    try:os.kill(int(parts[0]),signal.SIGTERM)
                    except ProcessLookupError:pass
        r=json.loads(out.with_suffix('.png.json').read_text())
        assert abs(r['panelWidth']-width)<.01 and abs(r['panelHeight']-height)<.01,r
        assert r['fixtureMode'] and out.stat().st_size>100,r
        if mode=='menu-widget':assert r['menuClickShowsPanel'] and r['visibleBefore'] and r['movable'],r
        if mode.startswith('menu'):assert r['displayMode']=='menu' and r['visibleBefore']==(mode=='menu-widget') and r['menuTitle'],r
        if mode in ('menu-next','menu-timer','menu-active','menu-fallback'):
            assert r['menuTitle'].startswith('GLM —') and '/' not in r['menuTitle'],r
            assert 'CODEX 5ч' in r['menuTooltip'] and 'GLM —' in r['menuTooltip'],r
        if mode=='menu-bar':assert r['menuTitle'].startswith('CODEX 5ч') and 'GLM' not in r['menuTitle'] and '/' not in r['menuTitle'],r
        if mode.startswith('today'):assert r['metricMode']=='today',r
        if mode=='glm-menu-quotas':assert r['menuTitle'].startswith('GLM 5ч') and '7д' in r['menuTitle'],r
        if mode=='kimi-menu-quotas':assert r['menuTitle'].startswith('KIMI 5ч') and '7д' in r['menuTitle'],r
        assert r['hidePassed'] and r['restorePassed'],r
        if mode=='window-focus':
            assert r['utilityTogglePassed'] and r['utilityRestorePassed'] and r['utilityFocusPassed'] and r['utilityPlacementPassed'],r
            assert all(r['utilityFocusChecks'].get(k) is True for k in ('readyBefore','readyAfter','widgetKey','utilityMain','hidden')),r
        if destination:
            shutil.copy2(out,destination/out.name);shutil.copy2(out.with_suffix('.png.json'),destination/(out.name+'.json'))
print('PASS: minimum compact/detail, resize handler, menu-only launch, movable menu-click widget, rotating status buttons and foreground/fallback selection')
