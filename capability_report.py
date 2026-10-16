"""Counts approved capability identities; loading, invocation and declaration differ."""
import time

def observation_coverage(j,calls,providers=None):
    """Counts missing evidence without guessing which unknown skill was used."""
    rows=[]
    allowed=set(providers) if providers is not None else {c['provider'] for c in calls}
    for provider in sorted(allowed):
        selected=[c for c in calls if c['provider']==provider]
        skill_calls=[c for c in selected if c['tool'].lower() in {'skill','use_skill'}]
        successes=[c for c in skill_calls if c['paired'] and c['outcome']=='success']
        ids={c['id'] for c in selected}
        evidence=[dict(r) for r in j.db.execute("SELECT call,evidence FROM capability_evidence WHERE provider=? AND kind='skill'",(provider,)) if r['call'] in ids]
        mapped={r['call'] for r in evidence if r['evidence']=='invoked'}
        loaded={r['call'] for r in evidence if r['evidence']=='loaded'}
        rows.append({'provider':provider,'skillToolCalls':len(skill_calls),
                     'successfulSkillToolCalls':len(successes),
                     'mappedSkillToolCalls':sum(c['id'] in mapped for c in successes),
                     'unmappedSuccessfulSkillToolCalls':sum(c['id'] not in mapped for c in successes),
                     'skillReadCalls':len(loaded),'state':'observed' if mapped or loaded else 'not-observed',
                     'nonUseEstablished':False,'versionVerified':False,
                     'basis':'Successful native Skill and exact catalog file reads; reading is not application.'})
    return rows

def capabilities(j,providers=None):
    inventory={(r['provider'],r['id'],r['kind']):dict(r) for r in j.db.execute('SELECT * FROM inventory')}
    usage={}
    for row in j.db.execute('SELECT c.provider,c.id,c.kind,c.evidence,coalesce(s.source,\'legacy\') AS source,count(*) AS n,max(c.at) AS last FROM capability_evidence c LEFT JOIN capability_source s ON c.provider=s.provider AND c.session=s.session AND c.call=s.call AND c.id=s.id AND c.evidence=s.evidence WHERE c.at>=? GROUP BY c.provider,c.id,c.kind,c.evidence,s.source',(time.time()-30*86400,)):
        key=(row['provider'],row['id'],row['kind']);u=usage.setdefault(key,{'loaded':0,'invoked':0,'declared':0,'lastSeen':None,'evidenceSources':{}})
        u[row['evidence']]+=row['n'];u['lastSeen']=max(u['lastSeen'] or 0,row['last'])
        u['evidenceSources'][row['source']]=u['evidenceSources'].get(row['source'],0)+row['n']
    rows=[]
    for key in sorted(set(inventory)|set(usage)):
        provider,name,kind=key
        if providers is not None and provider not in providers:continue
        i=inventory.get(key,{});u=usage.get(key,{'loaded':0,'invoked':0,'declared':0,'lastSeen':None})
        observed=i.get('observed')
        rows.append({'provider':provider,'id':name,'kind':kind,'status':i.get('status','not-in-current-inventory'),
                     'inventoryFresh':bool(observed and 0<=time.time()-observed<7*86400),
                     'evidenceStatus':'invoked' if u['invoked'] else 'declared' if u['declared'] else 'loaded-only' if u['loaded'] else 'not-observed',
                     **u,'coverage':'partial; no observed use does not establish non-use'})
    return rows[:1000]
