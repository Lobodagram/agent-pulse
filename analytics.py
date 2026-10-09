"""Deterministic workflow discovery. Suggestions are hypotheses with local evidence."""
from check_receipts import check_report
from collection_health import health as storage_health
from journal import MAX_EVENTS
from collections import Counter, defaultdict
import statistics
import time
from capability_report import capabilities
from model_evidence import model_history
from command_profile import control_tool

TEXT = {
 'sequence':('Repeated workflow','Повторяющийся сценарий','Review this sequence for a tested script or skill.','Проверьте цепочку как кандидата на скрипт или скилл.'),
 'retry':('Repeated failing call','Повторяющийся сбой','Fix the cause before adding another tool.','Исправьте причину сбоя перед добавлением инструмента.'),
 'repeat_read':('Repeated read with unchanged file metadata','Повторное чтение при неизменных метаданных','Review scoped retrieval or an index; metadata is not a content proof.','Проверьте поиск или индекс; метаданные не доказывают неизменность содержимого.'),
 'repeat_call':('Repeated identical tool input','Повтор одинакового запроса','Inspect the task before consolidating these calls.','Изучите задачу перед объединением вызовов.'),
 'template':('Repeated operation family','Повторяющееся семейство операций','Similar categories may have different purposes; inspect evidence.','Одинаковые категории могут решать разные задачи; изучите примеры.')}

def recommendation(j,key,kind,calls,sequence=None,*,summary_only=False):
    unique={c['id']:c for c in calls};calls=list(unique.values())
    provider=calls[0]['provider']
    # Sample recent distinct sessions/turns before filling remaining slots.
    selected=[];seen_sessions=set();seen_turns=set()
    for c in reversed(calls):
        if c['session'] not in seen_sessions:
            selected.append(c);seen_sessions.add(c['session']);seen_turns.add((c['session'],c['turn']))
        if len(selected)>=10:break
    for c in reversed(calls):
        if len(selected)>=10:break
        if (c['session'],c['turn']) not in seen_turns:
            selected.append(c);seen_turns.add((c['session'],c['turn']))
    selected_ids={c['id'] for c in selected}
    for c in reversed(calls):
        if len(selected)>=10:break
        if c['id'] not in selected_ids:selected.append(c);selected_ids.add(c['id'])
    examples=[c['id'] for c in selected]
    summary={'id':j.digest('finding',[provider,kind,key]),'provider':provider,'kind':kind,
             'occurrences':len(calls),'sessions':len({c['session'] for c in calls}),'evidenceIds':examples}
    # Rechecks need qualification/counts, not inventory routing or display metadata.
    # Keep the same ranking and overlap evidence as the complete finding path.
    if summary_only:return summary
    completed=[c for c in calls if c['paired'] and c['outcome'] in {'success','failed','unknown'}]
    durations=[c['durationMs'] for c in completed if c['durationMs'] is not None]
    categories=set(sequence or [c['category'] for c in calls])
    inventory=[dict(r) for r in j.db.execute('SELECT * FROM inventory WHERE provider=?',(provider,))]
    # Generic other/shell buckets do not establish a useful substitution.
    operations={c.get('operation') for c in calls}-{'unknown','legacy','shell','other','remote',None}
    advertised={r['id'] for r in j.db.execute('SELECT id,operation FROM asset_operation WHERE provider=?',(provider,)) if r['operation'] in operations}
    relevant=[r for r in inventory if r['category'] in categories-{'other','shell'} and (r['category'] not in {'remote','read','search'} or r['id'] in advertised)]
    recent=[r for r in relevant if time.time()-r['observed']<7*86400]
    available=[r for r in recent if r['status']=='available']
    configured=[r for r in recent if r['status']=='configured']
    observed_candidates=[dict(r) for r in j.db.execute(
        'SELECT id,kind,count(*) AS calls FROM capability_evidence WHERE provider=? AND evidence=? AND call IN ('+','.join('?' for _ in examples)+') GROUP BY id,kind',
        [provider,'invoked',*examples])] if examples else []
    if available:
        match='available_review';action='routing';detail='An available candidate is inventoried. Category matching does not prove substitution or non-use.'
    elif configured:
        match='configured_unverified';action='connection';detail='A candidate is configured, but its live availability is unverified.'
    elif recent:
        match='disabled_or_unavailable';action='connection';detail='Relevant inventoried entries are disabled or unavailable.'
    elif inventory:
        match='no_match_in_inventory';action='candidate';detail='No category match in this user-supplied inventory; global absence is not established.'
    else:
        match='inventory_unknown';action='review';detail='No reviewed inventory: do not conclude that a skill or MCP is missing.'
    if kind=='retry':action='fix'
    elif not relevant and kind=='sequence':action='script_or_skill'
    elif not relevant and categories <= {'read','search'}:action='retrieval'
    elif not relevant and 'remote' in categories:action='typed_tool_or_mcp'
    title,ru,suggest,suggest_ru=TEXT[kind]
    # Frequency is evidence, not a promised token saving. Tool duration sums can overlap.
    return {**summary,'title':title,'titleRu':ru,
      'suggestion':suggest,'suggestionRu':suggest_ru,'action':action,'confidence':'medium' if kind!='template' else 'low',
      'sequence':sequence or [],'evidenceSessions':list(dict.fromkeys(c['session'] for c in selected)),
      'medianDurationMs':statistics.median(durations) if durations else None,'failedCalls':sum(c['outcome']=='failed' for c in calls),
      'unknownOutcomes':sum(c['outcome']=='unknown' for c in calls),'sampledCapabilityInvocations':observed_candidates,
      'models':sorted({c['model'] for c in calls if c['model']!='other'}),'unknownModelCalls':sum(c['model']=='other' for c in calls),
      'inventoryStatus':match,'inventoryDetail':detail,'inventoryCandidates':[{'id':r['id'],'kind':r['kind'],'status':r['status']} for r in relevant[:10]],
      'measuredTokenSavings':None,'limitations':['Observed calls only; unknown coverage outside this journal.','Frequency does not prove waste or exact per-tool token cost.']}

def findings(j,calls,*,summary_only=False):
    ranks={}
    def card(key,kind,items,sequence=None):
        entry=recommendation(j,key,kind,items,sequence,summary_only=summary_only)
        typed=all(c.get('operation') not in {'unknown','legacy','shell','other','remote',None} for c in items)
        ranks[entry['id']]={'retry':0,'repeat_read':1,'repeat_call':2,'template':4}.get(kind,3 if typed else 5)
        return entry
    groups=defaultdict(list);reads=defaultdict(list);families=defaultdict(list);lanes=defaultdict(list)
    for c in calls:
        if c['paired'] and not control_tool(c.get('tool','')):
            groups[(c['provider'],c['project'],c['fingerprint'])].append(c)
            families[(c['provider'],c['project'],c['template'],c.get('operation'))].append(c)
            if c['category']=='read' and c['resource'] and c['revision']:
                reads[(c['provider'],c['project'],c['turn'],c['resource'],c['revision'])].append(c)
        # Keep failures/pending calls as barriers instead of joining their neighbours.
        if c['turn_source']!='unknown':lanes[(c['provider'],c['project'],c['session'],c['turn'],c['actor'])].append(c)
    result=[]
    for key,items in groups.items():
        fails=[c for c in items if c['outcome']=='failed']
        if len(fails)>=3:result.append(card(key,'retry',fails))
        elif len(items)>=4 and len({c['turn'] for c in items})>=2:result.append(card(key,'repeat_call',items))
    for key,items in reads.items():
        if len(items)>=3:result.append(card(key,'repeat_read',items))
    sequences=defaultdict(list)
    for lane,items in lanes.items():
        items.sort(key=lambda c:c['startedAt'] if c['startedAt'] is not None else c['endedAt'])
        # Build only execution-order segments: overlapping calls cannot establish causal chains.
        segments=[];segment=[];busy_until=0
        for c in items:
            if control_tool(c.get('tool','')) or not c['paired'] or c['outcome']=='failed' or c.get('outcomeSource')=='running-process' or c['endedAt']<c['startedAt']:
                segments.append(segment);segment=[]
                if c['endedAt'] is None or c.get('outcomeSource')=='running-process':busy_until=float('inf')
                elif c['startedAt'] is not None and c['endedAt']>=c['startedAt']:busy_until=max(busy_until,c['endedAt'])
                continue
            if c['startedAt']<busy_until:
                segments.append(segment);segment=[];busy_until=max(busy_until,c['endedAt']);continue
            if segment and c['startedAt']-segment[-1]['endedAt']>600:
                segments.append(segment);segment=[]
            busy_until=c['endedAt']
            segment.append(c)
        segments.append(segment)
        for items in segments:
            for n in range(2,5):
                for i in range(len(items)-n+1):
                    chunk=items[i:i+n];shape=tuple(c['category'] for c in chunk)
                    operations=tuple(c.get('operation','legacy') for c in chunk)
                    # A typed blob/tree/commit chain has one category but distinct operations.
                    # Repeated writes/test runs and generic same-category calls remain excluded.
                    if len(set(shape))<2 and (shape[0] in {'edit','test'} or len(set(operations))<2 or
                        any(o in {'unknown','legacy','remote','other','shell'} for o in operations)):continue
                    sequences[(lane[0],lane[1],shape,operations)].append(chunk)
    accepted=[]
    for key,chunks in sequences.items():
        turns={(x[0]['session'],x[0]['turn']) for x in chunks}
        if len(turns)>=3:accepted.append((key,chunks))
    accepted.sort(key=lambda r:len(r[0][2]),reverse=True)
    kept=[]
    for key,chunks in accepted:
        shape=key[2]
        turns={(x[0]['session'],x[0]['turn']) for x in chunks}
        if any(key[:2]==other[:2] and turns<=other_turns and
               any(shape==other[2][i:i+len(shape)] and key[3]==other[3][i:i+len(shape)] for i in range(len(other[2])-len(shape)+1))
               for other,other_turns in kept):continue
        kept.append((key,turns));entry=card(key,'sequence',[c for chunk in chunks for c in chunk],list(shape))
        entry['occurrences']=len(chunks)
        if not summary_only:
            entry['operations']=list(key[3])
            entry['sequenceBasis']='operation-family' if not any(o in {'legacy','unknown'} for o in key[3]) else 'category-only'
            if ranks[entry['id']]==5:entry['confidence']='low';entry['sequenceBasis']='category-only'
        result.append(entry)
    for key,items in families.items():
        if any(c.get('operation') in {'unknown','legacy'} for c in items):continue
        if len(items)>=10 and len({c['turn'] for c in items})>=3 and not any(r['provider']==key[0] and set(r['evidenceIds']) & {c['id'] for c in items} for r in result):
            result.append(card(key,'template',items))
    # Prioritize failure/repetition evidence; no fabricated numeric saving score.
    ordered=sorted(result,key=lambda r:(ranks[r['id']],-r['sessions'],-r['occurrences'],r['id']))
    # Keep exact evidence first; diversify only broad category-only sequences.
    projects={c['id']:c['project'] for c in calls}
    precise=[r for r in ordered if ranks[r['id']]<5]
    broad=[r for r in ordered if ranks[r['id']]==5];counts=defaultdict(int);chosen=[];remaining=[]
    for r in broad:
        project=next((projects[cid] for cid in r['evidenceIds'] if cid in projects), 'unknown')
        key=(r['provider'],project)
        if counts[key]<3:chosen.append(r);counts[key]+=1
        else:remaining.append(r)
    return (precise+chosen+remaining)[:30]

def report(j,providers=None,session_limit=100):
    j.prune();calls=j.calls();calls=[c for c in calls if providers is None or c['provider'] in providers]
    sessions=defaultdict(list)
    for c in calls:sessions[(c['provider'],c['session'])].append(c)
    summaries=[]
    for (provider,sid),items in sessions.items():
        a=j.db.execute('SELECT label,outcome,variant FROM annotation WHERE session=?',(sid,)).fetchone()
        starts=[c['startedAt'] for c in items if c['startedAt'] is not None];ends=[c['endedAt'] for c in items if c['endedAt'] is not None]
        usage=[dict(r) for r in j.db.execute('SELECT turn,input,cached_input,output,source FROM turn_usage WHERE session=?',(sid,))]
        usage_by_turn=defaultdict(list)
        for u in usage:usage_by_turn[u['turn']].append(u)
        totals={};conflicts=0
        for component in ['input','cached_input','output']:
            values=[];conflict=False
            for rows in usage_by_turn.values():
                known={r[component] for r in rows if r[component] is not None}
                if len(known)>1:conflict=True;conflicts+=1
                elif known:values.append(next(iter(known)))
            totals[component]=None if conflict or not values else sum(values)
        summaries.append({'id':sid,'provider':provider,'projectId':items[0]['project'],'calls':len(items),
          'failed':sum(c['outcome']=='failed' for c in items),'pending':sum(c['outcome']=='pending' for c in items),
          'paired':sum(c['paired'] for c in items),'startedAt':min(starts) if starts else None,'endedAt':max(ends) if ends else None,
          'elapsedMs':(max(ends)-min(starts))*1000 if starts and ends and max(ends)>=min(starts) else None,
          'label':a['label'] if a else None,'outcome':a['outcome'] if a else 'unknown','variant':a['variant'] if a else None,
          'reportedInputTokens':totals['input'],'reportedOutputTokens':totals['output'],'reportedCachedInputTokens':totals['cached_input'],
          'models':sorted({c['model'] for c in items if c['model']!='other'}),'modelHistory':model_history(items),
          'settingsCoverage':'model identifiers only when native hooks report them; effort and task difficulty unverified',
          'usageTurns':len(usage_by_turn),'usageConflicts':conflicts,'usageCoverage':'explicit turn reports only; conflicting components unknown; not a session total unless every turn is reported'})
    coverage=[]
    health={r['provider']:dict(r) for r in j.db.execute('SELECT * FROM health')}
    tool_seen={r['provider']:r['at'] for r in j.db.execute("SELECT provider,max(received) AS at FROM observation WHERE call!='' GROUP BY provider")}
    for provider in sorted(providers or {c['provider'] for c in calls}):
        h=health.get(provider,{});items=[c for c in calls if c['provider']==provider];seen=h.get('last_event');active=bool(seen and time.time()-seen<600)
        recent_tool=tool_seen.get(provider);tool_active=bool(recent_tool and time.time()-recent_tool<600)
        coverage.append({'provider':provider,'mode':'hook-events' if any(c['source']=='hook' for c in items) else 'projected-events' if items else 'no-events',
          'state':'receiving' if tool_active else 'lifecycle-only' if active else 'stale' if seen else 'not-observed','lastEventAt':seen,'lastToolEventAt':recent_tool,'calls':len(items),
          'pairedCalls':sum(c['paired'] for c in items),'rejected':h.get('rejected',0),
          'knownOutcomes':sum(c['paired'] and c['outcome'] in {'success','failed'} for c in items),
          'unknownOutcomes':sum(c['outcome']=='unknown' for c in items),
          'missingFinishes':sum(c['endedAt'] is None for c in items),
          'missingStarts':sum(c['startedAt'] is None for c in items),
          'collectionGaps':sum(c.get('collectionIssue') in {'stale-unpaired','missing-finish-after-boundary','missing-start'} for c in items),
          'completeness':'unknown; hosted tools, disabled hooks and disconnected clients may be absent'})
    total=j.db.execute('SELECT count(*) FROM observation WHERE received>=?',(time.time()-30*86400,)).fetchone()[0]
    usage=defaultdict(list);shared=defaultdict(list)
    for c in calls:
        usage[(c['provider'],c['tool'])].append(c)
        if c['paired'] and c['project']!='unknown' and c.get('operation') not in {'unknown','legacy','other','shell',None}:
            shared[(c['project'],c['operation'])].append(c)
    tool_usage=[]
    for (provider,tool),items in usage.items():
        durations=[c['durationMs'] for c in items if c['durationMs'] is not None]
        tool_usage.append({'provider':provider,'tool':tool,'calls':len(items),'failed':sum(c['outcome']=='failed' for c in items),
                           'unknown':sum(c['outcome']=='unknown' for c in items),'pending':sum(c['outcome']=='pending' for c in items),
                           'medianDurationMs':statistics.median(durations) if durations else None})
    cross=[]
    for (project,op),items in shared.items():
        ps=sorted({c['provider'] for c in items});turns={(c['provider'],c['session'],c['turn']) for c in items if c['turn_source']!='unknown'}
        if len(ps)>=2 and len(turns)>=3 and len(items)>=6:
            cross.append({'operation':op,'providers':ps,'calls':len(items),'turns':len(turns),'projectId':project,
                          'evidenceIds':[c['id'] for c in items[:10]],'confidence':'low; same family, not equivalent task'})
    from capability_detection import mcp_namespace
    namespaces=defaultdict(list)
    for c in calls:
        name=mcp_namespace(c['tool'])
        if name:namespaces[(c['provider'],name)].append(c)
    mcp_usage=[{'provider':p,'namespace':n,'calls':len(items),'confirmedSuccesses':sum(c['paired'] and c['outcome']=='success' for c in items),
               'unknownOutcomes':sum(c['outcome']=='unknown' for c in items),'pending':sum(c['outcome']=='pending' for c in items),
               'registered':bool(j.db.execute('SELECT 1 FROM inventory WHERE provider=? AND id=? AND kind=?',(p,n,'mcp')).fetchone()),
               'coverage':'native namespace only; plugin identity and live availability are not inferred'} for (p,n),items in namespaces.items()]
    from finding_review import reviewed_findings
    reviews=reviewed_findings(j,calls,providers)
    from efficiency import efficiency_report
    efficiency=efficiency_report(j,calls,providers)
    return {'schemaVersion':5,'generatedAt':time.time(),'coverage':coverage,'sessions':sorted(summaries,key=lambda x:x['startedAt'] or 0,reverse=True)[:session_limit] if session_limit is not None else sorted(summaries,key=lambda x:x['startedAt'] or 0,reverse=True),
      'sessionsTruncated':session_limit is not None and len(summaries)>session_limit,'efficiency':efficiency,
      'findings':findings(j,calls),'recentCalls':calls[-100:],'calls':len(calls),'eventLimitReached':total>MAX_EVENTS,
      'capabilities':capabilities(j,providers),'toolUsage':sorted(tool_usage,key=lambda x:-x['calls'])[:100],
      'crossClientPatterns':sorted(cross,key=lambda x:-x['calls'])[:30],
      'modelHistory':model_history(calls),
      'mcpNamespaces':sorted(mcp_usage,key=lambda x:-x['calls'])[:100],'findingReviews':reviews,
      'findingReviewsTruncated':j.db.execute('SELECT count(*) FROM finding_review').fetchone()[0]>30,
      'checkRuns':check_report(j,providers),
      'storageHealth':storage_health(j),
      'quality':{'pairedCalls':sum(c['paired'] for c in calls),'knownOutcomes':sum(c['paired'] and c['outcome'] in {'success','failed'} for c in calls),
                 'outcomeSources':dict(Counter(c['outcomeSource'] for c in calls)),
                 'unpairedCalls':sum(not c['paired'] for c in calls),'windowDays':30,'completeCoverage':False},
      'tokenAttribution':'native turn usage only; no per-tool costs or subscription-token conversion',
      'analysisCoverage':{'bookkeepingCalls':sum(control_tool(c.get('tool','')) for c in calls),
        'typedOperationCalls':sum(c.get('operation') not in {'unknown','legacy','shell','other','remote','bookkeeping',None} for c in calls),
        'unknownOperationCalls':sum(c.get('operation') in {'unknown','legacy',None} for c in calls),
        'basis':'Allowlisted command/tool names; historical unknown shell payloads cannot be reconstructed.'},
      'inventoryCount':j.db.execute('SELECT count(*) FROM inventory').fetchone()[0],'localOnly':True}

def compare(j,label,before,after):
    from journal import safe_name
    if any(safe_name(x)=='other' for x in [label,before,after]) or before==after:raise ValueError('invalid_comparison')
    rows=report(j,session_limit=None)['sessions'];groups={v:[s for s in rows if s['label']==label and s['variant']==v] for v in [before,after]}
    result={'label':label,'before':before,'after':after,'groups':{},'confidence':'insufficient','tokenSavings':None,'causalClaim':False,
      'limitations':['User labels do not establish equal task difficulty or model settings.','Failed/rework outcomes count against an improvement.','Manual observations do not establish causation.']}
    for v,items in groups.items():
        durations=[s['elapsedMs'] for s in items if s['elapsedMs'] is not None]
        result['groups'][v]={'sessions':len(items),'accepted':sum(s['outcome']=='accepted' for s in items),'failedOrRework':sum(s['outcome'] in {'failed','rework'} for s in items),
          'medianCalls':statistics.median([s['calls'] for s in items]) if items else None,'medianElapsedMs':statistics.median(durations) if durations else None,
          'models':sorted({m for s in items for m in s['models']}),'unknownModelCalls':sum(s['modelHistory']['unknownModelCalls'] for s in items),
          'reportedModelChanges':sum(s['modelHistory']['reportedChanges'] for s in items)}
    if all(len(x)>=3 for x in groups.values()):result['confidence']='observational'
    return result
