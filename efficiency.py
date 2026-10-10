"""Local task/version evidence. No inference, raw payloads or quota conversion."""
from collections import Counter, defaultdict
import json
import re
import statistics
import time
from sanitizers import safe_name


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS asset_version(provider TEXT,id TEXT,version TEXT,kind TEXT,finding TEXT,at REAL,
      PRIMARY KEY(provider,id,version));
    CREATE TABLE IF NOT EXISTS asset_operation(provider TEXT,id TEXT,version TEXT,operation TEXT,
      PRIMARY KEY(provider,id,version,operation));
    CREATE TABLE IF NOT EXISTS reviewed_task(id TEXT PRIMARY KEY,provider TEXT,session TEXT,label TEXT,
      variant TEXT,criterion TEXT,outcome TEXT,asset TEXT,version TEXT,applied INTEGER,at REAL);
    CREATE TABLE IF NOT EXISTS task_call(task TEXT,provider TEXT,call TEXT,
      PRIMARY KEY(provider,call));
    CREATE INDEX IF NOT EXISTS task_call_task ON task_call(task);
    CREATE TABLE IF NOT EXISTS task_eligibility(task TEXT PRIMARY KEY,eligibility TEXT,non_use_reason TEXT);
    CREATE TABLE IF NOT EXISTS turn_usage_status(provider TEXT,session TEXT,turn TEXT,source TEXT,
      complete INTEGER,requests REAL,PRIMARY KEY(provider,session,turn,source));
    CREATE TABLE IF NOT EXISTS widget_comparison(provider TEXT PRIMARY KEY,label TEXT,before_variant TEXT,after_variant TEXT);
    ''')


def slug(value):
    if safe_name(value)=='other' or len(value)>64:raise ValueError('invalid_public_label')
    return value


def version_name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',value) or safe_name('v'+value)=='other':
        raise ValueError('invalid_version')
    return value


def register_asset(j,spec):
    from journal import PROVIDERS
    if not isinstance(spec,dict) or not {'provider','assetId','version','kind'}<=set(spec) or set(spec)-{'provider','assetId','version','kind','findingId','operations'}:
        raise ValueError('invalid_asset')
    provider=spec['provider'];asset=slug(spec['assetId']);version=version_name(spec['version']);kind=spec['kind'];finding=spec.get('findingId','')
    if provider not in PROVIDERS or kind not in {'skill','mcp','tool'}:raise ValueError('invalid_asset')
    operations=spec.get('operations',[])
    if not isinstance(operations,list) or len(operations)>10:raise ValueError('invalid_operations')
    operations=sorted({slug(op) for op in operations})
    if finding:
        from analytics import findings
        if not any(f['id']==finding and f['provider']==provider for f in findings(j,j.calls())):raise ValueError('finding_not_found')
    with j.db:
        j.db.execute('BEGIN IMMEDIATE')
        old=j.db.execute('SELECT kind,finding FROM asset_version WHERE provider=? AND id=? AND version=?',(provider,asset,version)).fetchone()
        if old and tuple(old)!=(kind,finding):raise ValueError('version_is_immutable')
        old_operations=sorted(r[0] for r in j.db.execute('SELECT operation FROM asset_operation WHERE provider=? AND id=? AND version=?',(provider,asset,version)))
        if old and old_operations!=operations:raise ValueError('version_is_immutable')
        if not old and j.db.execute('SELECT count(*) FROM asset_version').fetchone()[0]>=200:raise ValueError('asset_limit')
        j.db.execute('INSERT OR IGNORE INTO asset_version VALUES (?,?,?,?,?,?)',(provider,asset,version,kind,finding,time.time()))
        j.db.executemany('INSERT OR IGNORE INTO asset_operation VALUES (?,?,?,?)',[(provider,asset,version,op) for op in operations])
    return {'saved':True,'localOnly':True,'assetId':asset,'version':version}


def record_task(j,spec):
    from journal import PROVIDERS
    required={'provider','taskId','label','variant','criterion','outcome','callIds'}
    if not isinstance(spec,dict) or not required<=set(spec) or set(spec)-required-{'assetId','version','applied','eligibility','nonUseReason'}:raise ValueError('invalid_task')
    provider=spec['provider'];label=slug(spec['label']);variant=slug(spec['variant']);criterion=slug(spec['criterion'])
    if not isinstance(spec['taskId'],str) or not 1<=len(spec['taskId'])<=1000:raise ValueError('invalid_task_identity')
    ids=spec['callIds'];outcome=spec['outcome'];applied=spec.get('applied',False)
    if provider not in PROVIDERS or outcome not in {'accepted','failed','rework','unknown'} or type(applied)!=bool:raise ValueError('invalid_task')
    if not isinstance(ids,list) or not 1<=len(ids)<=500 or any(not isinstance(c,str) or not re.fullmatch('[a-f0-9]{32}',c) for c in ids) or len(set(ids))!=len(ids):raise ValueError('invalid_call_selection')
    j.prune()
    observed=j.calls();by_id={c['id']:c for c in observed if c['provider']==provider};calls=[by_id[c] for c in ids if c in by_id]
    if len(calls)!=len(ids) or len({(c['session'],c['project'],c['actor']) for c in calls})!=1:raise ValueError('selection_scope_mismatch')
    session=calls[0]['session'];lane=[c for c in observed if (c['provider'],c['session'],c['actor'])==(provider,session,calls[0]['actor'])]
    indexes=[i for i,c in enumerate(lane) if c['id'] in ids]
    if max(indexes)-min(indexes)+1!=len(ids):raise ValueError('selection_not_contiguous')
    asset=spec.get('assetId','');version=spec.get('version','')
    eligibility=spec.get('eligibility','unknown');non_use=spec.get('nonUseReason','')
    if not isinstance(eligibility,str) or not isinstance(non_use,str) or eligibility not in {'yes','no','unknown'} or non_use not in {'','unknown','unavailable','not-selected','workflow-mismatch','preferred-alternative'}:raise ValueError('invalid_eligibility')
    if (eligibility!='unknown' or non_use) and not asset:raise ValueError('asset_version_required')
    if applied and (eligibility=='no' or non_use):raise ValueError('contradictory_application')
    if bool(asset)!=bool(version) or applied and not asset:raise ValueError('asset_version_required')
    if asset:
        slug(asset);version_name(version)
        if not j.db.execute('SELECT 1 FROM asset_version WHERE provider=? AND id=? AND version=?',(provider,asset,version)).fetchone():raise ValueError('asset_not_registered')
    task=j.digest('reviewed-task',[provider,spec['taskId']])
    with j.db:
        j.db.execute('BEGIN IMMEDIATE')
        old=j.db.execute('SELECT * FROM reviewed_task WHERE id=?',(task,)).fetchone()
        old_ids={r['call'] for r in j.db.execute('SELECT call FROM task_call WHERE task=?',(task,))}
        if old and (old_ids!=set(ids) or (old['label'],old['variant'],old['criterion'],old['asset'],old['version'])!=(label,variant,criterion,asset,version)):
            raise ValueError('task_identity_is_immutable')
        if not old and j.db.execute('SELECT count(*) FROM reviewed_task').fetchone()[0]>=1000:raise ValueError('task_limit')
        if any(j.db.execute('SELECT 1 FROM task_call WHERE provider=? AND call=? AND task!=?',(provider,c,task)).fetchone() for c in ids):raise ValueError('overlapping_task')
        j.db.execute('INSERT OR REPLACE INTO reviewed_task VALUES (?,?,?,?,?,?,?,?,?,?,?)',(task,provider,session,label,variant,criterion,outcome,asset,version,int(applied),time.time()))
        j.db.executemany('INSERT OR IGNORE INTO task_call VALUES (?,?,?)',[(task,provider,c) for c in ids])
        assessment=j.db.execute('SELECT eligibility,non_use_reason FROM task_eligibility WHERE task=?',(task,)).fetchone()
        if assessment:
            eligibility=spec.get('eligibility',assessment['eligibility']);non_use=spec.get('nonUseReason',assessment['non_use_reason'])
        if applied and (eligibility=='no' or non_use):raise ValueError('contradictory_application')
        j.db.execute('INSERT OR REPLACE INTO task_eligibility VALUES (?,?,?)',(task,eligibility,non_use))
    return {'saved':True,'localOnly':True,'taskId':task}


def usage_summary(j,provider,session,turns):
    rows=j.db.execute('''SELECT u.*,s.complete,s.requests FROM turn_usage u LEFT JOIN turn_usage_status s
      ON u.provider=s.provider AND u.session=s.session AND u.turn=s.turn AND u.source=s.source
      WHERE u.provider=? AND u.session=? AND u.at>=?''',(provider,session,time.time()-30*86400)).fetchall()
    grouped=defaultdict(list)
    for r in rows:
        if r['turn'] in turns:grouped[r['turn']].append(r)
    totals={};conflicts=0
    for field in ['input','cached_input','output','requests']:
        values=[];bad=False
        for turn in turns:
            known={r[field] for r in grouped.get(turn,[]) if r[field] is not None}
            if len(known)>1:bad=True;conflicts+=1
            elif known:values.append(next(iter(known)))
        totals[field]=None if bad or len(values)!=len(turns) or not turns else sum(values)
    if totals['cached_input'] is not None and totals['input'] is not None and totals['cached_input']>totals['input']:
        totals['cached_input']=None;conflicts+=1
    for group in grouped.values():
        inputs={r['input'] for r in group if r['input'] is not None};cached={r['cached_input'] for r in group if r['cached_input'] is not None}
        if len(inputs)==len(cached)==1 and next(iter(cached))>next(iter(inputs)):
            totals['cached_input']=None;conflicts+=1
    complete=bool(turns) and all(any(r['complete']==1 and r['input'] is not None and r['output'] is not None for r in grouped.get(t,[])) for t in turns) and not conflicts and totals['input'] is not None and totals['output'] is not None
    requests_complete=bool(turns) and not conflicts and all(any(r['complete']==1 and r['requests'] is not None for r in grouped.get(t,[])) for t in turns)
    return {**totals,'complete':complete,'requestsComplete':requests_complete,'reportedTurns':len(grouped),'totalTurns':len(turns),'conflicts':conflicts,
            'sources':sorted({r['source'] for group in grouped.values() for r in group}),
            'completenessBasis':'explicit reporter flag; not independently verified'}


def ingest_usage(j,spec):
    allowed={'provider','sessionId','turnId','input','cached_input','output','complete','modelRequests'}
    if not isinstance(spec,dict) or set(spec)-allowed or not {'provider','sessionId','turnId'}<=set(spec):raise ValueError('invalid_usage_receipt')
    if any(not isinstance(spec[k],str) or not 1<=len(spec[k])<=1000 for k in ('sessionId','turnId')):raise ValueError('invalid_usage_identity')
    usage={k:spec[k] for k in ('input','cached_input','output') if k in spec}
    if any(type(v)!=int or not 0<=v<=10**15 for v in usage.values()):raise ValueError('invalid_usage_counter')
    j.usage(spec['provider'],spec['sessionId'],spec['turnId'],usage,source='native-receipt',complete=spec.get('complete',False),model_requests=spec.get('modelRequests'))
    return {'saved':True,'localOnly':True,'provenance':'reporter-supplied native receipt; not independently verified'}


def task_rows(j,calls):
    indexed={c['id']:c for c in calls};all_turns=defaultdict(set)
    for c in calls:all_turns[(c['provider'],c['session'],c['turn'])].add(c['id'])
    memberships=defaultdict(list)
    for r in j.db.execute('SELECT * FROM task_call'):memberships[r['task']].append(r['call'])
    from journal import MAX_EVENTS
    limited=j.db.execute('SELECT count(*) FROM observation WHERE received>=?',(time.time()-30*86400,)).fetchone()[0]>MAX_EVENTS
    result=[]
    for row in j.db.execute('SELECT * FROM reviewed_task WHERE at>=? ORDER BY at DESC',(time.time()-30*86400,)):
        r=dict(row);ids=memberships[r['id']];selected=[indexed[c] for c in ids if c in indexed]
        full=bool(ids) and len(selected)==len(ids) and not limited
        turns={c['turn'] for c in selected};known=all(c['turn_source']!='unknown' for c in selected)
        full_turns=full and known and all(all_turns[(r['provider'],r['session'],t)]<=set(ids) for t in turns)
        usage=usage_summary(j,r['provider'],r['session'],turns)
        usage['complete']=usage['complete'] and full_turns and all(c['paired'] for c in selected)
        usage['requestsComplete']=usage['requestsComplete'] and full_turns and all(c['paired'] for c in selected)
        native=bool(r['asset'] and any(j.db.execute("SELECT 1 FROM capability_evidence WHERE provider=? AND call=? AND id=? AND evidence='invoked'",(r['provider'],c,r['asset'])).fetchone() for c in ids))
        starts=[c['startedAt'] for c in selected if c['startedAt'] is not None];ends=[c['endedAt'] for c in selected if c['endedAt'] is not None]
        elapsed=(max(ends)-min(starts))*1000 if full and len(starts)==len(ids) and len(ends)==len(ids) and all(c['endedAt']>=c['startedAt'] for c in selected) else None
        models=sorted({c['model'] for c in selected});actors=sorted({c['actor'] for c in selected});projects=sorted({c['project'] for c in selected})
        asset=r.pop('asset')
        assessment=j.db.execute('SELECT eligibility,non_use_reason FROM task_eligibility WHERE task=?',(r['id'],)).fetchone()
        eligibility=assessment['eligibility'] if assessment else 'unknown'
        non_use=assessment['non_use_reason'] if assessment else ''
        result.append({**r,'taskId':r['id'],'assetId':asset,'callIds':ids,'calls':len(selected),'selectionComplete':full,
          'eligibility':eligibility,'nonUseReason':non_use,
          'application':'used' if r['applied'] else 'not-used' if non_use else 'unknown',
          'knownResults':sum(c['paired'] and c['outcome'] in {'success','failed'} for c in selected),
          'successes':sum(c['paired'] and c['outcome']=='success' for c in selected),'elapsedMs':elapsed,
          'models':models,'actors':actors,'projects':projects,'usage':usage,
          'nativeIdentityObserved':native,'useEvidence':'declared' if r['applied'] else 'not-attested',
          'cohort':json.dumps([r['provider'],projects,models,r['criterion']],sort_keys=True),
          'modelKnown':len(models)==1 and models[0]!='other','attribution':'observed task only; complete visibility unverified'})
    return result


def summarize(rows):
    accepted=sum(r['outcome']=='accepted' for r in rows);reviewed=sum(r['outcome']!='unknown' for r in rows)
    complete=sum(r['usage']['complete'] for r in rows);cost_complete=bool(rows) and complete==len(rows)
    all_tokens=sum(r['usage']['input']+r['usage']['output'] for r in rows) if cost_complete else None
    inputs=sum(r['usage']['input'] for r in rows) if cost_complete else None
    cache=sum(r['usage']['cached_input'] for r in rows) if cost_complete and all(r['usage']['cached_input'] is not None for r in rows) else None
    requests=sum(r['usage']['requests'] for r in rows) if rows and all(r['usage']['requestsComplete'] for r in rows) else None
    durations=[r['elapsedMs'] for r in rows if r['elapsedMs'] is not None]
    known=sum(r['knownResults'] for r in rows);success=sum(r['successes'] for r in rows)
    return {'tasks':len(rows),'accepted':accepted,'reviewed':reviewed,'failedOrRework':sum(r['outcome'] in {'failed','rework'} for r in rows),
      'acceptanceRate':accepted/reviewed if reviewed else None,'usageCompleteTasks':complete,
      'tokensPerAccepted':all_tokens/accepted if all_tokens is not None and accepted else None,
      'reportedTokens':all_tokens,'modelRequests':requests,'cacheHitRate':cache/inputs if cache is not None and inputs else None,
      'medianElapsedMs':statistics.median(durations) if durations else None,'elapsedTasks':len(durations),
      'nativeUses':0,'nativeIdentityUses':sum(r['nativeIdentityObserved'] for r in rows),'declaredUses':sum(r['useEvidence']=='declared' for r in rows),
      'observedCallsPerAccepted':sum(r['calls'] for r in rows)/accepted if accepted and all(r['selectionComplete'] for r in rows) else None,
      'elapsedMsPerAccepted':sum(durations)/accepted if accepted and len(durations)==len(rows) else None,
      'modelRequestsPerAccepted':requests/accepted if requests is not None and accepted else None,
      'knownResults':known,'observedCalls':sum(r['calls'] for r in rows),'technicalSuccessRate':success/known if known else None,
      'eligibleTasks':None,'adoptionRate':None,'subscriptionSavings':None,'causalClaim':False}


def efficiency_report(j,calls=None,providers=None):
    if calls is None:j.prune()
    calls=j.calls() if calls is None else calls
    rows=task_rows(j,calls);assets=[]
    if providers is not None:rows=[r for r in rows if r['provider'] in providers]
    for r in j.db.execute('SELECT * FROM asset_version ORDER BY at DESC'):
        if providers is not None and r['provider'] not in providers:continue
        group=[t for t in rows if (t['provider'],t['assetId'],t['version'])==(r['provider'],r['id'],r['version'])]
        eligible=[t for t in group if t['eligibility']=='yes'];known=[t for t in eligible if t['application']!='unknown']
        used=sum(t['application']=='used' for t in eligible)
        lifecycle='registered-awaiting-use'
        applied=[t for t in group if t['application']=='used']
        if applied:lifecycle='accepted-awaiting-comparison' if any(t['outcome']=='accepted' for t in applied) else 'awaiting-acceptance'
        assets.append({'provider':r['provider'],'assetId':r['id'],'version':r['version'],'kind':r['kind'],'findingId':r['finding'],
                       **summarize(group),'state':'observed' if group else 'insufficient',
                       'eligibleTasks':len(eligible) if any(t['eligibility']!='unknown' for t in group) else None,'eligibilityKnownTasks':sum(t['eligibility']!='unknown' for t in group),
                       'eligibilityUnknownTasks':sum(t['eligibility']=='unknown' for t in group),'usedEligibleTasks':used,
                       'adoptionKnownTasks':len(known),'adoptionRate':used/len(eligible) if eligible and len(known)==len(eligible) else None,
                       'adoptionBasis':'explicit assessments of selected tasks only; not all possible work',
                       'nonUseReasons':dict(Counter(t['nonUseReason'] for t in eligible if t['application']=='not-used')),
                       'lifecycle':lifecycle})
    public_rows=[{**r,'callIds':r['callIds'][:20],'callIdsTruncated':len(r['callIds'])>20} for r in rows[:100]]
    return {'assets':assets,'tasks':public_rows,'totalTasks':len(rows),'tasksTruncated':len(rows)>100,
      'widgetBenefits':widget_benefits(j,calls,rows,assets,providers),
      'coverage':'explicit reviewed selections; native usage only; no quota or per-tool token attribution',
      'subscriptionSavings':None,'causalClaim':False}


def compare_tasks(j,label,before,after,provider=None):
    from journal import PROVIDERS
    slug(label);slug(before);slug(after)
    if provider is not None and provider not in PROVIDERS:raise ValueError('invalid_provider')
    if before==after:raise ValueError('invalid_comparison')
    j.prune()
    return compare_rows(task_rows(j,j.calls()),label,before,after,provider)


def compare_rows(rows,label,before,after,provider):
    """One explicitly chosen comparison; identical gates for CLI and widget."""
    groups={v:[r for r in rows if r['label']==label and r['variant']==v and (provider is None or r['provider']==provider)] for v in [before,after]}
    a,b=groups[before],groups[after];reasons=[]
    if min(len(a),len(b))<3:reasons.append('insufficient-tasks')
    ca=Counter(r['cohort'] for r in a);cb=Counter(r['cohort'] for r in b)
    if set(ca)!=set(cb) or any(ca[k]*len(b)!=cb[k]*len(a) for k in ca):reasons.append('different-cohorts')
    if not all(r['modelKnown'] and r['selectionComplete'] and 'unknown' not in r['projects'] for r in a+b):reasons.append('unknown-model-or-selection')
    summaries={v:summarize(g) for v,g in groups.items()};sa,sb=summaries[before],summaries[after]
    if not all(r['outcome']!='unknown' for r in a+b):reasons.append('unreviewed-tasks')
    if sa['acceptanceRate'] is None or sb['acceptanceRate'] is None or sb['acceptanceRate']<sa['acceptanceRate']:reasons.append('quality-not-established')
    common=list(reasons)
    metrics={}
    for metric,missing in [('observedCallsPerAccepted','incomplete-selection'),('elapsedMsPerAccepted','incomplete-time'),('modelRequestsPerAccepted','incomplete-requests'),('tokensPerAccepted','incomplete-usage')]:
        x,y=sa[metric],sb[metric];blocked=list(common)
        if x is None or y is None:blocked.append(missing)
        elif x==0:blocked.append('zero-baseline')
        metrics[metric]={'before':x,'after':y,'reduction':1-y/x if not blocked else None,'reasons':blocked,
                         'confidence':'observational' if not blocked else 'insufficient'}
    if sa['tokensPerAccepted'] in (None,0) or sb['tokensPerAccepted'] is None:reasons.append('incomplete-usage')
    reduction=1-sb['tokensPerAccepted']/sa['tokensPerAccepted'] if not reasons else None
    return {'label':label,'before':before,'after':after,'groups':summaries,'tokenReduction':reduction,'metrics':metrics,
      'reasons':reasons,'confidence':'observational' if not reasons else 'insufficient','causalClaim':False,'subscriptionSavings':None,
      'limitations':['Equal labels and observed cohort mix do not establish equal difficulty, reasoning settings or causation.',
                    'Usage includes all selected attempts; task visibility and manual acceptance remain partial.']}


def select_widget_comparison(j,provider,label=None,before=None,after=None):
    """Persist direction explicitly; clearing changes no task or asset evidence."""
    from journal import PROVIDERS
    if provider not in PROVIDERS:raise ValueError('invalid_provider')
    if label is None and before is None and after is None:
        with j.db:j.db.execute('DELETE FROM widget_comparison WHERE provider=?',(provider,))
    else:
        slug(label);slug(before);slug(after)
        if before==after:raise ValueError('invalid_comparison')
        with j.db:j.db.execute('INSERT OR REPLACE INTO widget_comparison VALUES (?,?,?,?)',(provider,label,before,after))
    return {'saved':True,'localOnly':True,'provider':provider,'selected':label is not None}


def widget_benefits(j,calls,rows,assets,providers=None):
    """Bounded metadata only; registration, application, invocation and effects differ."""
    from journal import PROVIDERS
    result={};call_ids={c['id'] for c in calls}
    invoked=defaultdict(set)
    for r in j.db.execute("SELECT provider,id,kind,call FROM capability_evidence WHERE evidence='invoked'"):
        if r['call'] in call_ids:invoked[(r['provider'],r['id'],r['kind'])].add(r['call'])
    selections={r['provider']:r for r in j.db.execute('SELECT * FROM widget_comparison')}
    for provider in sorted(PROVIDERS if providers is None else providers):
        linked=[a for a in assets if a['provider']==provider and a['findingId']]
        # Versions are not additional tools. Registry order is newest first.
        distinct={}
        for a in linked:distinct.setdefault(a['assetId'],a['kind'])
        registered=Counter(distinct.values());versions={(a['assetId'],a['version']) for a in linked}
        tasks=[r for r in rows if r['provider']==provider and (r['assetId'],r['version']) in versions]
        identities={(a['assetId'],a['kind']) for a in linked}
        uses=set().union(*(invoked[(provider,ident,kind)] for ident,kind in identities)) if identities else set()
        comparison=None
        if provider in selections:
            s=selections[provider]
            comparison=compare_rows(rows,s['label'],s['before_variant'],s['after_variant'],provider)
        result[provider]={'windowDays':30,'linkedAssets':{k:registered[k] for k in ('skill','mcp','tool')},
          'observedInvocations':len(uses),'declaredAppliedTasks':sum(r['application']=='used' for r in tasks),
          'reviewedLinkedTasks':len(tasks),'hasObservations':any(c['provider']==provider for c in calls),
          'comparison':comparison,'subscriptionSavings':None,'causalClaim':False,
          'coverage':'Registered finding links (all registry); observed invocations and declared task applications (retained 30 days). Not total activity or created assets.'}
    return result


def widget_lines(provider,ru=False):
    """Windows text adapter for the shared summary; unknowns never become savings."""
    def tr(en,rus):return rus if ru else en
    b=provider.get('benefit')
    if b is None:
        lines=[tr('PULSE · finding links: awaiting evidence','PULSE · связи с находками: ждём данные'),tr('30d: no observed activity yet','30д: пока нет наблюдений'),tr('Comparison: awaiting evidence','Сравнение: ждём данные')]
    else:
        a=b['linkedAssets']
        lines=[tr('PULSE · linked: skills ','PULSE · связано: скиллы ')+str(a['skill'])+' · MCP '+str(a['mcp'])+tr(' · tools ',' · тулзы ')+str(a['tool'])]
        lines.append(tr('30d: applied tasks ','30д: применено в задачах ')+str(b['declaredAppliedTasks'])+tr(' · calls ',' · вызовы ')+str(b['observedInvocations']) if b['hasObservations'] or b['reviewedLinkedTasks'] else tr('30d: no observed activity yet','30д: пока нет наблюдений'))
        c=b.get('comparison')
        if c is None:lines.append(tr('Comparison: choose a comparison ↗','Сравнение: выберите сравнение ↗'))
        else:
            metrics=c['metrics'];req=metrics['modelRequestsPerAccepted']['reduction'];tokens=metrics['tokensPerAccepted']['reduction']
            def change(v):
                if v is None:return '—'
                if v==0:return '0%'
                return ('↓' if v>0 else '↑')+('<0.1' if abs(v)<.001 else f'{abs(v)*100:.1f}')+'%'
            lines.append(tr('Per result: requests ','На результат: запросы ')+change(req)+tr(' · tokens ',' · токены ')+change(tokens) if req is not None or tokens is not None else tr('Comparison: not enough comparable tasks ↗','Сравнение: мало сравнимых задач ↗'))
    cache=(provider.get('localTokenProfile') or {}).get('cacheHitRate')
    lines.append(tr('Cache today: ','Кэш сегодня: ')+('—' if cache is None else f'{cache*100:.1f}%')+tr(' input · partial',' входа · частично'))
    return lines
