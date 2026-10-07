"""Reviewed native hook configuration; preserves other hooks and credentials in place."""
import json
import os
from pathlib import Path
import shlex
import sys
import tomllib
from journal import Journal, atomic_json, safe_name, PROVIDERS

NATIVE_EVENTS={'codex':['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','Stop','Interrupt','SessionEnd'],
 'glm':['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','PostToolUseFailure','Stop'],
 'claude':['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','PostToolUseFailure','Stop','SessionEnd'],
 'kimi':['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','PostToolUseFailure','Stop','Interrupt','SessionEnd']}

def command_argv(provider,state):
    if getattr(sys,'frozen',False):
        exe=Path(sys.executable)
        if exe.name.lower()=='agentpulse.exe':exe=exe.with_name('pulse-collector.exe')
        return [str(exe),'--state',str(state),'hook','--provider',provider]
    return [sys.executable,str(Path(__file__).parent/'hook_bridge.py'),'--provider',provider,'--state',str(state)]

def is_ours(h):return isinstance(h,dict) and h.get('agentPulseObserver') is True

def native_path(provider,home=None):
    if provider=='kimi':return (Path(home)/'.kimi-code' if home is not None else Path(os.environ.get('KIMI_CODE_HOME',str(Path.home()/'.kimi-code'))))/'config.toml'
    home=Path(home) if home else Path.home()
    return home/('.codex/hooks.json' if provider=='codex' else '.zcode/cli/config.json' if provider=='glm' else '.claude/settings.json')

def configure_hooks(provider,state,enable=True,home=None):
    if provider not in NATIVE_EVENTS:raise ValueError('unsupported_hook_client')
    if provider=='kimi':return configure_kimi_hooks(state,enable,home)
    # Initialize the key and DB before concurrent hook processes start.
    j=Journal(state);j.close()
    path=native_path(provider,home)
    if path.is_symlink():raise ValueError('symlink_config')
    original=path.read_bytes() if path.exists() else None
    raw=json.loads(original) if original is not None else {}
    if not isinstance(raw,dict):raise ValueError('invalid_config')
    argv=command_argv(provider,state)
    # Use an exact command marker instead of adding unknown keys to strict native schemas.
    def ours(h):
        if not isinstance(h,dict):return False
        cmd=h.get('command','');args=h.get('args',[])
        try:
            tokens=[cmd]+args if provider=='glm' and isinstance(args,list) else shlex.split(cmd, posix=os.name!='nt')
            normalized=[str(v).strip('"') for v in tokens]
            if '--provider' not in normalized:return False
            i=normalized.index('--provider')
            if i+1>=len(normalized) or normalized[i+1]!=provider:return False
            return any(Path(t).name=='hook_bridge.py' for t in normalized) or ('hook' in normalized and Path(normalized[0]).name in {'pulse-collector','pulse-collector.exe'})
        except (ValueError,TypeError):return False
    hooks=raw.setdefault('hooks',{})
    if not isinstance(hooks,dict):raise ValueError('invalid_hooks')
    mapping=hooks.setdefault('events',{}) if provider=='glm' else hooks
    if not isinstance(mapping,dict):raise ValueError('invalid_events')
    for event in NATIVE_EVENTS[provider]:
        entries=mapping.get(event,[])
        if not isinstance(entries,list):raise ValueError('invalid_hook_entries')
        retained=[]
        for entry in entries:
            if not isinstance(entry,dict) or not isinstance(entry.get('hooks'),list):raise ValueError('invalid_hook_entry')
            handlers=[h for h in entry['hooks'] if not ours(h)]
            if handlers:retained.append(dict(entry,hooks=handlers))
        if enable:
            if provider=='glm':handler={'type':'process','command':argv[0],'args':argv[1:],'enabled':True,'timeoutMs':2000}
            else:
                import subprocess
                cmd=subprocess.list2cmdline(argv) if os.name=='nt' else shlex.join(argv)
                handler={'type':'command','command':cmd,'timeout':2}
            retained.append({'hooks':[handler]})
        if retained:mapping[event]=retained
        elif event in mapping:del mapping[event]
    if provider=='glm' and enable:hooks['enabled']=True
    # No backups of the full native configuration: it could contain credentials.
    # Inverse removal touches only this observer's handlers.
    if (path.read_bytes() if path.exists() else None)!=original:raise ValueError('config_changed_retry')
    atomic_json(path,raw)
    return {'provider':provider,'configured':enable,'requiresNewSession':True,'nativeTrustReviewMayBeRequired':provider=='codex','events':NATIVE_EVENTS[provider] if enable else [],'modelCalls':0}

KIMI_BEGIN='# BEGIN Agent Pulse observer\n'
KIMI_END='# END Agent Pulse observer\n'

def configure_kimi_hooks(state,enable=True,home=None):
    """Kimi Code 2.x TOML hooks; preserve native bytes and remove only our block."""
    import subprocess
    import tempfile
    path=native_path('kimi',home)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('symlink_config')
    if path.exists() and path.stat().st_size>65536:raise ValueError('invalid_config')
    original=path.read_bytes() if path.exists() else b''
    text=original.decode('utf-8')
    parsed=tomllib.loads(text)
    if not isinstance(parsed.get('hooks',[]),list):raise ValueError('invalid_hooks')
    if text.count(KIMI_BEGIN)!=text.count(KIMI_END) or text.count(KIMI_BEGIN)>1:raise ValueError('invalid_observer_block')
    base=text
    if KIMI_BEGIN in text:
        start=text.index(KIMI_BEGIN);end=text.index(KIMI_END)+len(KIMI_END)
        if end<start:raise ValueError('invalid_observer_block')
        if start>0 and text[start-1]=='\n':start-=1
        base=text[:start]+text[end:]
    if enable:
        j=Journal(state);j.close()
        argv=command_argv('kimi',state)
        command=subprocess.list2cmdline(argv) if os.name=='nt' else shlex.join(argv)
        block=KIMI_BEGIN+''.join('[[hooks]]\nevent = '+json.dumps(event)+'\ncommand = '+json.dumps(command)+'\ntimeout = 2\n' for event in NATIVE_EVENTS['kimi'])+KIMI_END
        updated=base+('\n' if base else '')+block
    else:updated=base
    if len(updated.encode('utf-8'))>65536:raise ValueError('invalid_config')
    tomllib.loads(updated)
    # No native credential backups or TOML reserialization; the rest stays byte-exact.
    if (path.read_bytes() if path.exists() else b'')!=original:raise ValueError('config_changed_retry')
    if updated.encode('utf-8')!=original:
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,tmp=tempfile.mkstemp(prefix='.pulse-',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:stream.write(updated)
            os.replace(tmp,path)
        finally:
            if Path(tmp).exists():Path(tmp).unlink()
    return {'provider':'kimi','configured':enable,'requiresNewSession':True,'nativeTrustReviewMayBeRequired':True,'events':NATIVE_EVENTS['kimi'] if enable else [],'modelCalls':0,'clientFamily':'kimi-code-2.x'}

def scan_inventory(provider,skill_dirs=(),config_path=None):
    if provider not in PROVIDERS:raise ValueError('invalid_provider')
    entries=[]
    for root in skill_dirs:
        root=Path(root)
        if root.is_symlink() or not root.is_dir():raise ValueError('invalid_skill_directory')
        for f in sorted(root.glob('*/SKILL.md'))[:500]:
            if f.is_symlink() or f.parent.is_symlink():continue
            # Names only. Do not read instructions, descriptions, client projects or code.
            name=safe_name(f.parent.name)
            if name=='other':continue
            kind='other'
            if 'test' in name or 'qa' in name:kind='test'
            elif 'search' in name or 'context' in name:kind='search'
            entries.append({'provider':provider,'id':name,'kind':'skill','category':kind,'status':'configured','locator':str(f.absolute())})
    if config_path:
        p=Path(config_path)
        if p.is_symlink() or p.stat().st_size>1024*1024:raise ValueError('invalid_config')
        text=p.read_text();d=tomllib.loads(text) if p.suffix=='.toml' else json.loads(text)
        servers=d.get('mcp_servers',d.get('mcpServers',d.get('mcp',{}).get('servers',{})))
        if isinstance(servers,list):servers={r.get('name','other'):r for r in servers if isinstance(r,dict)}
        if isinstance(servers,dict):
            for name,r in list(servers.items())[:500]:
                name=safe_name(name)
                if name=='other':continue
                entries.append({'provider':provider,'id':name,'kind':'mcp','category':'remote','status':'disabled' if isinstance(r,dict) and (r.get('enabled') is False or r.get('disabled') is True) else 'configured'})
    return entries
