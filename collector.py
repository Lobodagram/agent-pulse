"""Agent Pulse: read-only counters. No models, native DB reads, cookie scraping or uploads.

Only native usage RPCs and a bounded projection of Codex tool/token events are allowed.
Never persist messages, arguments, results, code, reasoning, credentials or native paths.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import queue
import threading
import shutil
import signal
import sqlite3
import subprocess
import time
from platform_support import state_directory, find_node, zcode_paths
import providers as adapters

HERE = Path(__file__).resolve().parent
DEFAULT_STATE = state_directory()
METHODS = {'initialize', 'account/rateLimits/read', 'account/usage/read', 'thread/list', 'usage/stats'}
TIMEZONE = 'UTC'



class Unavailable(Exception):
    pass


class RPC:
    def __init__(self, command, env=None, timeout=18):
        options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NO_WINDOW}
        self.p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, bufsize=0, cwd=str(HERE), env=env, **options)
        self.chunks = queue.Queue(maxsize=128)
        self.stopped = threading.Event()
        def read():
            try:
                while not self.stopped.is_set():
                    chunk = os.read(self.p.stdout.fileno(), 65536)
                    while not self.stopped.is_set():
                        try: self.chunks.put(chunk, timeout=.1); break
                        except queue.Full: pass
                    if not chunk: break
            except (OSError, ValueError): pass
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        self.buffer = b''
        self.seq = 0
        self.timeout = timeout

    def send(self, data):
        try:
            self.p.stdin.write((json.dumps(data)+'\n').encode())
            self.p.stdin.flush()
        except (OSError, BrokenPipeError):
            raise Unavailable('native_process_closed') from None

    def call(self, method, params=None):
        if method not in METHODS:
            raise Unavailable('rpc_not_allowed')
        self.seq += 1
        msg = {'id': self.seq, 'method': method}
        if params is not None:
            msg['params'] = params
        self.send(msg)
        deadline = time.monotonic()+self.timeout
        total = 0
        while time.monotonic() < deadline:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                try:
                    result = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if result.get('id') == self.seq and ('result' in result or 'error' in result):
                    if 'error' in result:
                        code=result['error'].get('code')
                        raise Unavailable('native_rpc_'+(str(code) if isinstance(code,int) else 'error'))
                    if not isinstance(result['result'],dict):raise Unavailable('native_result_not_object')
                    return result['result']
                # Notifications and server-initiated requests are never persisted or answered.
            if len(self.buffer) > 8*1024*1024:
                raise Unavailable('response_too_large')
            try: chunk = self.chunks.get(timeout=min(.25, max(.001, deadline-time.monotonic())))
            except queue.Empty: continue
            if not chunk: raise Unavailable('native_process_closed')
            self.buffer += chunk
            total += len(chunk)
            if total > 8*1024*1024: raise Unavailable('response_too_large')
        raise Unavailable('native_timeout')

    def close(self):
        self.stopped.set()
        try:
            if os.name == 'nt': self.p.terminate()
            else: os.killpg(self.p.pid, signal.SIGTERM)
            self.p.wait(timeout=2)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill','/PID',str(self.p.pid),'/T','/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                    self.p.kill()
                else: os.killpg(self.p.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired): pass
            try: self.p.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
        self.reader.join(timeout=.3)
        for stream in [self.p.stdin, self.p.stdout]: stream.close()


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:/-]{0,100}', value):
        return 'other'
    if re.search(r'(?i)(bcm_|sk-|ghp_|github_pat_|hf_|bearer|token=)', value):
        return 'other'
    return value


def quota_windows(raw):
    buckets = raw.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        legacy = raw.get('rateLimits')
        buckets = {legacy.get('limitId') or 'codex': legacy} if isinstance(legacy, dict) else {}
    result = []
    for ident, bucket in buckets.items():
        if not isinstance(bucket, dict): continue
        for key in ['primary', 'secondary']:
            window = bucket.get(key)
            if not isinstance(window, dict): continue
            used = number(window.get('usedPercent'))
            mins = number(window.get('windowDurationMins'))
            result.append({'bucket': safe_name(ident), 'kind': key, 'durationMinutes': mins,
                           'remainingPercent': max(0, min(100, 100-used)) if used is not None else None,
                           'resetsAt': number(window.get('resetsAt'))})
    return result


def codex_usage(raw, day):
    buckets = raw.get('dailyUsageBuckets')
    daily = []
    if isinstance(buckets, list):
        for item in buckets:
            if isinstance(item, dict) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(item.get('startDate',''))):
                daily.append({'date':item['startDate'], 'tokens':number(item.get('tokens'))})
    today = next((i['tokens'] for i in daily if i['date'] == day), None)
    # A missing bucket is not a verified zero.
    return {'todayTokens':today, 'lifetimeTokens':number((raw.get('summary') or {}).get('lifetimeTokens')),
            'daily':daily, 'tokenSource':'Codex account/usage/read', 'tokenCoverage':'account-reported'}


def zcode_usage(raw, day):
    daily = []
    for week in raw.get('heatmap',{}).get('weeks',[]):
        for item in week.get('days',[]):
            if isinstance(item,dict) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(item.get('date',''))):
                daily.append({'date':item['date'],'tokens':number(item.get('totalTokens'))})
    tools = []
    for item in raw.get('tools',[]):
        if isinstance(item,dict):
            tools.append({'provider':'glm','name':safe_name(item.get('toolName')),
                          'count':number(item.get('callCount')) or 0,
                          'errors':number(item.get('errorCount')) or 0,
                          'averageMs':number(item.get('avgDurationMs')),
                          'source':'ZCode usage/stats · 7 days'})
    return {'todayTokens':next((i['tokens'] for i in daily if i['date']==day),None),
            'periodTokens':number(raw.get('summary',{}).get('totalTokens')),
            'sessions':number(raw.get('summary',{}).get('totalSessions')),
            'daily':daily,'tools':tools, 'tokenSource':'ZCode usage/stats',
            'tokenCoverage':'local ZCode records · 7 days'}


def collect_codex(day, config=None, read_patterns=False):
    binary = (config or {}).get('codexCli') or shutil.which('codex') or '/opt/homebrew/bin/codex'
    rpc = None
    base={'id':'codex','name':'Codex','status':'unavailable','quotas':[],'daily':[],
          'todayTokens':None,'resetCredits':None,'sourceStatus':[]}
    try:
        # Standalone metadata-only process; no thread/turn create/resume or MCP invocation.
        rpc = RPC([binary, '-c', 'analytics.enabled=false', 'app-server', '--stdio'])
        rpc.call('initialize', {'clientInfo':{'name':'agent-pulse','version':'0.2.0'},'capabilities':{}})
        rpc.send({'method':'initialized'})
        try:
            limits=rpc.call('account/rateLimits/read')
            base['quotas']=quota_windows(limits)
            credits=limits.get('rateLimitResetCredits')
            if isinstance(credits,dict):base['resetCredits']=number(credits.get('availableCount'))
            base['sourceStatus'].append('limits_ok')
        except Unavailable as e:base['sourceStatus'].append(str(e))
        try:
            base.update(codex_usage(rpc.call('account/usage/read'),day))
            base['sourceStatus'].append('tokens_ok')
        except Unavailable as e:base['sourceStatus'].append(str(e))
        threads=[]
        try:
            if not read_patterns: raise Unavailable('patterns_disabled')
            metadata=rpc.call('thread/list',{'limit':30,'sortKey':'updated_at','useStateDbOnly':True})
            # Keep only identifiers and rollout paths transiently, never titles/previews/turns.
            cutoff=time.time()-7*86400
            threads=[{'id':t['id'],'path':t.get('path')} for t in metadata.get('data',[])
                     if number(t.get('updatedAt')) is not None and t['updatedAt']>=cutoff]
        except Unavailable:pass
        base['status']='ready' if base['sourceStatus'] and any(x.endswith('_ok') for x in base['sourceStatus']) else 'unavailable'
        return base, threads
    except (Unavailable,OSError):
        base['sourceStatus'].append('native_unavailable')
        return base, []
    finally:
        if rpc:rpc.close()


def collect_glm(day, config=None):
    config=config or {}
    NODE=config.get('nodePath') or find_node()
    ZENTRY,ZBUILTIN=zcode_paths(config)
    NODE=Path(NODE)
    base={'id':'glm','name':'GLM / ZCode','status':'unavailable','quotas':[], 'daily':[],
          'todayTokens':None,'resetCredits':None, 'sourceStatus':[]}
    rpc=None
    try:
        if not all(p.is_file() for p in [NODE,ZENTRY,ZBUILTIN]):raise Unavailable('runtime_missing')
        env=os.environ.copy()
        # Installed app's CLI provider resolver otherwise guesses a nonexistent packaging path.
        # Native client reads its own provider configuration; we never read credentials.
        env['ZCODE_BUILTIN_PROVIDER_CONFIG_FILE']=str(ZBUILTIN)
        env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']=str(Path.home()/'.zcode/v2/provider_config.json')
        rpc=RPC([str(NODE),str(ZENTRY),'app-server'],env=env)
        raw=rpc.call('usage/stats',{'range':'7d','timeZone':'UTC'})
        base.update(zcode_usage(raw,day))
        base['status']='ready'
        base['sourceStatus']=['local_tokens_ok']
    except (Unavailable,OSError) as e:
        base['sourceStatus']=[str(e) if isinstance(e,Unavailable) else 'runtime_unavailable']
    finally:
        if rpc:rpc.close()
    return base


class Store:
    def __init__(self, directory):
        directory=Path(directory)
        if directory.is_symlink():raise ValueError('State directory cannot be a symlink')
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(directory,0o700)
        self.directory=directory
        db=directory/'metrics.sqlite'
        if db.is_symlink():raise ValueError('State DB cannot be a symlink')
        self.db=sqlite3.connect(db,timeout=5)
        os.chmod(db,0o600)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS daily(provider TEXT,date TEXT,tokens INTEGER,source TEXT,PRIMARY KEY(provider,date));
        CREATE TABLE IF NOT EXISTS samples(provider TEXT,at INTEGER,data TEXT,PRIMARY KEY(provider,at));
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,provider TEXT,at INTEGER,name TEXT,failed INTEGER);
        CREATE TABLE IF NOT EXISTS token_events(id TEXT PRIMARY KEY,date TEXT,tokens INTEGER);
        CREATE TABLE IF NOT EXISTS token_totals(id TEXT PRIMARY KEY,total INTEGER);
        CREATE TABLE IF NOT EXISTS cursors(id TEXT PRIMARY KEY,offset INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        revision=self.db.execute('SELECT value FROM settings WHERE key=?',('_projection_version',)).fetchone()
        if not revision or revision[0]!='4':
            # Reproject only the bounded tail. Stable event IDs prevent duplicate counters.
            self.db.execute('DELETE FROM events')
            self.db.execute('DELETE FROM cursors')
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('_projection_version','4'))
            self.db.commit()

    def settings(self):
        return {k:json.loads(v) for k,v in self.db.execute('SELECT key,value FROM settings')}

    def set_subscription(self,provider,date,kind):
        if provider not in adapters.IDS or kind not in ('renewal','expiry','none'):
            raise ValueError('Invalid setting')
        if kind=='none':date=''
        if date:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise ValueError('Use YYYY-MM-DD')
            datetime.strptime(date,'%Y-%m-%d')
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(provider,json.dumps({'date':date or None,'kind':kind,'source':'manual'})))
        self.db.commit()

    def persist(self,provider):
        pid=provider['id'];stamp=int(time.time())
        for row in provider.get('daily',[]):
            if row['tokens'] is not None:
                self.db.execute('INSERT OR REPLACE INTO daily VALUES (?,?,?,?)',(pid,row['date'],row['tokens'],provider.get('tokenSource','reported')))
        self.db.execute('INSERT OR REPLACE INTO samples VALUES (?,?,?)',(pid,stamp,json.dumps(provider)))
        self.db.execute('DELETE FROM samples WHERE at<?',(stamp-90*86400,))
        self.db.execute('DELETE FROM events WHERE at<?',(stamp-30*86400,))
        self.db.execute('DELETE FROM token_events WHERE date<?',((datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d'),))
        self.db.execute('DELETE FROM daily WHERE date<?',((datetime.now()-timedelta(days=180)).strftime('%Y-%m-%d'),))
        self.db.commit()

    def latest(self,pid):
        row=self.db.execute('SELECT at,data FROM samples WHERE provider=? ORDER BY at DESC LIMIT 1',(pid,)).fetchone()
        if not row:return None
        result=json.loads(row[1]);result['status']='stale';result['lastSuccessfulAt']=row[0]
        return result

    def project_rollout(self,thread):
        raw_path=thread.get('path')
        if not isinstance(raw_path,str):return 0
        path=Path(raw_path)
        allowed=Path.home()/'.codex/sessions'
        # Explicit native path, no directory crawling, no native DB/archived chats.
        if path.is_symlink() or not path.is_file() or path.suffix!='.jsonl':return 0
        if not path.resolve().is_relative_to(allowed.resolve()):return 0
        ident=hashlib.sha256(str(thread['id']).encode()).hexdigest()
        old=self.db.execute('SELECT offset FROM cursors WHERE id=?',(ident,)).fetchone()
        size=path.stat().st_size
        start=old[0] if old and old[0]<=size else max(0,size-2*1024*1024)
        added=0
        with path.open('rb') as f:
            f.seek(start)
            if start and not old:f.readline() # partial initial line
            total=0
            while True:
                offset=f.tell();line=f.readline(512*1024+1)
                if not line:break
                total+=len(line)
                if total>4*1024*1024 or len(line)>512*1024:
                    # Skip an oversized line without loading its message body.
                    while line and not line.endswith(b'\n') and total<=4*1024*1024:
                        line=f.readline(65536);total+=len(line)
                    if total>4*1024*1024:break
                    continue
                if not line.endswith(b'\n'):
                    f.seek(offset);break # incomplete write: retry later
                try:event=json.loads(line)
                except (ValueError,UnicodeError):continue
                token = project_token_event(event)
                if token:
                    date,total,last = token
                    prev=self.db.execute('SELECT total FROM token_totals WHERE id=?',(ident,)).fetchone()
                    amount=max(0,total-prev[0]) if prev else min(last,total)
                    eid=hashlib.sha256(f'{ident}:{offset}:tokens'.encode()).hexdigest()
                    self.db.execute('INSERT OR IGNORE INTO token_events VALUES (?,?,?)',(eid,date,amount))
                    self.db.execute('INSERT OR REPLACE INTO token_totals VALUES (?,?)',(ident,total))
                for at,name,failed in project_event(event):
                    eid=hashlib.sha256(f'{ident}:{offset}:{name}'.encode()).hexdigest()
                    before=self.db.total_changes
                    self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)',(eid,'codex',at,name,int(failed)))
                    added+=self.db.total_changes-before
            finish=f.tell()
        self.db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)',(ident,finish));self.db.commit()
        return added

    def local_tokens(self,day):
        row=self.db.execute('SELECT sum(tokens) FROM token_events WHERE date=?',(day,)).fetchone()
        return row[0] if row else None

    def persist_local_tokens(self):
        for day,tokens in self.db.execute('SELECT date,sum(tokens) FROM token_events GROUP BY date').fetchall():
            row=self.db.execute('SELECT source FROM daily WHERE provider=? AND date=?',('codex',day)).fetchone()
            if not row or row[0]=='Codex bounded local events':
                self.db.execute('INSERT OR REPLACE INTO daily VALUES (?,?,?,?)',('codex',day,tokens,'Codex bounded local events'))
        self.db.commit()

    def history(self):
        since=(datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d')
        return [{'provider':p,'date':d,'tokens':t} for p,d,t in self.db.execute('SELECT provider,date,tokens FROM daily WHERE date>=? ORDER BY date',(since,))]

    def patterns(self,glm_tools):
        cutoff=int(time.time())-7*86400
        own=[{'provider':p,'name':n,'count':c,'errors':None,'source':'Codex tool-call categories · partial 7 days'}
             for p,n,c,e in self.db.execute('SELECT provider,name,count(*),sum(failed) FROM events WHERE at>=? GROUP BY provider,name ORDER BY count(*) DESC',(cutoff,))]
        patterns=own+glm_tools
        for row in patterns:
            name=row['name'].lower()
            if any(x in name for x in ['exec','bash','shell']):hint='Проверить повторяемые команды; кандидат на локальный инструмент'
            elif any(x in name for x in ['read','glob','grep','search','query']):hint='Проверить повторное чтение; кандидат на точный поиск или краткий индекс'
            elif any(x in name for x in ['test','build','validate','check']):hint='Проверить возможность одной команды проверок'
            else:hint='Просмотреть сценарий перед созданием скилла или MCP'
            row['suggestion']='Review recurring workflow before adding an instrument; counts do not imply token savings'
        return sorted(patterns,key=lambda x:x['count'],reverse=True)[:30]


def project_token_event(event):
    if event.get('type')!='event_msg':return None
    p=event.get('payload')
    if not isinstance(p,dict) or p.get('type')!='token_count':return None
    info=p.get('info')
    if not isinstance(info,dict):return None
    total=number((info.get('total_token_usage') or {}).get('total_tokens'))
    last=number((info.get('last_token_usage') or {}).get('total_tokens'))
    if total is None or last is None:return None
    try:
        at=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
        if at.timestamp()<time.time()-7*86400:return None
        day=at.astimezone(timezone.utc).strftime('%Y-%m-%d')
    except (KeyError,ValueError,TypeError):return None
    return day,int(total),int(last)


def project_event(event):
    """Allowlist projection, never returns body/arguments/output/code or identifiers."""
    if event.get('type')!='response_item':return []
    p=event.get('payload')
    if not isinstance(p,dict) or p.get('type') not in ('function_call','custom_tool_call'):return []
    try:at=int(datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp())
    except (KeyError,ValueError,TypeError):return []
    if at < time.time()-7*86400:return []
    name=safe_name(p.get('name'))
    namespace=safe_name(p.get('namespace'))
    if namespace!='other' and name!='other':name=safe_name(namespace+'.'+name)
    names=[name]
    # Code-mode envelope: extract only invoked tool identifiers; discard all argument text.
    args=p.get('input') if p.get('type')=='custom_tool_call' else p.get('arguments')
    if name in ('functions.exec','exec') and isinstance(args,str) and len(args)<=128*1024:
        names=[safe_name(n) for n in re.findall(r'\btools\.([A-Za-z][A-Za-z0-9_]{0,99})\s*\(',args)] or [name]
    if name in ('functions.exec','exec','functions.exec_command','exec_command','bash','shell'):
        names += command_classes(args,code_mode=name in ('functions.exec','exec'))
    return [(at,n,False) for n in set(names) if n!='other']


def command_classes(arguments,code_mode=False):
    # Fixed classes only. Arguments are inspected transiently and never returned/stored.
    if not isinstance(arguments,str) or len(arguments)>128*1024:return []
    if code_mode:
        # Static envelope indicators; don't claim all branches executed.
        if not re.search(r'\btools\.(?:exec_command|bash)\s*\(',arguments):return []
        command=arguments
    else:
        try:
            body=json.loads(arguments)
            command=body.get('cmd',body.get('command','')) if isinstance(body,dict) else ''
        except ValueError:return []
        if not isinstance(command,str):return []
    rules={
        'command.tests':r'\b(?:pytest|unittest)\b|\b(?:npm|pnpm|bun)\s+(?:run\s+)?test\b',
        'command.build':r'\bswiftc\b|\bcargo\s+build\b|(?:\./)?build\.sh\b|\b(?:npm|pnpm|bun)\s+run\s+build\b',
        'command.git_inspection':r'\bgit\s+(?:status|diff|log|show|rev-parse)\b',
        'command.search_files':r'\brg(?:\s|\b)|\bglob\b',
        'command.read_files':r'\b(?:cat|sed|head|tail)\s|\bread_(?:text|bytes)\s*\(',
        'command.environment':r'--version\b|\bsw_vers\b|\bwhich\s|\bcommand\s+-v\b',
    }
    return [name for name,pattern in rules.items() if re.search(pattern,command)]


def snapshot(directory, collect_patterns=None):
    os.umask(0o077)
    config=adapters.load_config(directory)
    enabled=config['enabledProviders']
    collect_patterns=config.get('localPatterns',False) if collect_patterns is None else collect_patterns
    day=datetime.now(timezone.utc).strftime('%Y-%m-%d');store=Store(directory)
    items=[];threads=[]
    def fetch(ident):
        if ident=='codex': return collect_codex(day,config,collect_patterns)
        if ident=='glm': return collect_glm(day,config),[]
        return adapters.collect_extra(ident,directory,config),[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,enabled))
    for item,t in results:
        threads+=t
        if item['status']=='ready':
            item.setdefault('observedAt',int(time.time()));item['measurementDay']=day;store.persist(item)
        elif item['status']=='unavailable':
            cached=store.latest(item['id'])
            if cached:
                errors=item.get('sourceStatus',[]);item.update(cached);item['sourceStatus']=errors+['cached_previous_read']
                if item.get('measurementDay')!=day:item['todayTokens']=None
        items.append(item)
    codex=next((p for p in items if p['id']=='codex'),None)
    if collect_patterns and codex:
        for thread in threads:store.project_rollout(thread)
        store.persist_local_tokens()
        if codex.get('todayTokens') is None:
            codex['todayTokens']=store.local_tokens(day);codex['todayTokenCoverage']='partial-local'
        else:codex['todayTokenCoverage']='account-reported'
    settings=store.settings()
    for item in items:
        item['subscription']=settings.get(item['id'],{'date':None,'kind':'renewal','source':'manual'})
    result={'generatedAt':int(time.time()),'providers':items,'catalog':adapters.CATALOG,'localPatterns':bool(collect_patterns),
            'history':[x for x in store.history() if x['provider'] in enabled],
            'patterns':[x for x in store.patterns([t for p in items for t in p.get('tools',[])]) if x['provider'] in enabled and (x['provider']!='codex' or collect_patterns)],
            'patternCoverage':'Tool categories, partial local records; no per-tool token attribution',
            'privacy':'Local counters only; no prompts/results/code saved or uploaded'}
    store.db.close()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,default=DEFAULT_STATE)
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('snapshot');s.add_argument('--no-patterns',action='store_true')
    q=sub.add_parser('subscription');q.add_argument('--provider',choices=sorted(adapters.IDS),required=True);q.add_argument('--date',default='');q.add_argument('--kind',choices=['renewal','expiry','none'],required=True)
    sub.add_parser('catalog')
    c=sub.add_parser('configure');c.add_argument('--providers',required=True);c.add_argument('--local-patterns',choices=['on','off'],default='off')
    i=sub.add_parser('ingest');i.add_argument('--provider',choices=sorted(adapters.IDS),required=True);i.add_argument('--file',type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    try:
        if a.command=='subscription':
            s=Store(a.state);s.set_subscription(a.provider,a.date,a.kind);s.db.close();result={'saved':True}
        elif a.command=='catalog':result=adapters.CATALOG
        elif a.command=='configure':
            enabled=list(dict.fromkeys(a.providers.split(','))) if a.providers else []
            if any(x not in adapters.IDS for x in enabled):raise ValueError('invalid_provider')
            config=adapters.load_config(a.state);config.update(enabledProviders=enabled,localPatterns=a.local_patterns=='on')
            adapters.atomic_json(a.state/'config.json',config);result={'saved':True}
        elif a.command=='ingest':
            if a.file.is_symlink() or a.file.stat().st_size>2*1024*1024:raise ValueError('invalid_import')
            raw=json.loads(a.file.read_text(encoding='utf-8'));result=adapters.normalized(raw,a.provider)
            adapters.atomic_json(a.state/'imports'/f'{a.provider}.json',result);result={'saved':True}
        else:result=snapshot(a.state,False if a.no_patterns else None)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    except Exception:print('{"error":"collector_unavailable"}');raise SystemExit(1)

if __name__=='__main__':main()
