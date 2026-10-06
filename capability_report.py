"""Counts approved capability identities; loading, invocation and declaration differ."""
import time

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
