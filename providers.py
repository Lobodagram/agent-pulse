"""Explicit provider catalog and read-only adapters. No dynamic plugin code execution."""
from datetime import datetime, timezone
import json
import os
import re
import ssl
import sys
from pathlib import Path
import time
import urllib.request
from urllib.parse import urlparse

CATALOG=[
 {'id':'codex','name':'Codex','mode':'native','support':'Native account quotas, account tokens and optional partial local events'},
 {'id':'glm','name':'GLM / ZCode','mode':'native','support':'Native local ZCode statistics; opt-in Z.ai Coding Plan quotas with own key'},
 {'id':'claude','name':'Claude Code','mode':'statusline','support':'Official status-line bridge: quotas and context size, not cumulative token spend'},
 {'id':'kimi','name':'Kimi Code','mode':'api','support':'Opt-in read-only quota API; own key in local Secrets.json; no token-spend API assumed'},
 {'id':'qwen','name':'Qwen Code','mode':'loopback','support':'Opt-in existing local qwen serve usage dashboard; no daemon is started'},
 *[{'id':i,'name':n,'mode':'import','support':'Normalized local metrics import; automatic account quota adapter not available'} for i,n in
   [('gemini','Gemini CLI'),('cursor','Cursor'),('copilot','GitHub Copilot'),('windsurf','Windsurf'),('deepseek','DeepSeek'),('openrouter','OpenRouter')]],
]
IDS={x['id'] for x in CATALOG}

def load_config(directory):
    path=Path(directory)/'config.json'
    if not path.exists():return {'enabledProviders':['codex','glm'],'localPatterns':False,'localTokens':False}
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('invalid_config')
    raw=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw,dict):raise ValueError('invalid_config')
    enabled=raw.get('enabledProviders',['codex','glm'])
    if not isinstance(enabled,list) or any(x not in IDS for x in enabled):raise ValueError('invalid_providers')
    if 'localTokens' in raw and not isinstance(raw['localTokens'],bool):raise ValueError('invalid_local_tokens')
    raw['enabledProviders']=list(dict.fromkeys(enabled))
    return raw

def atomic_json(path,value):
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink_not_allowed')
    if path.parent.is_symlink():raise ValueError('symlink_parent')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False)
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

class ConfigBusy(TimeoutError):
    """A cooperating writer holds the local preference lock; retry later."""

def patch_config(directory,changes):
    """Serialize all cooperating UI/CLI/MCP patches across atomic replacements.

    Different fields merge; for the same field the last completed patch wins.
    The lock file must remain in place: unlinking it would split waiting writers.
    """
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('symlink_state')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/'.config.lock'
    if path.is_symlink():raise ValueError('symlink_lock')
    fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'r+b') as lock:
        if os.name=='nt':
            import msvcrt
            # Byte-range locking supports empty files; do not write into a
            # region another process may already have locked beyond EOF.
        else:
            import fcntl
            os.fchmod(lock.fileno(),0o600)
        deadline=time.monotonic()+1
        while True:
            try:
                if os.name=='nt':
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise ConfigBusy('config_busy')
                time.sleep(.01)
            except OSError:
                if os.name!='nt':raise
                if time.monotonic()>=deadline:raise ConfigBusy('config_busy')
                time.sleep(.01)
        try:
            config=load_config(directory)
            revision=config.get('configRevision',0)
            if type(revision)!=int or not 0<=revision<2**53:raise ValueError('invalid_config_revision')
            config.update(changes);config['configRevision']=revision+1
            atomic_json(directory/'config.json',config)
            return config['configRevision']
        finally:
            if os.name=='nt':
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock,fcntl.LOCK_UN)

def empty(ident):
    spec=next(x for x in CATALOG if x['id']==ident)
    return {'id':ident,'name':spec['name'],'status':'unavailable','quotas':[],'daily':[],
            'todayTokens':None,'resetCredits':None,'sourceStatus':['not_configured'],
            'tokenSource':spec['mode'],'tokenCoverage':spec['support']}

def normalized(raw,ident):
    from collector import number,safe_name
    if not isinstance(raw,dict):raise ValueError('invalid_metrics')
    p=empty(ident);p['status']='ready';p['sourceStatus']=['local_metrics_import']
    for key in ['todayTokens','periodTokens','sessions','contextTokens']:p[key]=number(raw.get(key))
    p['tokenSource']='Local normalized metrics import';p['tokenCoverage']='user-exported, partial'
    for q in (raw.get('quotas') if isinstance(raw.get('quotas'),list) else [])[:8]:
        if not isinstance(q,dict):continue
        pct=number(q.get('remainingPercent'))
        p['quotas'].append({'bucket':ident,'kind':safe_name(q.get('kind','primary')),
                           'durationMinutes':number(q.get('durationMinutes')),
                           'remainingPercent':min(100,pct) if pct is not None else None,
                           'resetsAt':number(q.get('resetsAt'))})
    for r in (raw.get('daily') if isinstance(raw.get('daily'),list) else [])[:366]:
        if not isinstance(r,dict):continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(r.get('date',''))):continue
        try:datetime.strptime(r.get('date',''),'%Y-%m-%d')
        except (ValueError,TypeError):continue
        p['daily'].append({'date':r['date'],'tokens':number(r.get('tokens'))})
    p['tools']=[]
    for r in (raw.get('tools') if isinstance(raw.get('tools'),list) else [])[:100]:
        if not isinstance(r,dict):continue
        name=safe_name(r.get('name'));count=number(r.get('count'))
        if name=='other' or count is None:continue
        p['tools'].append({'provider':ident,'name':name,'count':count,'errors':number(r.get('errors')),'source':'local metrics import'})
    p['observedAt']=number(raw.get('observedAt'))
    if p['observedAt'] is None:p['status']='stale';p['sourceStatus']=['import_timestamp_missing']
    elif p['observedAt']>time.time()+60 or time.time()-p['observedAt']>600:p['status']='stale';p['sourceStatus']=['import_stale']
    return p

def claude_statusline(raw):
    from collector import number
    p=empty('claude');p.update(status='ready',sourceStatus=['official_statusline_bridge'],tokenSource='Claude status-line snapshot',tokenCoverage='context gauge; no cumulative spend',todayTokenCoverage='not-reported')
    context=raw.get('context_window') or {}
    inp=number(context.get('total_input_tokens'));out=number(context.get('total_output_tokens'))
    p['contextTokens']=inp+out if inp is not None and out is not None else None
    limits=raw.get('rate_limits') or {}
    for key,mins in [('five_hour',300),('seven_day',10080)]:
        q=limits.get(key) or {};used=number(q.get('used_percentage'))
        if not q:continue
        p['quotas'].append({'bucket':'claude','kind':'primary' if mins==300 else 'secondary','durationMinutes':mins,'remainingPercent':max(0,min(100,100-used)) if used is not None else None,'resetsAt':number(q.get('resets_at'))})
    # Never read transcript_path, session_name, cwd, prompt_id, messages or credentials.
    p['observedAt']=int(time.time())
    return p

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def verified_http_context():
    context=ssl.create_default_context()
    # Frozen python.org macOS builds retain a framework CA path absent on many Macs.
    # Add the OS-owned roots; certificate and hostname verification remain required.
    if sys.platform=='darwin' and getattr(sys,'frozen',False):
        roots=Path('/etc/ssl/cert.pem')
        if roots.is_file():context.load_verify_locations(cafile=str(roots))
    return context

def get_json(url,headers=None):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=verified_http_context()))
    with opener.open(urllib.request.Request(url,headers=headers or {},method='GET'),timeout=12) as r:
        body=r.read(2*1024*1024+1)
        if len(body)>2*1024*1024:raise ValueError('response_too_large')
        x=json.loads(body)
        if not isinstance(x,dict):raise ValueError('invalid_response')
        return x

def kimi_quotas(raw):
    from sanitizers import number
    if not isinstance(raw,dict) or not isinstance(raw.get('limits',[]),list) or len(raw.get('limits',[]))>8:raise ValueError('quota_schema_unavailable')
    p=empty('kimi');p.update(status='ready',sourceStatus=['quota_api'],tokenSource='Kimi Code quota API',tokenCoverage='quota units, not token spend',todayTokenCoverage='not-reported')
    def minutes(row):
        window=row.get('window')
        window=window if isinstance(window,dict) else row
        duration=number(window.get('duration'));unit=window.get('timeUnit')
        factors={'MINUTE':1,'MINUTES':1,'HOUR':60,'HOURS':60,'DAY':1440,'DAYS':1440,'SECOND':1/60,'SECONDS':1/60}
        if duration is None or unit not in factors:return None
        result=duration*factors[unit]
        return int(result) if result==int(result) and 0<result<=366*1440 else None
    rows=[(raw.get('usage'),10080)]
    for row in raw.get('limits',[])[:8]:
        if not isinstance(row,dict):continue
        detail=row.get('detail')
        detail=detail if isinstance(detail,dict) else row
        outer=minutes(row);inner=minutes(detail)
        if outer is not None and inner is not None and outer!=inner:raise ValueError('quota_schema_unavailable')
        rows.append((detail,outer or inner))
    for row,mins in rows:
        if not isinstance(row,dict):continue
        limit=number(row.get('limit'));used=number(row.get('used'));remaining=number(row.get('remaining'))
        if remaining is None and limit is not None and used is not None and used<=limit:remaining=limit-used
        percent=remaining/limit*100 if limit and remaining is not None and remaining<=limit else None
        if used is not None and limit is not None and (used>limit or remaining is not None and abs(remaining+used-limit)>1e-8):percent=None
        reset=next((row[k] for k in ['reset_at','resetAt','reset_time','resetTime'] if row.get(k) is not None),None)
        if isinstance(reset,str):
            try:
                parsed=datetime.fromisoformat(reset.replace('Z','+00:00'))
                reset=parsed.timestamp() if parsed.tzinfo else None
            except ValueError:reset=None
        reset=number(reset)
        reset=reset if reset is not None and 946684800<=reset<=4102444800 else None
        if limit is None and percent is None:continue
        p['quotas'].append({'bucket':'kimi','kind':'secondary' if mins==10080 else 'primary','durationMinutes':mins,'remainingPercent':percent,'resetsAt':reset})
    # Duplicate declared windows are ambiguous; do not choose one account row.
    for q in p['quotas']:
        if q['durationMinutes'] is not None and sum(r['durationMinutes']==q['durationMinutes'] for r in p['quotas'])>1:q.update(remainingPercent=None,resetsAt=None)
    if not any(q['remainingPercent'] is not None for q in p['quotas']):p.update(status='unavailable',sourceStatus=['quota_fields_unavailable'])
    return p

def collect_extra(ident,directory,config):
    try:
        path=Path(directory)/'imports'/f'{ident}.json'
        if path.is_file():
            if path.parent.is_symlink() or path.is_symlink() or path.stat().st_size>2*1024*1024:raise ValueError('invalid_import')
            p=normalized(json.loads(path.read_text()),ident)
            if ident=='claude':p['tokenSource']='Claude official status-line bridge';p['tokenCoverage']='context size, not token spend';p['todayTokens']=None;p['daily']=[];p['periodTokens']=None
            if p.get('observedAt') is not None and datetime.fromtimestamp(p['observedAt'],timezone.utc).strftime('%Y-%m-%d') != datetime.now(timezone.utc).strftime('%Y-%m-%d'):p['todayTokens']=None
            return p
        if ident=='kimi':
            from provider_secrets import secrets
            connection=secrets(directory).get('kimi') or {}
            key=connection.get('api_key')
            if not isinstance(key,str) or not key:return empty(ident)
            if len(key)>4096 or any(c.isspace() for c in key):raise ValueError('invalid_key')
            endpoints={'mainland-cn':'https://api.kimi.com/coding/v1/usages','global':'https://api.kimi.ai/coding/v1/usages'}
            endpoint=endpoints.get(connection.get('region','mainland-cn'))
            if endpoint is None:raise ValueError('quota_schema_unavailable')
            return kimi_quotas(get_json(endpoint,{'Authorization':'Bearer '+key}))
        if ident=='qwen' and config.get('qwenBaseUrl'):
            u=urlparse(config['qwenBaseUrl'])
            if u.scheme!='http' or u.hostname not in ('127.0.0.1','::1') or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:raise ValueError('loopback_required')
            raw=get_json(config['qwenBaseUrl'].rstrip('/')+'/usage/dashboard?range=today&heatmapDays=30')
            return qwen_dashboard(raw)
        return empty(ident)
    except Exception as error:
        from glm_quota import failure_category
        p=empty(ident);p['sourceStatus']=['adapter_unavailable',failure_category(error)];return p

def qwen_dashboard(raw):
    from collector import number
    p=empty('qwen');p.update(status='ready',sourceStatus=['local_dashboard'],tokenSource='Qwen local usage dashboard',tokenCoverage='native aggregate, local')
    # Shape documented from the official usage-dashboard-service contract; no transcripts.
    summary=raw.get('summary') or {}
    p['todayTokens']=number(summary.get('totalTokens'))
    p['sessions']=number(summary.get('sessions'))
    days={}
    heatmap=raw.get('heatmap') or {}
    if isinstance(heatmap,dict):
        for date,r in list(heatmap.items())[:366]:
            if isinstance(r,dict):days[date]=number(r.get('tokens'))
    for r in (raw.get('daily') or [])[:366]:
        if isinstance(r,dict):days[r.get('date')]=number(r.get('tokens'))
    for date,tokens in days.items():
        try:datetime.strptime(date,'%Y-%m-%d')
        except (ValueError,TypeError):continue
        p['daily'].append({'date':date,'tokens':tokens})
    p['tools']=[]
    from collector import safe_name
    for r in (raw.get('skills') or [])[:100]:
        if not isinstance(r,dict):continue
        name=safe_name(r.get('name'));count=number(r.get('count'))
        if name!='other' and count is not None:p['tools'].append({'provider':'qwen','name':'skill.'+name,'count':count,'errors':None,'source':'Qwen local aggregate'})
    if p['todayTokens'] is None:p.update(status='unavailable',sourceStatus=['dashboard_schema_unavailable'])
    return p


def tls_check():
    """Explicit diagnostic: fixed HTTPS GET, no key and no inference endpoint."""
    from urllib.error import HTTPError
    context=verified_http_context()
    if context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname:raise ValueError('unsafe_tls_context')
    roots=context.cert_store_stats()['x509_ca']
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=context))
    request=urllib.request.Request('https://api.z.ai/api/monitor/usage/quota/limit',headers={'Accept':'application/json'},method='GET')
    try:
        with opener.open(request,timeout=12) as response:status=response.status
    except HTTPError as error:status=error.code
    return {'verifiedTLS':True,'hostnameVerified':True,'caCertificates':roots,'httpStatus':status,'credentialSent':False}
