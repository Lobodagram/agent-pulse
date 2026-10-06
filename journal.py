"""Private local event journal. Native payloads are projected, never persisted verbatim."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import shlex
import sqlite3
import time

MAX_INPUT = 1024 * 1024
MAX_EVENTS = 100000
EVENTS = {'SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','PostToolUseFailure','Stop','SessionEnd','Interrupt','SubagentStart','SubagentStop','PreCompact','PostCompact'}
PROVIDERS = {'codex','glm','claude','kimi','qwen','gemini','cursor','copilot','windsurf','deepseek','openrouter'}
CATEGORIES = {'read','search','edit','test','build','inspect','environment','remote','delegate','shell','other','lifecycle'}

def number(v):
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 else None

def safe_name(v):
    if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,100}',v):return 'other'
    if re.search(r'(?i)(bcm_|sk-|ghp_|github_pat_|hf_|bearer|token|password|secret)',v):return 'other'
    return v

def private_dir(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink_state')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name!='nt':os.chmod(path,0o700)
    return path

def atomic_json(path,value):
    import tempfile
    path=Path(path);private_dir(path.parent)
    if path.is_symlink():raise ValueError('symlink_file')
    fd,tmp=tempfile.mkstemp(prefix='.pulse-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False)
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

def timestamp(raw,now):
    v=raw.get('timestamp',raw.get('at'))
    if isinstance(v,str):
        try:v=datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
        except ValueError:v=None
    v=number(v)
    if v is not None and v>10**12:v/=1000
    if raw.get('timestamp',raw.get('at')) is not None and (v is None or not now-31*86400<=v<=now+60):raise ValueError('invalid_event_time')
    return v if v is not None else now

def command_shape(command):
    if not isinstance(command,str) or len(command)>32768:return 'shell', 'shell <unparsed>'
    if any(x in command for x in ['\n','&&','||',';','`','$(','<<','>','|']):return 'shell', 'shell <compound>'
    try:tokens=shlex.split(command)
    except ValueError:return 'shell','shell <unparsed>'
    if not tokens:return 'shell','shell <empty>'
    exe=Path(tokens[0]).name
    known={'python','python3','pytest','npm','pnpm','bun','cargo','swiftc','git','rg','grep','cat','sed','head','tail','which','sw_vers','node','build.sh'}
    if exe not in known:return 'shell','shell <command>'
    words={'-m','unittest','pytest','discover','test','run','build','status','diff','log','show','rev-parse','--version','-s','-v','-q','-n','--files','-c','--check','--stat','install'}
    template=' '.join([exe]+[v if v in words else '<arg>' for v in tokens[1:20]])
    if exe=='pytest' or exe in {'python','python3'} and len(tokens)>2 and tokens[1:3] in [['-m','unittest'],['-m','pytest']]:kind='test'
    elif exe in {'npm','pnpm','bun'} and 'test' in tokens[1:3]:kind='test'
    elif exe=='swiftc' or exe=='build.sh' or exe=='cargo' and tokens[1:2]==['build'] or exe in {'npm','pnpm','bun'} and 'build' in tokens[1:3]:kind='build'
    elif exe=='git' and tokens[1:2] and tokens[1] in {'status','diff','log','show','rev-parse'}:kind='inspect'
    elif exe in {'rg','grep'}:kind='search'
    elif exe in {'cat','sed','head','tail'}:kind='read'
    elif '--version' in tokens or exe in {'which','sw_vers'}:kind='environment'
    else:kind='shell'
    return kind,template

def category(tool,args):
    name=tool.lower()
    if any(x in name for x in ['apply_patch','write','edit']):return 'edit'
    if any(x in name for x in ['read','cat_file']):return 'read'
    if any(x in name for x in ['search','grep','glob','query']):return 'search'
    if any(x in name for x in ['agent','task','spawn']):return 'delegate'
    if name.startswith('mcp__') or 'web' in name:return 'remote'
    command=args.get('command',args.get('cmd','')) if isinstance(args,dict) else ''
    return command_shape(command)[0] if command else 'shell' if any(x in name for x in ['bash','shell','exec']) else 'other'

def outcome(event,raw):
    if event=='PostToolUseFailure':return 'failed',None
    if event!='PostToolUse':return 'unknown',None
    response=raw.get('tool_response',raw.get('toolResponse'))
    code=None;failed=None
    tool=safe_name(raw.get('tool_name',raw.get('toolName'))).lower()
    shell=tool in {'bash','shell','exec_command','functions.exec_command','functions.exec','exec'}
    if isinstance(response,dict):
        if any(response.get(k) is True for k in ['isError','is_error','failed']):failed=True
        for k in ['exit_code','exitCode']:
            v=response.get(k)
            if isinstance(v,int) and not isinstance(v,bool) and -255<=v<=255:code=v;break
        if code is None and shell:
            # Native MCP text wrappers can contain a JSON result or a shell exit marker.
            for block in (response.get('content') or [])[:10] if isinstance(response.get('content'),list) else []:
                text=block.get('text') if isinstance(block,dict) else None
                if isinstance(text,str):
                    m=re.search(r'(?:"exit_code"\s*:\s*|Process exited with code\s+)(-?\d{1,3})\b',text[:128*1024])
                    if m:code=int(m.group(1));break
    if code is not None:return ('success' if code==0 else 'failed'),code
    if failed:return 'failed',None
    # A completed shell tool can still mean an ongoing process. Do not invent exit status.
    return ('unknown' if shell else 'success'),None

class Journal:
    def __init__(self,state):
        self.state=private_dir(state)
        keyfile=self.state/'Secrets.json'
        if keyfile.is_symlink():raise ValueError('symlink_secret')
        # Cross-process lock is separate from Secrets.json: atomic rename retains the lock.
        lockpath=self.state/'.journal-key.lock'
        if lockpath.is_symlink():raise ValueError('symlink_lock')
        with open(lockpath,'a+b') as lock:
            if os.name=='nt':
                import msvcrt
                lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX)
                os.chmod(lockpath,0o600)
            secret=json.loads(keyfile.read_text()) if keyfile.exists() else {}
            if not isinstance(secret,dict):raise ValueError('invalid_secrets')
            key=secret.get('journalHmacKey')
            if key is None:
                key=secrets.token_hex(32);secret['journalHmacKey']=key;atomic_json(keyfile,secret)
            if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('invalid_journal_key')
            if os.name!='nt':os.chmod(keyfile,0o600)
            self.key=bytes.fromhex(key)
        path=self.state/'journal.sqlite'
        if path.is_symlink():raise ValueError('symlink_db')
        self.db=sqlite3.connect(path,timeout=.75)
        self.db.row_factory=sqlite3.Row
        if os.name!='nt':os.chmod(path,0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA max_page_count=65536')
        self.db.execute('PRAGMA journal_size_limit=1048576')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS observation(id TEXT PRIMARY KEY, provider TEXT, session TEXT, turn TEXT,
          project TEXT, actor TEXT, call TEXT, phase TEXT, at REAL, received REAL, tool TEXT, category TEXT,
          fingerprint TEXT, template TEXT, resource TEXT, revision TEXT, outcome TEXT, exit_code INTEGER,
          duration_ms REAL, duration_source TEXT, source TEXT, turn_source TEXT, model TEXT);
        CREATE INDEX IF NOT EXISTS observation_session ON observation(session,at);
        CREATE INDEX IF NOT EXISTS observation_received ON observation(received);
        CREATE TABLE IF NOT EXISTS live_turn(session TEXT PRIMARY KEY, turn TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS health(provider TEXT PRIMARY KEY, last_event REAL, rejected INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inventory(provider TEXT,id TEXT,kind TEXT,category TEXT,status TEXT,
          observed REAL,PRIMARY KEY(provider,id));
        CREATE TABLE IF NOT EXISTS annotation(session TEXT PRIMARY KEY, label TEXT, outcome TEXT, variant TEXT, observed REAL);
        CREATE TABLE IF NOT EXISTS turn_usage(provider TEXT,session TEXT,turn TEXT,input REAL,cached_input REAL,
          output REAL,source TEXT,at REAL,PRIMARY KEY(provider,session,turn,source));
        ''')
        self.db.commit()
    def close(self):self.db.close()
    def digest(self,label,value):
        body=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)
        return hmac.new(self.key,(label+'\0'+body).encode(),hashlib.sha256).hexdigest()[:32]
    def reject(self,provider):
        if provider not in PROVIDERS:return
        self.db.execute('INSERT INTO health(provider,rejected) VALUES (?,1) ON CONFLICT(provider) DO UPDATE SET rejected=rejected+1',(provider,));self.db.commit()
    def record(self,provider,raw,source='hook'):
        if provider not in PROVIDERS or not isinstance(raw,dict):raise ValueError('invalid_event')
        event=raw.get('hook_event_name',raw.get('hookEventName'))
        sid=raw.get('session_id',raw.get('sessionId'))
        if event not in EVENTS or not isinstance(sid,str) or not sid or len(sid)>1000:raise ValueError('invalid_event')
        now=time.time();at=timestamp(raw,now)
        session=self.digest('session',[provider,sid])
        actor=self.digest('actor',raw.get('agent_id',raw.get('agentId',sid)))
        # Subagents can share the parent's session id; separate their sequence lane.
        lane=self.digest('lane',[session,actor])
        cwd=raw.get('cwd','');project=self.digest('project',cwd) if isinstance(cwd,str) and cwd else 'unknown'
        supplied=raw.get('turn_id',raw.get('turnId'))
        existing=self.db.execute('SELECT turn,source FROM live_turn WHERE session=?',(lane,)).fetchone()
        if supplied and isinstance(supplied,str):turn=self.digest('turn',[provider,sid,supplied]);turn_source='native'
        elif event=='UserPromptSubmit':turn=self.digest('turn',[lane,at]);turn_source='hook-boundary'
        elif existing:turn,turn_source=existing
        else:turn=self.digest('turn',[lane,'unscoped']);turn_source='unknown'
        if event=='UserPromptSubmit' or supplied:
            self.db.execute('INSERT OR REPLACE INTO live_turn VALUES (?,?,?)',(lane,turn,turn_source))
        callraw=raw.get('tool_use_id',raw.get('toolCallId'))
        istool=event in {'PreToolUse','PostToolUse','PostToolUseFailure'}
        if istool and (not isinstance(callraw,str) or not callraw or len(callraw)>1000):raise ValueError('missing_call_id')
        call=self.digest('call',[provider,sid,callraw]) if istool else ''
        phase='start' if event=='PreToolUse' else 'finish' if event in {'PostToolUse','PostToolUseFailure'} else event
        tool=safe_name(raw.get('tool_name',raw.get('toolName'))) if istool else event
        args=raw.get('tool_input',raw.get('toolInput',{}));kind=category(tool,args) if istool else 'lifecycle'
        fingerprint=self.digest('input',[tool,args]) if istool else ''
        # Template categories expose no literal strings, code, filenames or arbitrary flag values.
        command=args.get('command',args.get('cmd','')) if isinstance(args,dict) else ''
        template=command_shape(command)[1] if command else kind+'.'+tool if istool else event
        resource='';revision=''
        path=args.get('file_path',args.get('path')) if isinstance(args,dict) else None
        if isinstance(path,str) and len(path)<4096:
            resource=self.digest('resource',path)
            # Metadata only, inside the active project, no file content reading.
            try:
                target=Path(path) if Path(path).is_absolute() else Path(cwd)/path
                if cwd and target.resolve().is_relative_to(Path(cwd).resolve()) and not target.is_symlink():
                    st=target.stat();revision=self.digest('revision',[st.st_mtime_ns,st.st_size])
            except (OSError,ValueError):pass
        status,code=outcome(event,raw)
        duration=number(raw.get('durationMs',raw.get('duration_ms')))
        if duration is not None and duration>86400000:duration=None
        duration_source='native' if duration is not None else 'unknown'
        eid=self.digest('event',[provider,session,call,phase]) if istool else self.digest('event',[provider,session,actor,event,turn,at])
        values=(eid,provider,session,turn,project,actor,call,phase,at,now,tool,kind,fingerprint,template,resource,revision,status,code,duration,duration_source,safe_name(source),turn_source,safe_name(raw.get('model')))
        # Retry deliveries deduplicate. Hook and historical projection remain distinct; no claims of complete coverage.
        self.db.execute('INSERT OR IGNORE INTO observation VALUES ('+','.join('?' for _ in values)+')',values)
        self.db.execute('INSERT INTO health(provider,last_event,rejected) VALUES (?,?,0) ON CONFLICT(provider) DO UPDATE SET last_event=max(coalesce(last_event,0),excluded.last_event)',(provider,now))
        if event in {'Stop','Interrupt','SessionEnd'}:self.db.execute('DELETE FROM live_turn WHERE session=?',(lane,))
        self.db.commit()
        rowid=self.db.execute('SELECT rowid FROM observation WHERE id=?',(eid,)).fetchone()
        if rowid and rowid[0]%500==0:self.prune()
        return eid
    def usage(self,provider,sid,tid,usage,source='native-turn'):
        # Only explicit per-turn native usage. No differencing overlapping account counters.
        if provider not in PROVIDERS or not isinstance(usage,dict) or not sid or not tid:raise ValueError('invalid_usage')
        vals=[number(usage.get(x)) for x in ['input','cached_input','output']]
        if all(v is None for v in vals):raise ValueError('missing_usage')
        if vals[1] is not None and vals[0] is not None and vals[1]>vals[0]:raise ValueError('invalid_cached_input')
        self.db.execute('INSERT OR REPLACE INTO turn_usage VALUES (?,?,?,?,?,?,?,?)',(provider,self.digest('session',[provider,sid]),self.digest('turn',[provider,sid,tid]),*vals,safe_name(source),time.time()));self.db.commit()
    def annotate(self,session,label,outcome,variant):
        if not re.fullmatch(r'[a-f0-9]{32}',session):raise ValueError('invalid_session')
        if not self.db.execute('SELECT 1 FROM observation WHERE session=?',(session,)).fetchone():raise ValueError('unknown_session')
        if outcome not in {'accepted','failed','rework','unknown'}:raise ValueError('invalid_outcome')
        label=safe_name(label);variant=safe_name(variant)
        if label=='other' or variant=='other':raise ValueError('use_non_sensitive_slug')
        self.db.execute('INSERT OR REPLACE INTO annotation VALUES (?,?,?,?,?)',(session,label,outcome,variant,time.time()));self.db.commit()
    def import_inventory(self,raw):
        if not isinstance(raw,list) or len(raw)>1000:raise ValueError('invalid_inventory')
        entries=[]
        for r in raw:
            if not isinstance(r,dict) or r.get('provider') not in PROVIDERS or r.get('kind') not in {'skill','tool','mcp'} or r.get('category') not in CATEGORIES or r.get('status') not in {'available','configured','disabled','unavailable'}:raise ValueError('invalid_inventory')
            name=safe_name(r.get('id'))
            if name=='other':raise ValueError('invalid_inventory_name')
            entries.append((r['provider'],name,r['kind'],r['category'],r['status'],number(r.get('observed')) or time.time()))
        self.db.execute('DELETE FROM inventory');self.db.executemany('INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?,?)',entries);self.db.commit()
    def calls(self,session=None,days=30):
        args=[time.time()-days*86400];where='received>=?'
        if session:where+=' AND session=?';args.append(session)
        rows=self.db.execute('SELECT * FROM observation WHERE '+where+' ORDER BY received DESC LIMIT 20000',args).fetchall()
        paired={}
        for r in rows:
            if not r['call']:continue
            key=(r['provider'],r['session'],r['call']);paired.setdefault(key,{})[r['phase']]=dict(r)
        result=[]
        for parts in paired.values():
            start=parts.get('start');end=parts.get('finish');r=start or end
            status=end['outcome'] if end else 'pending'
            duration=end.get('duration_ms') if end else None;dsource=end['duration_source'] if end else 'unknown'
            if duration is None and start and end and end['at']>=start['at']:
                duration=(end['at']-start['at'])*1000;dsource='hook-wall' if start['source']=='hook' else 'event-wall'
            result.append({k:r[k] for k in ['provider','session','turn','project','actor','call','tool','category','fingerprint','template','resource','revision','source','turn_source','model']} | {
                'id':r['call'],'startedAt':start['at'] if start else None,'endedAt':end['at'] if end else None,
                'outcome':status,'exitCode':end['exit_code'] if end else None,'durationMs':duration,'durationSource':dsource,
                'evidence':[v['id'] for v in [start,end] if v], 'paired':bool(start and end)})
        return sorted(result,key=lambda x:x['startedAt'] or x['endedAt'] or 0)
    def prune(self):
        cutoff=time.time()-30*86400
        self.db.execute('DELETE FROM observation WHERE received<?',(cutoff,))
        self.db.execute('DELETE FROM turn_usage WHERE at<?',(cutoff,))
        self.db.execute('DELETE FROM annotation WHERE session NOT IN (SELECT session FROM observation)')
        self.db.execute('DELETE FROM live_turn WHERE turn NOT IN (SELECT DISTINCT turn FROM observation)')
        self.db.execute('DELETE FROM observation WHERE id IN (SELECT id FROM observation ORDER BY received DESC LIMIT -1 OFFSET ?)',(MAX_EVENTS,))
        self.db.commit()
        self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')
    def stats(self):
        return {'events':self.db.execute('SELECT count(*) FROM observation').fetchone()[0], 'bytes':sum(p.stat().st_size for p in self.state.glob('journal.sqlite*') if p.is_file())}
