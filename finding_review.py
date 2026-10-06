"""Manual finding decisions and equal-window observational rechecks, no causation."""
import re
import time
from analytics import findings

STATUSES={'open','actioned','dismissed'}
REASONS={'unspecified','script','skill','mcp','routing','retrieval','fix','not-applicable','duplicate'}

def window_summary(j,calls,finding_id):
    candidate=next((f for f in findings(j,calls,summary_only=True) if f['id']==finding_id),None)
    return {'observedCalls':len(calls),'pairedCalls':sum(c['paired'] for c in calls),
            'knownTurns':len({(c['session'],c['turn']) for c in calls if c['turn_source']!='unknown'}),
            'unknownOutcomes':sum(c['outcome']=='unknown' for c in calls),
            'qualifies':candidate is not None,'occurrences':candidate['occurrences'] if candidate else None}

def in_window(c,begin,end):
    at=c['startedAt'] if c['startedAt'] is not None else c['endedAt']
    return at is not None and begin<=at<end

def review_finding(j,finding_id,status,reason='unspecified',days=1):
    if not isinstance(finding_id,str) or not re.fullmatch('[a-f0-9]{32}',finding_id):raise ValueError('invalid_finding')
    if status not in STATUSES or reason not in REASONS or type(days)!=int or days not in {1,3,7}:raise ValueError('invalid_review')
    # Reopen/dismiss existing decisions even if the finding no longer qualifies.
    old=j.db.execute('SELECT * FROM finding_review WHERE id=?',(finding_id,)).fetchone()
    calls=j.calls();candidate=next((f for f in findings(j,calls) if f['id']==finding_id),None)
    if not candidate:
        if old and status in {'open','dismissed'}:
            j.db.execute('UPDATE finding_review SET status=?,reason=? WHERE id=?',(status,reason,finding_id));j.db.commit();return {'saved':True,'localOnly':True}
        raise ValueError('finding_not_found')
    reference=next(c for c in calls if c['id'] in candidate['evidenceIds'])
    provider,project=reference['provider'],reference['project'];at=time.time();seconds=days*86400
    subset=[c for c in calls if c['provider']==provider and c['project']==project and in_window(c,at-seconds,at)]
    import json
    baseline=window_summary(j,subset,finding_id)
    j.db.execute('INSERT OR REPLACE INTO finding_review VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 (finding_id,provider,project,candidate['kind'],status,reason,at,seconds,candidate['title'],candidate['titleRu'],json.dumps(baseline)))
    j.db.execute('DELETE FROM finding_review WHERE rowid IN (SELECT rowid FROM finding_review ORDER BY at DESC LIMIT -1 OFFSET 200)')
    j.db.commit();return {'saved':True,'localOnly':True}

def reviewed_findings(j,calls,providers=None):
    import json
    result=[];now=time.time()
    rows=j.db.execute('SELECT * FROM finding_review ORDER BY at DESC,id').fetchall()
    rows=[r for r in rows if providers is None or r['provider'] in providers]
    for r in rows[:30]:
        baseline=json.loads(r['baseline']);end=r['at']+r['seconds'];after=None
        state='not-requested' if r['status']!='actioned' else 'awaiting-window'
        if r['status']=='actioned' and now>=end:
            subset=[c for c in calls if c['provider']==r['provider'] and c['project']==r['project'] and in_window(c,r['at'],end)]
            after=window_summary(j,subset,r['id'])
            if not baseline['qualifies']:state='baseline-not-qualifying'
            elif baseline['knownTurns']<3 or after['knownTurns']<3:state='insufficient-evidence'
            elif not after['qualifies']:state='not-qualifying-in-observed-window'
            else:state='observational-lower' if after['occurrences']<baseline['occurrences'] else 'observational-higher' if after['occurrences']>baseline['occurrences'] else 'observational-same'
        result.append({'findingId':r['id'],'provider':r['provider'],'kind':r['kind'],'title':r['title'],'titleRu':r['title_ru'],
                       'status':r['status'],'reason':r['reason'],'reviewedAt':r['at'],'windowHours':r['seconds']//3600,
                       'afterWindowEndsAt':end,'baseline':baseline,'after':after,'recheckState':state,
                       'causalClaim':False,'tokenSavings':None,'completeCoverage':False,
                       'limitations':['Equal time windows do not establish equal tasks/models or causation.',
                                      'Not qualifying does not mean zero occurrences, resolution or complete coverage.']})
    return result
