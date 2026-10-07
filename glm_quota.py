"""Opt-in Coding Plan quotas. No native credentials, sessions or reset operations."""
import time
import ssl
from urllib.error import HTTPError, URLError
from sanitizers import number

URL='https://api.z.ai/api/monitor/usage/quota/limit'

from provider_secrets import secrets, save_key

def windows(raw):
    if not isinstance(raw,dict) or isinstance(raw.get('code'),bool) or raw.get('code') not in (None,0,200) or raw.get('success') is False:raise ValueError('quota_response_unavailable')
    data=raw.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('limits'),list):raise ValueError('quota_schema_unavailable')
    result=[]
    for kind,unit,count,minutes in [('primary',3,5,300),('secondary',6,1,10080)]:
        rows=[r for r in data['limits'][:32] if isinstance(r,dict) and r.get('type') in ('TOKENS_LIMIT','CREDIT_LIMIT') and type(r.get('unit')) is int and r['unit']==unit and (type(r.get('number')) in (int,float) and r.get('number')==count or unit==6 and r.get('number') is None)]
        row=rows[0] if len(rows)==1 else {}
        used=number(row.get('percentage'));reset=number(row.get('nextResetTime'))
        # The native quota contract uses epoch milliseconds. Reject other units.
        reset=reset/1000 if reset is not None and 946684800000<=reset<=4102444800000 else None
        result.append({'bucket':'glm','kind':kind,'durationMinutes':minutes,'remainingPercent':100-used if used is not None and used<=100 else None,'resetsAt':reset})
    if not any(q['remainingPercent'] is not None for q in result):raise ValueError('quota_fields_unavailable')
    return result

def failure_category(error):
    """Fixed labels only; never exception messages, response bodies or key data."""
    if isinstance(error,HTTPError):
        return 'authentication' if error.code in (401,403) else 'remote'
    if isinstance(error,ssl.SSLError):return 'tls'
    if isinstance(error,URLError):
        return 'tls' if isinstance(error.reason,ssl.SSLError) else 'network'
    if isinstance(error,(TimeoutError,ConnectionError,OSError)):return 'network'
    if isinstance(error,(ValueError,TypeError,KeyError)):return 'schema'
    return 'unavailable'

def collect(directory):
    result={'quotas':[],'quotaObservedAt':None,'quotaStatus':'unavailable','quotaSource':'Z.ai Coding Plan · separately configured key'}
    phase='configuration'
    try:
        key=(secrets(directory).get('glm') or {}).get('api_key')
        if not isinstance(key,str) or not key:return result | {'quotaStatus':'not-configured'}
        if len(key)>4096 or any(c.isspace() for c in key):raise ValueError('invalid_key')
        from providers import get_json
        phase='remote'
        result['quotas']=windows(get_json(URL,{'Authorization':key,'Accept':'application/json'}))
        result.update(quotaStatus='ready',quotaObservedAt=int(time.time()))
    except Exception as error:
        # A failed read must not reuse the previous key/account's quota.
        result.update(quotas=[],quotaStatus='unavailable',quotaObservedAt=None,quotaError=phase if phase=='configuration' else failure_category(error))
    return result
