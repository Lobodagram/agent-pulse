"""Display only reported quota percentages; never infer them from token counts."""
import math

NAMES={'codex':'Cdx','glm':'GLM','claude':'Cl','kimi':'Kimi','qwen':'Qwen'}

def window_label(minutes,ru=False):
    if not isinstance(minutes,(int,float)) or isinstance(minutes,bool) or not math.isfinite(minutes) or minutes<=0 or minutes>525600:return 'окно' if ru else 'win'
    if minutes%1440==0:return str(int(minutes/1440))+('д' if ru else 'd')
    if minutes%60==0:return str(int(minutes/60))+('ч' if ru else 'h')
    return str(int(minutes))+('м' if ru else 'm')

def provider_line(provider,ru=False):
    name=NAMES.get(provider.get('id'),str(provider.get('name') or provider.get('id') or '?')[:5])
    values=[]
    for q in provider.get('quotas',[])[:2]:
        v=q.get('remainingPercent');valid=isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<=v<=100
        values.append(window_label(q.get('durationMinutes'),ru)+' '+(str(math.floor(v))+'%' if valid else '—'))
    prefix='~' if provider.get('status')=='stale' else ''
    return prefix+name+' '+(' · '.join(values) if values else '—')

def quota_pages(providers,ru=False,size=3):
    lines=[provider_line(p,ru) for p in providers]
    return [lines[i:i+size] for i in range(0,len(lines),size)] or [[]]

def tray_tooltip(providers,ru=False,limit=127):
    rows=[provider_line(p,ru) for p in providers];kept=[]
    for i,line in enumerate(rows):
        suffix='\n+'+str(len(rows)-i-1) if i+1<len(rows) else ''
        if len('\n'.join(['Agent Pulse']+kept+[line])+suffix)>limit:break
        kept.append(line)
    if len(kept)<len(rows):kept.append('+'+str(len(rows)-len(kept)))
    return '\n'.join(['Agent Pulse']+kept)
