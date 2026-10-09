"""Bounded local control. No secrets, native client configuration or model calls."""
from pathlib import Path
from contextlib import closing
import json
import sqlite3
from providers import IDS, load_config, patch_config

CONFIG_KEYS={'enabledProviders','localPatterns','localTokens','language','widgetScale','displayMode','metricMode','menuNumbers','menuFollowActive','topmost'}

def settings(directory):
    config=load_config(directory)
    # Unknown fields may hold provider locators; do not expose them to the agent.
    result={'config':{k:v for k,v in config.items() if k in CONFIG_KEYS},'localOnly':True,
            'credentials':'Enter provider keys in the app settings; never paste them into an agent chat.'}
    revision=config.get('configRevision',0)
    result['configRevision']=revision if type(revision)==int and 0<=revision<=2**53 else None
    result['subscriptions']={}
    path=Path(directory)/'metrics.sqlite'
    if Path(directory).is_symlink() or path.is_symlink():raise ValueError('symlink_state')
    if path.exists():
        # No Store/schema initialization or migrations on this read-only path.
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
            try:
                rows=db.execute('SELECT key,value FROM settings WHERE key IN ('+','.join('?' for _ in IDS)+')',tuple(IDS)).fetchall()
            except sqlite3.OperationalError as error:
                if str(error)!='no such table: settings':raise
                rows=[]
            result['subscriptions']={k:json.loads(v) for k,v in rows}
    return result

def update_settings(directory,changes):
    if not isinstance(changes,dict) or not changes or not set(changes)<=CONFIG_KEYS:raise ValueError('invalid_settings')
    for key,value in changes.items():
        if key=='enabledProviders':
            if not isinstance(value,list) or len(value)>len(IDS) or any(not isinstance(v,str) or v not in IDS for v in value):raise ValueError('invalid_providers')
        elif key in ('localPatterns','localTokens','menuNumbers','menuFollowActive','topmost'):
            if type(value) is not bool:raise ValueError('invalid_boolean')
        elif key=='widgetScale':
            if type(value) not in (int,float) or not .8<=value<=1:raise ValueError('invalid_scale')
        elif key=='language' and value not in ('en','ru'):raise ValueError('invalid_language')
        elif key=='metricMode' and value not in ('limits','today'):raise ValueError('invalid_metric')
        elif key=='displayMode' and value not in ('floating','compact','tray','menu'):raise ValueError('invalid_placement')
    changes=dict(changes)
    if 'enabledProviders' in changes:changes['enabledProviders']=list(dict.fromkeys(changes['enabledProviders']))
    revision=patch_config(directory,changes)
    return {'saved':True,'localOnly':True,'configRevision':revision}

def control(name,args,directory):
    if name=='pulse_configure' and set(args)=={'changes'}:return update_settings(directory,args['changes'])
    if name=='pulse_subscription' and set(args)=={'provider','date','kind'}:
        from collector import Store
        store=Store(Path(directory))
        try:store.set_subscription(args['provider'],args['date'],args['kind'])
        finally:store.db.close()
        return {'saved':True,'source':'manual'}
    from journal import Journal
    j=Journal(directory)
    try:
        if name in {'pulse_register_asset','pulse_record_task','pulse_record_usage'}:
            from efficiency import register_asset,record_task,ingest_usage
            return {'pulse_register_asset':register_asset,'pulse_record_task':record_task,'pulse_record_usage':ingest_usage}[name](j,args)
        if name=='pulse_review_finding' and set(args)=={'findingId','status','reason','days'}:
            from finding_review import review_finding
            return review_finding(j,args['findingId'],args['status'],args['reason'],args['days'])
        if name=='pulse_annotate_session' and set(args)=={'sessionId','label','outcome','variant'}:
            j.annotate(args['sessionId'],args['label'],args['outcome'],args['variant']);return {'saved':True,'evidence':'manual review'}
    finally:j.close()
    raise ValueError('control_not_allowed')
