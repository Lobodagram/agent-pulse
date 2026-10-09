"""Agent Pulse: read-only counters. No models, native DB reads, cookie scraping or uploads.

Only native usage RPCs and a bounded projection of Codex tool/token events are allowed.
Never persist messages, arguments, results, code, reasoning, credentials or native paths.
"""
from __future__ import annotations
import sys
if sys.version_info < (3,11):
    # Old interpreters must not import tomllib; hook commands stay silent/fail-open.
    if 'hook' in sys.argv:raise SystemExit(0)
    print('Agent Pulse requires Python 3.11 or newer. Use a supported Python or the packaged app.',file=sys.stderr)
    raise SystemExit(1)
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
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
import journal
import analytics
import journal_cli
import instrumentation
import mcp_server
from pulse_version import __version__

HERE = Path(__file__).resolve().parent
DEFAULT_STATE = state_directory()
METHODS = {'initialize', 'account/rateLimits/read', 'account/read', 'account/usage/read', 'thread/list', 'usage/stats'}
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


from sanitizers import number, safe_name

def quota_windows(raw):
    buckets = raw.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        legacy = raw.get('rateLimits')
        buckets = {legacy.get('limitId') or 'codex': legacy} if isinstance(legacy, dict) else {}
    result = []
    for ident, bucket in sorted(buckets.items(),key=lambda item:(item[0]!='codex',item[0])):
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
            'todayTokenStatus':'reported' if today is not None else 'account-day-pending',
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


def collect_codex(day, config=None, read_patterns=False, quota_only=False, directory=None, read_local_tokens=False):
    binary = (config or {}).get('codexCli') or shutil.which('codex') or next((p for p in ['/opt/homebrew/bin/codex','/usr/local/bin/codex'] if os.path.isfile(p) and os.access(p,os.X_OK)), 'codex')
    rpc = None
    base={'id':'codex','name':'Codex','status':'unavailable','quotas':[],'daily':[],
          'todayTokens':None,'resetCredits':None,'sourceStatus':[]}
    try:
        # Standalone metadata-only process; no thread/turn create/resume or MCP invocation.
        rpc = RPC([binary, '-c', 'analytics.enabled=false', 'app-server', '--stdio'])
        rpc.call('initialize', {'clientInfo':{'name':'agent-pulse','version':__version__},'capabilities':{}})
        rpc.send({'method':'initialized'})
        try:
            limits=rpc.call('account/rateLimits/read')
            base['quotas']=quota_windows(limits)
            credits=limits.get('rateLimitResetCredits')
            if isinstance(credits,dict):base['resetCredits']=number(credits.get('availableCount'))
            base['sourceStatus'].append('limits_ok');base['quotaObservedAt']=int(time.time())
            aid=limits.get('accountId')
            if not isinstance(aid,str) or not aid:
                try:
                    account=rpc.call('account/read',{'refreshToken':False}).get('account') or {}
                    aid=account.get('id') or account.get('email')
                except Unavailable:aid=None
            if isinstance(aid,str) and aid:
                j=journal.Journal(directory or DEFAULT_STATE)
                try:base['accountScope']=j.digest('account',['codex',aid])
                finally:j.close()
            else:base['accountScope']=None
            base['accountCoverage']='native identity hashed' if base.get('accountScope') else 'identity unknown; no account cache fallback'
        except Unavailable as e:base['sourceStatus'].append(str(e))
        if quota_only:
            base['status']='ready' if 'limits_ok' in base['sourceStatus'] else 'unavailable'
            return base,[]
        try:
            base.update(codex_usage(rpc.call('account/usage/read'),day))
            base['sourceStatus'].append('tokens_ok')
        except Unavailable as e:base['sourceStatus'].append(str(e))
        threads=[]
        try:
            if not (read_patterns or read_local_tokens): raise Unavailable('patterns_disabled')
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


def collect_glm(day, config=None, directory=None):
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
    import glm_quota
    quota=glm_quota.collect(directory or DEFAULT_STATE)
    base.update(quota)
    base['sourceStatus'].append('glm_quota_'+quota['quotaStatus'])
    if quota.get('quotaError'):base['sourceStatus'].append('glm_quota_error_'+quota['quotaError'])
    if quota['quotaStatus']=='ready':base['status']='ready'
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
        CREATE TABLE IF NOT EXISTS account_daily(provider TEXT,scope TEXT,date TEXT,tokens INTEGER,source TEXT,PRIMARY KEY(provider,scope,date));
        CREATE TABLE IF NOT EXISTS samples(provider TEXT,at INTEGER,data TEXT,PRIMARY KEY(provider,at));
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,provider TEXT,at INTEGER,name TEXT,failed INTEGER);
        CREATE TABLE IF NOT EXISTS token_events(id TEXT PRIMARY KEY,date TEXT,tokens INTEGER);
        CREATE TABLE IF NOT EXISTS token_totals(id TEXT PRIMARY KEY,total INTEGER);
        CREATE TABLE IF NOT EXISTS token_profiles(id TEXT PRIMARY KEY,input INTEGER,output INTEGER,cached INTEGER);
        CREATE TABLE IF NOT EXISTS token_profile_totals(id TEXT PRIMARY KEY,date TEXT,input INTEGER,output INTEGER,cached INTEGER,total INTEGER);
        CREATE TABLE IF NOT EXISTS cursors(id TEXT PRIMARY KEY,offset INTEGER);
        CREATE TABLE IF NOT EXISTS rollout_gaps(id TEXT PRIMARY KEY,at INTEGER);
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
        value=json.dumps({'date':date or None,'kind':kind,'source':'manual'})
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(provider,value))
        scope=self.db.execute('SELECT value FROM settings WHERE key=?',('_account_'+provider,)).fetchone()
        if scope:self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('_billing_'+provider+'_'+json.loads(scope[0]),value))
        self.db.commit()

    def persist(self,provider):
        pid=provider['id'];stamp=int(time.time())
        scope=provider.get('accountScope')
        if isinstance(scope,str):
            old=self.db.execute('SELECT value FROM settings WHERE key=?',('_account_'+pid,)).fetchone()
            if not old or json.loads(old[0])!=scope:
                self.db.execute('DELETE FROM samples WHERE provider=?',(pid,))
                if old:
                    billing=self.db.execute('SELECT value FROM settings WHERE key=?',(pid,)).fetchone()
                    if billing:self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('_billing_'+pid+'_'+json.loads(old[0]),billing[0]))
                    self.db.execute('DELETE FROM settings WHERE key=?',(pid,))
                    saved=self.db.execute('SELECT value FROM settings WHERE key=?',('_billing_'+pid+'_'+scope,)).fetchone()
                    if saved:self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(pid,saved[0]))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('_account_'+pid,json.dumps(scope)))
        for row in provider.get('daily',[]):
            if row['tokens'] is not None:
                if isinstance(scope,str):
                    self.db.execute('INSERT OR REPLACE INTO account_daily VALUES (?,?,?,?,?)',(pid,scope,row['date'],row['tokens'],provider.get('tokenSource','reported')))
                else:self.db.execute('INSERT OR REPLACE INTO daily VALUES (?,?,?,?)',(pid,row['date'],row['tokens'],provider.get('tokenSource','reported')))
        self.db.execute('INSERT OR REPLACE INTO samples VALUES (?,?,?)',(pid,stamp,json.dumps(provider)))
        self.db.execute('DELETE FROM samples WHERE at<?',(stamp-90*86400,))
        self.db.execute('DELETE FROM events WHERE at<?',(stamp-30*86400,))
        self.db.execute('DELETE FROM rollout_gaps WHERE at<?',(stamp-30*86400,))
        self.db.execute('DELETE FROM token_events WHERE date<?',((datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d'),))
        self.db.execute('DELETE FROM token_profiles WHERE NOT EXISTS (SELECT 1 FROM token_events e WHERE e.id=token_profiles.id)')
        self.db.execute('DELETE FROM token_profile_totals WHERE date<?',((datetime.now(timezone.utc)-timedelta(days=30)).strftime('%Y-%m-%d'),))
        self.db.execute('DELETE FROM account_daily WHERE date<?',((datetime.now()-timedelta(days=180)).strftime('%Y-%m-%d'),))
        self.db.execute('DELETE FROM daily WHERE date<?',((datetime.now()-timedelta(days=180)).strftime('%Y-%m-%d'),))
        self.db.commit()

    def latest(self,pid):
        row=self.db.execute('SELECT at,data FROM samples WHERE provider=? ORDER BY at DESC LIMIT 1',(pid,)).fetchone()
        if not row:return None
        result=json.loads(row[1]);result['status']='stale';result['lastSuccessfulAt']=row[0]
        return result

    def project_rollout(self,thread, include_tools=True):
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
        continuous=bool(old and 0<=old[0]<=size and size-old[0]<=4*1024*1024)
        start=old[0] if continuous else max(0,size-2*1024*1024)
        if old and not continuous:
            # Bounded recent coverage rather than an indefinitely delayed backlog.
            # A cumulative delta across skipped bytes would misattribute older days.
            self.db.execute('DELETE FROM token_totals WHERE id=?',(ident,))
            self.db.execute('DELETE FROM token_profile_totals WHERE id=?',(ident,))
            self.db.execute('INSERT OR REPLACE INTO rollout_gaps VALUES (?,?)',(ident,int(time.time())))
        added=0
        with path.open('rb') as f:
            f.seek(start)
            bytes_read=0
            if start and not continuous:
                # Skip a partial first line in bounded chunks, including huge bodies.
                while True:
                    part=f.readline(65536);bytes_read+=len(part)
                    if not part or part.endswith(b'\n') or bytes_read>4*1024*1024:break
            while True:
                if bytes_read>4*1024*1024:break
                offset=f.tell();line=f.readline(512*1024+1)
                if not line:break
                bytes_read+=len(line)
                if bytes_read>4*1024*1024 or len(line)>512*1024:
                    # Skip an oversized line without loading its message body.
                    while line and not line.endswith(b'\n') and bytes_read<=4*1024*1024:
                        line=f.readline(65536);bytes_read+=len(line)
                    if bytes_read>4*1024*1024:break
                    continue
                if not line.endswith(b'\n'):
                    f.seek(offset);break # incomplete write: retry later
                try:event=json.loads(line)
                except (ValueError,UnicodeError):continue
                token = project_token_event(event)
                if token:
                    date,cumulative_total,last = token
                    prev=self.db.execute('SELECT total FROM token_totals WHERE id=?',(ident,)).fetchone()
                    amount=max(0,cumulative_total-prev[0]) if prev else min(last,cumulative_total)
                    eid=hashlib.sha256(f'{ident}:{offset}:tokens'.encode()).hexdigest()
                    self.db.execute('INSERT OR IGNORE INTO token_events VALUES (?,?,?)',(eid,date,amount))
                    breakdown=project_token_breakdown(event)
                    baseline=self.db.execute('SELECT date,input,output,cached,total FROM token_profile_totals WHERE id=?',(ident,)).fetchone()
                    if breakdown:
                        current,latest=breakdown
                        # A vector delta is usable only with the same validated total baseline and UTC day.
                        if baseline and baseline[0]==date and prev and baseline[4]==prev[0] and cumulative_total>=prev[0]:
                            observed=tuple(a-b for a,b in zip(current,baseline[1:4]))
                        elif not prev or cumulative_total>prev[0]:observed=latest
                        else:observed=None
                        if observed is not None and min(observed)>=0 and observed[2]<=observed[0] and sum(observed[:2])<=amount:
                            self.db.execute('INSERT OR IGNORE INTO token_profiles VALUES (?,?,?,?)',(eid,*observed))
                        self.db.execute('INSERT OR REPLACE INTO token_profile_totals VALUES (?,?,?,?,?,?)',(ident,date,*current,cumulative_total))
                    else:self.db.execute('DELETE FROM token_profile_totals WHERE id=?',(ident,))
                    self.db.execute('INSERT OR REPLACE INTO token_totals VALUES (?,?)',(ident,cumulative_total))
                for at,name,failed in (project_event(event) if include_tools else []):
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

    def local_token_profile(self,day):
        """Observed device-day counters; never account, task, request or saving attribution."""
        row=self.db.execute('''SELECT sum(p.input),sum(p.output),sum(p.cached),sum(e.tokens),
          sum(CASE WHEN e.tokens>0 AND p.id IS NULL THEN 1 ELSE 0 END)
          FROM token_events e LEFT JOIN token_profiles p ON p.id=e.id WHERE e.date=?''',(day,)).fetchone()
        inputs,outputs,cached,observed,gaps=row
        profiled=inputs+outputs if inputs is not None and outputs is not None else None
        return {'provider':'codex','date':day,'scope':'device-local','coverage':'partial-local',
                'inputTokens':inputs,'outputTokens':outputs,'cachedInputTokens':cached,'profiledTokens':profiled,
                'observedTokens':observed,'cacheHitRate':cached/inputs if inputs else None,
                'counterCoverageRate':profiled/observed if profiled is not None and observed else None,
                'unprofiledEvents':gaps or 0,'modelRequests':None,'subscriptionSavings':None,
                'attribution':'observed device day only; no task or asset attribution'}

    def persist_local_tokens(self):
        for day,tokens in self.db.execute('SELECT date,sum(tokens) FROM token_events GROUP BY date').fetchall():
            row=self.db.execute('SELECT source FROM daily WHERE provider=? AND date=?',('codex',day)).fetchone()
            if not row or row[0]=='Codex bounded local events':
                self.db.execute('INSERT OR REPLACE INTO daily VALUES (?,?,?,?)',('codex',day,tokens,'Codex bounded local events'))
        self.db.commit()

    def history(self):
        # Native account totals are upserted per account/day, then summed across known accounts.
        # Legacy unscoped rows remain stored, but cannot be added to an overlapping day safely.
        rows=[dict(provider=p,date=d,tokens=t,coverage='partial-local' if s=='Codex bounded local events' else 'legacy-or-local') for p,d,t,s in self.db.execute("SELECT provider,date,tokens,source FROM daily WHERE date>=date('now','-30 days') ORDER BY date")]
        known=[dict(provider=p,date=d,tokens=t,coverage='known-account-sum') for p,d,t in self.db.execute("SELECT provider,date,sum(tokens) FROM account_daily WHERE date>=date('now','-30 days') GROUP BY provider,date")]
        covered={(r['provider'],r['date']) for r in known}
        return sorted([r for r in rows if (r['provider'],r['date']) not in covered]+known,key=lambda r:(r['date'],r['provider']))

    def patterns(self,glm_tools):
        cutoff=int(time.time())-7*86400
        own=[{'provider':p,'name':n,'count':c,'errors':None,'source':'Codex tool-call categories · partial 7 days'}
             for p,n,c in self.db.execute('SELECT provider,name,count(*) FROM events WHERE at>=? GROUP BY provider,name ORDER BY count(*) DESC',(cutoff,))]
        patterns=own+glm_tools
        for row in patterns:
            row['suggestion']='Review recurring workflow before adding an instrument; counts do not imply token savings'
            row['suggestionRu']='Проверьте повторяющийся сценарий перед добавлением инструмента; частота не доказывает экономию токенов'
        return sorted(patterns,key=lambda x:x['count'],reverse=True)[:30]


def project_token_event(event):
    if not isinstance(event,dict):return None
    if event.get('type')!='event_msg':return None
    p=event.get('payload')
    if not isinstance(p,dict) or p.get('type')!='token_count':return None
    info=p.get('info')
    if not isinstance(info,dict):return None
    cumulative=info.get('total_token_usage');latest=info.get('last_token_usage')
    if not isinstance(cumulative,dict) or not isinstance(latest,dict):return None
    total=number(cumulative.get('total_tokens'))
    last=number(latest.get('total_tokens'))
    if total is None or last is None:return None
    try:
        at=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
        if at.timestamp()<time.time()-7*86400:return None
        day=at.astimezone(timezone.utc).strftime('%Y-%m-%d')
    except (KeyError,ValueError,TypeError):return None
    return day,int(total),int(last)


def project_token_breakdown(event):
    """Strict current Codex token schema, fail closed on unknown/malformed counters."""
    if not project_token_event(event):return None
    info=event['payload']['info'];vectors=[]
    for key in ('total_token_usage','last_token_usage'):
        usage=info[key];values=[usage.get(k) for k in ('input_tokens','output_tokens','cached_input_tokens','total_tokens')]
        if any(type(v)!=int or not 0<=v<=10**15 for v in values):return None
        inputs,outputs,cached,total=values
        if cached>inputs or inputs+outputs!=total:return None
        vectors.append((inputs,outputs,cached))
    if any(a>b for a,b in zip(vectors[1],vectors[0])):return None
    return tuple(vectors)


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
    collect_tokens=bool(config.get('localTokens',False) or collect_patterns)
    day=datetime.now(timezone.utc).strftime('%Y-%m-%d');store=Store(directory)
    items=[];threads=[]
    def fetch(ident):
        if ident=='codex': return collect_codex(day,config,collect_patterns,directory=directory,read_local_tokens=collect_tokens)
        if ident=='glm': return collect_glm(day,config,directory),[]
        return adapters.collect_extra(ident,directory,config),[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,enabled))
    for item,t in results:
        threads+=t
        if item['status']=='ready':
            item.setdefault('observedAt',int(time.time()));item['measurementDay']=day;store.persist(item)
        elif item['status']=='unavailable':
            cached=store.latest(item['id'])
            # Never reuse an account-specific Codex cache when current identity is unknown/mismatched.
            if item['id'] in ('codex','glm','kimi') and (not item.get('accountScope') or not cached or cached.get('accountScope')!=item['accountScope']):cached=None
            if cached:
                errors=item.get('sourceStatus',[]);item.update(cached);item['sourceStatus']=errors+['cached_previous_read']
                if item.get('measurementDay')!=day:item['todayTokens']=None
        items.append(item)
    codex=next((p for p in items if p['id']=='codex'),None)
    if collect_tokens and codex:
        for thread in threads:store.project_rollout(thread,include_tools=bool(collect_patterns))
        gaps=store.db.execute('SELECT count(*) FROM rollout_gaps WHERE at>=?',(int(time.time())-30*86400,)).fetchone()[0]
        codex['localTokenGaps']=gaps
        if gaps:codex.setdefault('sourceStatus',[]).append('local_tokens_backlog_skipped')
        store.persist_local_tokens()
        codex['localTokenProfile']=store.local_token_profile(day)
        if codex.get('todayTokens') is None:
            codex['todayTokens']=store.local_tokens(day);codex['todayTokenCoverage']='partial-local'
            codex['todayTokenStatus']='partial-local' if codex['todayTokens'] is not None else 'local-day-pending'
        else:codex['todayTokenCoverage']='account-reported'
    j=journal.Journal(directory)
    try:deep=analytics.report(j,enabled)
    finally:j.close()
    settings=store.settings()
    for item in items:
        item['subscription']=settings.get(item['id'],{'date':None,'kind':'renewal','source':'manual'}) if item['id']!='codex' or item.get('accountScope') else {'date':None,'kind':'renewal','source':'manual'}
    result={'analytics':deep,'generatedAt':int(time.time()),'providers':items,'catalog':adapters.CATALOG,'localPatterns':bool(collect_patterns),'localTokens':bool(config.get('localTokens',False)),
            'history':[x for x in store.history() if x['provider'] in enabled],
            'patterns':[x for x in store.patterns([t for p in items for t in p.get('tools',[])]) if x['provider'] in enabled and (x['provider']!='codex' or collect_patterns)],
            'patternCoverage':'Tool categories, partial local records; no per-tool token attribution',
            'privacy':'Local counters and sanitized journal metadata only; no raw payloads/code saved or uploaded'}
    store.db.close()
    return result


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,default=DEFAULT_STATE);p.add_argument('--debug',action='store_true',help='Print only a safe exception class to stderr, never its message or payload')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('snapshot');s.add_argument('--no-patterns',action='store_true')
    q=sub.add_parser('subscription');q.add_argument('--provider',choices=sorted(adapters.IDS),required=True);q.add_argument('--date',default='');q.add_argument('--kind',choices=['renewal','expiry','none'],required=True)
    sub.add_parser('catalog')
    sub.add_parser('limits')
    sub.add_parser('glm-key',help='Save/remove own Coding Plan key from bounded JSON on stdin; never use command-line key arguments')
    k=sub.add_parser('provider-key',help='Own GLM/Kimi key as bounded JSON on stdin only');k.add_argument('--provider',choices=['glm','kimi'],required=True)
    k.add_argument('--region',choices=['mainland-cn','global'],default='mainland-cn',help='Kimi account region; explicit endpoint, never automatic fallback')
    c=sub.add_parser('configure');c.add_argument('--providers',required=True);c.add_argument('--local-patterns',choices=['on','off'],default='off');c.add_argument('--local-tokens',choices=['on','off'])
    i=sub.add_parser('ingest');i.add_argument('--provider',choices=sorted(adapters.IDS),required=True);i.add_argument('--file',type=Path,required=True)
    h=sub.add_parser('hook');h.add_argument('--provider',choices=sorted(journal.PROVIDERS),required=True)
    h=sub.add_parser('hooks');h.add_argument('--provider',choices=sorted(instrumentation.NATIVE_EVENTS),required=True);h.add_argument('--action',choices=['install','remove'],required=True);h.add_argument('--observer-home',type=Path,help='Explicit isolated native config root for acceptance tests')
    h=sub.add_parser('journal');h.add_argument('--action',choices=['report','evidence','session','inventory','scan','annotate','declare','compare','export','review','asset','task','usage','compare-tasks','checks','check','health','backup'],default='report');h.add_argument('--session');h.add_argument('--provider',choices=sorted(journal.PROVIDERS),default='codex');h.add_argument('--skills-dir',type=Path,action='append',default=[]);h.add_argument('--config',type=Path);h.add_argument('--file',type=Path);h.add_argument('--label');h.add_argument('--variant');h.add_argument('--outcome',choices=['accepted','failed','rework','unknown'],default='unknown');h.add_argument('--before');h.add_argument('--after');h.add_argument('--finding');h.add_argument('--capability');h.add_argument('--kind',choices=['skill','tool','mcp'])
    h.add_argument('--status',choices=['open','actioned','dismissed'],default='open');h.add_argument('--reason',choices=['unspecified','script','skill','mcp','routing','retrieval','fix','not-applicable','duplicate'],default='unspecified');h.add_argument('--days',type=int,choices=[1,3,7],default=1)
    h.add_argument('--format',choices=['json','markdown'],default='json');h.add_argument('--language',choices=['en','ru'],default='en')
    h.add_argument('--cursor');h.add_argument('--limit',type=int,default=500)
    h.add_argument('--metadata',help='Bounded asset/task/usage/check counters; no raw payloads')
    h=sub.add_parser('mcp');h.add_argument('--allow-control',action='store_true')
    h=sub.add_parser('settings');h.add_argument('--update',action='store_true',help='Bounded JSON changes on stdin, no credentials')
    sub.add_parser('tls-check',help='Inspect actual TLS trust and verify a fixed public quota endpoint without any key')
    a=p.parse_args();os.umask(0o077)
    if a.command=='hook':
        j=None
        try:
            body=sys.stdin.buffer.read(journal.MAX_INPUT+1)
            if len(body)>journal.MAX_INPUT:raise ValueError('oversize')
            j=journal.Journal(a.state);j.record(a.provider,json.loads(body))
        except Exception:
            try:
                if j:j.reject(a.provider)
            except Exception:pass
        finally:
            if j:j.close()
        return
    if a.command=='mcp':mcp_server.serve(a.state,a.allow_control);return
    try:
        if a.command=='settings':
            from agent_control import settings,update_settings
            if a.update:
                body=sys.stdin.buffer.read(8193)
                if len(body)>8192:raise ValueError('oversize')
                result=update_settings(a.state,json.loads(body))
            else:result=settings(a.state)
        elif a.command=='tls-check':
            from providers import tls_check
            result=tls_check()
        elif a.command in ('glm-key','provider-key'):
            import provider_secrets
            body=sys.stdin.buffer.read(8193)
            if len(body)>8192:raise ValueError('oversize')
            result=provider_secrets.save_key(a.state,json.loads(body).get('key'),a.provider if a.command=='provider-key' else 'glm',a.region if a.command=='provider-key' else 'mainland-cn')
        elif a.command=='journal':result=journal_cli.run(a)
        elif a.command=='hooks':result=instrumentation.configure_hooks(a.provider,a.state,a.action=='install',home=a.observer_home)
        elif a.command=='subscription':
            s=Store(a.state);s.set_subscription(a.provider,a.date,a.kind);s.db.close();result={'saved':True}
        elif a.command=='catalog':result=adapters.CATALOG
        elif a.command=='limits':result=collect_codex(datetime.now(timezone.utc).strftime('%Y-%m-%d'),adapters.load_config(a.state),quota_only=True,directory=a.state)[0]
        elif a.command=='configure':
            enabled=list(dict.fromkeys(a.providers.split(','))) if a.providers else []
            if any(x not in adapters.IDS for x in enabled):raise ValueError('invalid_provider')
            from agent_control import update_settings
            changes={'enabledProviders':enabled,'localPatterns':a.local_patterns=='on'}
            if a.local_tokens is not None:changes['localTokens']=a.local_tokens=='on'
            result=update_settings(a.state,changes)
        elif a.command=='ingest':
            if a.file.is_symlink() or a.file.stat().st_size>2*1024*1024:raise ValueError('invalid_import')
            raw=json.loads(a.file.read_text(encoding='utf-8'));result=adapters.normalized(raw,a.provider)
            adapters.atomic_json(a.state/'imports'/f'{a.provider}.json',result);result={'saved':True}
        else:result=snapshot(a.state,False if a.no_patterns else None)
        print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False,allow_nan=False))
    except Exception as error:
        if a.debug:print('Agent Pulse: '+type(error).__name__,file=sys.stderr)
        print('{"error":"collector_unavailable"}');raise SystemExit(1)

if __name__=='__main__':main()
