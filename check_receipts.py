"""Allowlisted helper counters, not native tool results or task acceptance."""
import json
import math
import re
import statistics
import time

OPERATIONS = {'workflow-check', 'release-preflight', 'ci-summary', 'mesh-topology', 'mesh-compare', 'slicer-project'}
GATES = {'unit-tests', 'syntax', 'privacy-export', 'links', 'archives', 'source-stable', 'geometry', 'units', 'execution'}
STATUSES = {'started', 'success', 'failed', 'unknown', 'interrupted'}
LIMIT = 5000
GROUP_LIMIT = 50

def operation_metrics(rows, now):
    """Reported helper cohorts, independent of native outcomes or task acceptance."""
    grouped={}
    for row in rows:
        grouped.setdefault((row['provider'],row['operation'],row['version']),[]).append(row)
    groups=[]
    for (provider,operation,version), cohort in grouped.items():
        known=[r for r in cohort if r['status'] in {'success','failed'} and not r['conflict']]
        timed=[(r['ended']-r['started'])*1000 for r in known if r['begun'] and r['ended'] is not None]
        successes=sum(r['status']=='success' for r in known)
        failed_gates={}
        for r in cohort:
            if r['ended'] is not None and not r['conflict']:
                for gate,status in json.loads(r['gates']).items():
                    if status=='failed':failed_gates[gate]=failed_gates.get(gate,0)+1
        groups.append({'provider':provider,'operation':operation,'version':version,'runs':len(cohort),
            'knownResults':len(known),'successes':successes,'failures':len(known)-successes,
            'knownResultRate':len(known)/len(cohort),'successRate':successes/len(known) if known else None,
            'pendingRuns':sum(r['status']=='started' for r in cohort),
            'staleRuns':sum(r['status']=='started' and now-r['started']>600 for r in cohort),
            'interruptedRuns':sum(r['status']=='interrupted' and not r['conflict'] for r in cohort),
            'unknownRuns':sum(r['status']=='unknown' for r in cohort),
            'conflicts':sum(r['conflict'] for r in cohort),
            'finishWithoutStart':sum(r['ended'] is not None and not r['begun'] for r in cohort),
            'timedRuns':len(timed),'medianElapsedMs':statistics.median(timed) if timed else None,
            'failedGates':failed_gates,'lastStartedAt':max(r['started'] for r in cohort)})
    groups.sort(key=lambda r:(-r['lastStartedAt'],r['provider'],r['operation'],r['version']))
    return groups[:GROUP_LIMIT],len(groups)

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS check_run(id TEXT PRIMARY KEY,provider TEXT,operation TEXT,version TEXT,
      started REAL,ended REAL,status TEXT,digest TEXT,gates TEXT,conflict INTEGER DEFAULT 0,begun INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS collection_counter(key TEXT PRIMARY KEY,value INTEGER,started REAL);
    ''')
    for key in ('expired-events', 'capped-events', 'expired-checks'):
        db.execute('INSERT OR IGNORE INTO collection_counter VALUES (?,0,?)',(key,time.time()))

def receipt(j,spec):
    from journal import PROVIDERS
    from efficiency import version_name
    required={'runId','provider','operation','version','startedAt','status'}
    if not isinstance(spec,dict) or not required<=set(spec) or set(spec)-required-{'endedAt','sourceDigest','gates'}:
        raise ValueError('invalid_check_receipt')
    if not isinstance(spec['runId'],str) or not re.fullmatch('[a-f0-9]{32}',spec['runId']):raise ValueError('invalid_check_id')
    provider=spec['provider'];op=spec['operation'];status=spec['status'];version=version_name(spec['version'])
    if not all(isinstance(v,str) for v in (provider,op,status)) or provider not in PROVIDERS or op not in OPERATIONS or status not in STATUSES:raise ValueError('invalid_check_receipt')
    start=spec['startedAt'];end=spec.get('endedAt');now=time.time()
    def finite(v):return type(v) in (int,float) and math.isfinite(v)
    if not finite(start) or not now-30*86400<=start<=now+60:raise ValueError('invalid_check_time')
    if status=='started':
        if end is not None or spec.get('gates') or spec.get('sourceDigest'):raise ValueError('invalid_started_check')
    elif not finite(end) or not start<=end<=min(now+60,start+86400):raise ValueError('invalid_check_time')
    digest=spec.get('sourceDigest','')
    if not isinstance(digest,str) or digest and not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('invalid_check_digest')
    gates=spec.get('gates',{})
    if not isinstance(gates,dict) or not set(gates)<=GATES or any(not isinstance(v,str) or v not in {'passed','failed','unknown'} for v in gates.values()):
        raise ValueError('invalid_check_gates')
    if status=='success' and ('failed' in gates.values() or 'unknown' in gates.values()):raise ValueError('conflicting_check_status')
    j.prune()
    rid=j.digest('check-run',[provider,spec['runId']]);body=json.dumps(gates,sort_keys=True,separators=(',',':'))
    with j.db:
        j.db.execute('BEGIN IMMEDIATE')
        old=j.db.execute('SELECT * FROM check_run WHERE id=?',(rid,)).fetchone()
        if old and (old['provider'],old['operation'],old['version'],old['started'])!=(provider,op,version,start):
            raise ValueError('check_identity_is_immutable')
        if not old:
            if j.db.execute('SELECT count(*) FROM check_run').fetchone()[0]>=LIMIT:raise ValueError('check_limit')
            j.db.execute('INSERT INTO check_run VALUES (?,?,?,?,?,?,?,?,?,0,?)',(rid,provider,op,version,start,end,status,digest,body,int(status=='started')))
        elif old['conflict'] or status=='started':pass
        elif old['status']=='started':
            j.db.execute('UPDATE check_run SET ended=?,status=?,digest=?,gates=? WHERE id=?',(end,status,digest,body,rid))
        elif (old['ended'],old['status'],old['digest'],old['gates'])!=(end,status,digest,body):
            j.db.execute("UPDATE check_run SET status='unknown',digest='',gates='{}',conflict=1 WHERE id=?",(rid,))
    return {'saved':True,'localOnly':True,'runId':rid,'provenance':'helper-reported; not native outcome or human acceptance'}

def check_report(j,providers=None):
    now=time.time()
    rows=[dict(r) for r in j.db.execute('SELECT * FROM check_run WHERE started>=? ORDER BY started DESC',(now-30*86400,))
          if providers is None or r['provider'] in providers]
    operations,group_count=operation_metrics(rows,now)
    known=sum(r['status'] in {'success','failed'} and not r['conflict'] for r in rows)
    ended=sum(r['ended'] is not None for r in rows)
    public=[]
    for r in rows[:20]:
        r['gates']=json.loads(r['gates']);r['elapsedMs']=(r['ended']-r['started'])*1000 if r['ended'] is not None and not r['conflict'] else None
        public.append(r)
    providers_seen=sorted({r['provider'] for r in rows})
    by_provider=[{'provider':p,'runs':sum(r['provider']==p for r in rows),'knownResults':sum(r['provider']==p and r['status'] in {'success','failed'} and not r['conflict'] for r in rows)} for p in providers_seen]
    return {'byProvider':by_provider,'byOperationVersion':operations,'operationVersionCount':group_count,
            'operationVersionsTruncated':group_count>GROUP_LIMIT,
            'runs':len(rows),'knownResults':known,'finishedRuns':ended,'knownResultRate':known/len(rows) if rows else None,
            'startsObserved':sum(r['begun'] for r in rows),
            'finishWithoutStart':sum(r['ended'] is not None and not r['begun'] for r in rows),
            'pendingRuns':sum(r['status']=='started' for r in rows),
            'staleRuns':sum(r['status']=='started' and now-r['started']>600 for r in rows),
            'conflicts':sum(r['conflict'] for r in rows),'recent':public,'truncated':len(rows)>20,
            'coverage':'explicit helper receipts only; reporter-supplied, not independent verification',
            'nativeOutcomesChanged':0,'humanAcceptance':None}

class Reporter:
    """Optional telemetry never changes the helper's return value or failure."""
    def __init__(self,state,provider,operation,version):
        import uuid
        self.state=state;self.spec={'runId':uuid.uuid4().hex,'provider':provider,'operation':operation,
                                  'version':version,'startedAt':time.time(),'status':'started'}
        self.terminal=None
        self.saved=self._write(self.spec) if state is not None else None
    def _write(self,spec):
        from journal import Journal
        j=None
        try:
            j=Journal(self.state);receipt(j,spec);return True
        except Exception:return False
        finally:
            if j is not None:
                try:j.close()
                except Exception:pass
    def finish(self,status,gates=None,digest=''):
        if self.state is not None:
            fields={'status':status,'gates':gates.copy() if isinstance(gates,dict) else (gates or {}),'sourceDigest':digest}
            if self.terminal is None or any(self.terminal[k]!=v for k,v in fields.items()):
                self.terminal=dict(self.spec,**fields,endedAt=time.time())
            self.saved=self._write(self.terminal)
        return self.saved
