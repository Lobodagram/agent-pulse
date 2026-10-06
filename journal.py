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

from command_profile import command_shape, profile
from result_metadata import classify

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
    status,code,_=classify(event,raw,safe_name(raw.get('tool_name',raw.get('toolName'))))
    return status,code

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
        CREATE TABLE IF NOT EXISTS call_metadata(event TEXT PRIMARY KEY, signature TEXT, outcome_source TEXT);
        CREATE TABLE IF NOT EXISTS model_conflict(event TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS capability_locator(provider TEXT,id TEXT,locator TEXT,PRIMARY KEY(provider,id,locator));
        CREATE TABLE IF NOT EXISTS capability_evidence(provider TEXT,session TEXT,turn TEXT,call TEXT,
          id TEXT,kind TEXT,evidence TEXT,at REAL,PRIMARY KEY(provider,session,call,id,evidence));
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
        status,code,osource=classify(event,raw,tool)
        duration=number(raw.get('durationMs',raw.get('duration_ms')))
        if duration is not None and duration>86400000:duration=None
        duration_source='native' if duration is not None else 'unknown'
        eid=self.digest('event',[provider,session,call,phase]) if istool else self.digest('event',[provider,session,actor,event,turn,at])
        values=(eid,provider,session,turn,project,actor,call,phase,at,now,tool,kind,fingerprint,template,resource,revision,status,code,duration,duration_source,safe_name(source),turn_source,safe_name(raw.get('model')))
        # Retry deliveries deduplicate. Hook and historical projection remain distinct; no claims of complete coverage.
        self.db.execute('INSERT OR IGNORE INTO observation VALUES ('+','.join('?' for _ in values)+')',values)
        if istool:
            reported_model=safe_name(raw.get('model'))
            stored_model=self.db.execute('SELECT model FROM observation WHERE id=?',(eid,)).fetchone()['model']
            conflicted=self.db.execute('SELECT 1 FROM model_conflict WHERE event=?',(eid,)).fetchone()
            if not conflicted and reported_model!='other':
                if stored_model=='other':self.db.execute('UPDATE observation SET model=? WHERE id=?',(reported_model,eid))
                elif stored_model!=reported_model:
                    self.db.execute('INSERT OR IGNORE INTO model_conflict VALUES (?)',(eid,))
                    self.db.execute("UPDATE observation SET model='other' WHERE id=?",(eid,))
        p=profile(command) if command else None
        signature='unknown' if p and (not p['operations'] or any(o['family']=='unknown' for o in p['operations'])) else (
            ' '.join(o['category']+'.'+o['family']+(' '+p['operators'][i] if i<len(p['operators']) else '')
                     for i,o in enumerate(p['operations'])) if p else kind)
        self.db.execute('INSERT OR IGNORE INTO call_metadata VALUES (?,?,?)',(eid,signature,osource))
        if phase=='finish':
            previous=self.db.execute('SELECT outcome,exit_code,at,outcome_source FROM observation JOIN call_metadata ON observation.id=call_metadata.event WHERE id=?',(eid,)).fetchone()
            if previous and at>=previous['at']:
                if previous['outcome']=='unknown' and previous['outcome_source']!='conflicting-deliveries' and status in {'success','failed'}:
                    self.db.execute('UPDATE observation SET outcome=?,exit_code=?,at=?,received=?,duration_ms=?,duration_source=? WHERE id=?',
                                    (status,code,at,now,duration,duration_source,eid))
                    self.db.execute('UPDATE call_metadata SET outcome_source=? WHERE event=?',(osource,eid))
                elif previous['outcome'] in {'success','failed'} and status in {'success','failed'} and (previous['outcome']!=status or previous['exit_code']!=code):
                    self.db.execute('UPDATE observation SET outcome=?,exit_code=NULL WHERE id=?',('unknown',eid))
                    self.db.execute('UPDATE call_metadata SET outcome_source=? WHERE event=?',('conflicting-deliveries',eid))
        if istool and phase=='finish':
            stored=self.db.execute('SELECT outcome FROM observation WHERE id=?',(eid,)).fetchone()
            if stored and stored['outcome']=='success':self.observe_capabilities(provider,session,turn,call,tool,args,cwd,at)
            else:self.db.execute("DELETE FROM capability_evidence WHERE provider=? AND session=? AND call=? AND evidence!='declared'",(provider,session,call))
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
    def locator(self,path,cwd=''):
        # Lexical path normalization only; no skill content or symlink target reads.
        if not isinstance(path,str) or not path or len(path)>4096:return None
        return self.digest('capability-location',os.path.normcase(os.path.abspath(os.path.join(cwd,path))))
    def observe_capabilities(self,provider,session,turn,call,tool,args,cwd,at):
        args=args if isinstance(args,dict) else {}
        entries=self.db.execute('SELECT id,kind FROM inventory WHERE provider=?',(provider,)).fetchall()
        path=args.get('file_path',args.get('path'))
        loc=self.locator(path,cwd) if tool.lower() in {'read','read_file','cat_file'} else None
        loaded={r['id'] for r in self.db.execute('SELECT id FROM capability_locator WHERE provider=? AND locator=?',(provider,loc))} if loc else set()
        explicit=args.get('skill',args.get('skill_name',args.get('name'))) if tool.lower() in {'skill','use_skill'} else None
        for entry in entries:
            name,kind=entry['id'],entry['kind'];evidence=None
            if kind=='skill':
                if explicit==name:evidence='invoked'
                elif name in loaded:evidence='loaded'
            elif kind=='mcp' and tool.startswith('mcp__'+name+'__'):evidence='invoked'
            elif kind=='tool' and tool==name:evidence='invoked'
            if evidence:
                self.db.execute('INSERT OR IGNORE INTO capability_evidence VALUES (?,?,?,?,?,?,?,?)',
                                (provider,session,turn,call,name,kind,evidence,at))
    def declare_capability(self,provider,session,name,kind):
        if not isinstance(session,str) or not re.fullmatch('[a-f0-9]{32}',session):raise ValueError('invalid_session')
        if not self.db.execute('SELECT 1 FROM observation WHERE provider=? AND session=?',(provider,session)).fetchone():raise ValueError('unknown_session')
        if not self.db.execute('SELECT 1 FROM inventory WHERE provider=? AND id=? AND kind=?',(provider,name,kind)).fetchone():raise ValueError('unknown_capability')
        self.db.execute('INSERT OR REPLACE INTO capability_evidence VALUES (?,?,?,?,?,?,?,?)',
                        (provider,session,'manual','',name,kind,'declared',time.time()));self.db.commit()
    def import_inventory(self,raw):
        if not isinstance(raw,list) or len(raw)>1000:raise ValueError('invalid_inventory')
        entries=[];locators=[]
        for r in raw:
            if not isinstance(r,dict) or r.get('provider') not in PROVIDERS or r.get('kind') not in {'skill','tool','mcp'} or r.get('category') not in CATEGORIES or r.get('status') not in {'available','configured','disabled','unavailable'}:raise ValueError('invalid_inventory')
            name=safe_name(r.get('id'))
            if name=='other':raise ValueError('invalid_inventory_name')
            entries.append((r['provider'],name,r['kind'],r['category'],r['status'],number(r.get('observed')) or time.time()))
            if r.get('locator') is not None:
                if r['kind']!='skill' or not isinstance(r['locator'],str) or not os.path.isabs(r['locator']):raise ValueError('invalid_locator')
                locator=self.locator(r['locator'])
                if not locator:raise ValueError('invalid_locator')
                locators.append((r['provider'],name,locator))
        # A provider-only rescan preserves peers' existing hashed bindings.
        peers={(e[0],e[1]) for e in entries}
        old=[tuple(r) for r in self.db.execute('SELECT provider,id,locator FROM capability_locator') if (r['provider'],r['id']) in peers and not any(x[:2]==(r['provider'],r['id']) for x in locators)]
        self.db.execute('DELETE FROM inventory');self.db.executemany('INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?,?)',entries)
        self.db.execute('DELETE FROM capability_locator');self.db.executemany('INSERT OR IGNORE INTO capability_locator VALUES (?,?,?)',locators+old);self.db.commit()
    def calls(self,session=None,days=30,as_of=None,through_rowid=None):
        ceiling=time.time() if as_of is None else as_of
        args=[ceiling-days*86400,ceiling];where='received>=? AND received<=?'
        if through_rowid is not None:where+=' AND observation.rowid<=?';args.append(through_rowid)
        if session:where+=' AND session=?';args.append(session)
        rows=self.db.execute('SELECT observation.*,call_metadata.signature,call_metadata.outcome_source,EXISTS(SELECT 1 FROM model_conflict WHERE event=observation.id) AS model_conflicted FROM observation LEFT JOIN call_metadata ON observation.id=call_metadata.event WHERE '+where+' ORDER BY received DESC LIMIT 20000',args).fetchall()
        boundaries={}
        for r in rows:
            if r['phase'] in {'Stop','Interrupt','SessionEnd'}:
                key=(r['provider'],r['session'],r['actor'])
                boundaries[key]=max(boundaries.get(key,0),r['at'])
        paired={}
        for r in rows:
            if not r['call']:continue
            key=(r['provider'],r['session'],r['call']);paired.setdefault(key,{})[r['phase']]=dict(r)
        result=[]
        for parts in paired.values():
            start=parts.get('start');end=parts.get('finish');r=start or end
            from model_evidence import call_model
            model,model_source=call_model(start,end)
            status=end['outcome'] if end else 'pending'
            duration=end.get('duration_ms') if end else None;dsource=end['duration_source'] if end else 'unknown'
            if duration is None and start and end and end['at']>=start['at']:
                duration=(end['at']-start['at'])*1000;dsource='hook-wall' if start['source']=='hook' else 'event-wall'
            result.append({k:r[k] for k in ['provider','session','turn','project','actor','call','tool','category','fingerprint','template','resource','revision','source','turn_source','model']} | {
                'id':r['call'],'startedAt':start['at'] if start else None,'endedAt':end['at'] if end else None,
                'outcome':status,'exitCode':end['exit_code'] if end else None,'durationMs':duration,'durationSource':dsource,
                'operation':r['signature'] or 'legacy','outcomeSource':end['outcome_source'] or 'legacy' if end else 'not-finished',
                'model':model,'modelSource':model_source,
                'collectionIssue':('missing-finish-after-boundary' if boundaries.get((r['provider'],r['session'],r['actor']),0)>=r['at'] else
                                   'stale-unpaired' if time.time()-r['received']>600 else 'awaiting-finish') if not end else 'missing-start' if not start else None,
                'evidence':[v['id'] for v in [start,end] if v], 'paired':bool(start and end)})
        return sorted(result,key=lambda x:x['startedAt'] or x['endedAt'] or 0)
    def prune(self):
        cutoff=time.time()-30*86400
        self.db.execute('DELETE FROM observation WHERE received<?',(cutoff,))
        self.db.execute('DELETE FROM turn_usage WHERE at<?',(cutoff,))
        self.db.execute('DELETE FROM annotation WHERE session NOT IN (SELECT session FROM observation)')
        self.db.execute('DELETE FROM live_turn WHERE turn NOT IN (SELECT DISTINCT turn FROM observation)')
        self.db.execute('DELETE FROM observation WHERE id IN (SELECT id FROM observation ORDER BY received DESC LIMIT -1 OFFSET ?)',(MAX_EVENTS,))
        self.db.execute('DELETE FROM call_metadata WHERE event NOT IN (SELECT id FROM observation)')
        self.db.execute('DELETE FROM model_conflict WHERE event NOT IN (SELECT id FROM observation)')
        self.db.execute('DELETE FROM capability_evidence WHERE at<? OR session NOT IN (SELECT session FROM observation)',(cutoff,))
        self.db.execute('DELETE FROM capability_evidence WHERE rowid IN (SELECT rowid FROM capability_evidence ORDER BY at DESC LIMIT -1 OFFSET ?)',(MAX_EVENTS,))
        self.db.commit()
        self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')
    def stats(self):
        return {'events':self.db.execute('SELECT count(*) FROM observation').fetchone()[0], 'bytes':sum(p.stat().st_size for p in self.state.glob('journal.sqlite*') if p.is_file())}
