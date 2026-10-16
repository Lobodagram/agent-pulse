"""Bounded metadata diagnostics, independent of workflow automation hypotheses."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import time


def failure_review_plan(classes):
    """Fixed next steps for reported categories, not diagnoses or automatic retries."""
    guidance = {
        'syntax': ('Check the syntax of the failing operation before rerunning.', 'Проверьте синтаксис операции перед повтором.'),
        'reference': ('Check declared bindings and REPL state; do not assume prior state survived.', 'Проверьте объявленные переменные и состояние REPL; не предполагайте сохранение прежнего состояния.'),
        'type': ('Check input types against the actual tool contract.', 'Сверьте типы входных данных с фактическим контрактом инструмента.'),
        'module-not-found': ('Verify the required module in the actual runtime; installation requires owner approval.', 'Проверьте нужный модуль в фактическом runtime; установка требует разрешения владельца.'),
        'permission': ('Check the approved path and permissions; do not grant new access automatically.', 'Проверьте разрешённый путь и права; не выдавайте новый доступ автоматически.'),
        'not-found': ('Verify the exact required file or executable before rerunning.', 'Проверьте наличие нужного файла или исполняемого файла перед повтором.'),
        'timeout': ('Check whether the operation already changed state before any retry.', 'До повторной попытки проверьте, успела ли операция изменить состояние.'),
        'connection': ('Verify the existing connection contract; avoid repeated blind requests.', 'Проверьте существующий контракт подключения; избегайте повторных слепых запросов.'),
    }
    result = []
    for category in sorted(classes):
        text, local = guidance.get(category, ('Obtain a fixed structured error category on the next natural failure; the cause remains unknown.', 'При следующей естественной ошибке получите фиксированную структурированную категорию; причина пока неизвестна.'))
        result.append({'category': category, 'text': text, 'textRu': local, 'autoRetry': False})
    return result


def result_evidence(calls):
    """Whole retained selection, no dependence on bounded tool-group previews."""
    finished=[c for c in calls if c['endedAt'] is not None]
    unknown=[c for c in finished if c['outcome']=='unknown']
    recorded=[c for c in finished if c.get('responseEnvelope') is not None]
    unknown_recorded=[c for c in unknown if c.get('responseEnvelope') is not None]
    categories=dict(Counter(c['responseEnvelope']['responseKind'] for c in unknown_recorded))
    return {'calls':len(calls),'finished':len(finished),'missingFinish':len(calls)-len(finished),
        'unknownFinished':len(unknown),'terminalSources':dict(Counter(c['outcomeSource'] for c in finished)),
        'unknownByTool':dict(Counter(c['tool'] for c in unknown)),
        'envelopeRecorded':len(recorded),'envelopeNotRecorded':len(finished)-len(recorded),
        'unknownEnvelopeRecorded':len(unknown_recorded),'unknownResponseKinds':categories,
        'unknownDirectExitFields':dict(Counter(c['responseEnvelope']['directExit'] for c in unknown_recorded)),
        'unknownStructuredExitFields':dict(Counter(c['responseEnvelope']['structuredExit'] for c in unknown_recorded)),
        'firstReceivedEnvelopeOnly':True,'historicalReconstruction':False}


def failure_envelope_evidence(failed):
    recorded=[c['responseEnvelope'] for c in failed if c.get('responseEnvelope') is not None]
    return {'recorded':len(recorded),'notRecorded':len(failed)-len(recorded),
        'responseKinds':dict(Counter(e['responseKind'] for e in recorded)),
        'categorySources':dict(Counter(e['failureCategorySource'] for e in recorded)),
        'firstReceivedEnvelopeOnly':True}


def diagnostic_report(j, calls=None, providers=None, day=None, utc_offset_minutes=0):
    if type(utc_offset_minutes) is not int or not -840 <= utc_offset_minutes <= 840:
        raise ValueError('invalid_utc_offset')
    if day is None and utc_offset_minutes:
        raise ValueError('date_required_for_offset')
    now = time.time()
    calls = j.calls() if calls is None else calls
    calls = [c for c in calls if providers is None or c['provider'] in providers]
    period = {'kind': 'retained-window', 'days': 30}
    if day is not None:
        if not isinstance(day, str) or len(day) != 10:
            raise ValueError('invalid_date')
        try:
            parsed = date.fromisoformat(day)
            if parsed.isoformat() != day:
                raise ValueError()
        except ValueError:
            raise ValueError('invalid_date') from None
        zone = timezone(timedelta(minutes=utc_offset_minutes))
        start = datetime.combine(parsed, datetime.min.time(), zone).timestamp()
        calls = [c for c in calls if start <= (c['startedAt'] if c['startedAt'] is not None else c['endedAt'] or 0) < start + 86400]
        period = {'kind': 'local-day', 'date': day, 'utcOffsetMinutes': utc_offset_minutes}
    groups = defaultdict(list)
    for c in calls:
        groups[(c['provider'], c['tool'], c['operation'])].append(c)
    rows = []
    for (provider, tool, operation), items in groups.items():
        known = [c for c in items if c['paired'] and c['outcome'] in {'success', 'failed'}]
        failed = [c for c in known if c['outcome'] == 'failed']
        rows.append({'provider': provider, 'tool': tool, 'operation': operation,
                     'calls': len(items), 'knownOutcomes': len(known), 'failed': len(failed),
                     'unknown': sum(c['outcome'] == 'unknown' for c in items),
                     'pending': sum(c['outcome'] == 'pending' for c in items),
                     'unpaired': sum(not c['paired'] for c in items),
                     'observedFailureRate': len(failed) / len(known) if known else None,
                     'outcomeCoverage': len(known) / len(items),
                     'distinctFailedInputs': len({c['fingerprint'] for c in failed}),
                     'outcomeSources': dict(Counter(c['outcomeSource'] for c in items)),
                     'failureClasses': dict(Counter(c.get('failureClass','unknown') for c in failed)),
                     'failureClassSources': dict(Counter(c.get('failureClassSource','unreported') for c in failed)),
                     'failureEnvelope':failure_envelope_evidence(failed),
                     'needsFailureReview': len(failed) >= 3,
                     'sameCauseConfirmed': False})
    rows.sort(key=lambda r: (-r['failed'], -r['unknown'], -r['calls'], r['provider'], r['tool'], r['operation']))
    from command_profile import shell_tool
    from capability_report import observation_coverage
    command_coverage=[]
    for provider in sorted(set(providers or []) | {c['provider'] for c in calls}):
        commands=[c for c in calls if c['provider']==provider and shell_tool(c['tool'])]
        classified=[c for c in commands if c['operation'] not in {'unknown','legacy','shell','other',None}]
        unknown=[c for c in commands if c['operation'] in {'unknown','legacy','shell','other',None}]
        components=[c['commandComponents'] for c in commands if c.get('commandComponents') is not None]
        partial=[c for c in components if c['state']=='partial']
        command_coverage.append({'provider':provider,'calls':len(commands),'classified':len(classified),
                                 'unknown':len(commands)-len(classified),
                                 'unknownReasons':dict(Counter(c.get('recognitionReason','not-recorded') for c in unknown)),
                                 'classifiedRate':len(classified)/len(commands) if commands else None,
                                 'components':{'recordedCalls':len(components),'notRecordedCalls':len(commands)-len(components),
                                     'states':dict(Counter(c['state'] for c in components)),
                                     'partialCalls':len(partial),'recognizedInPartialCalls':sum(c['recognized'] for c in partial),
                                     'unknownInPartialCalls':sum(c['unknown'] for c in partial),
                                     'partialFamilies':dict(Counter(o['category']+'.'+o['family'] for c in partial
                                                                   for o in c['operations'] if o['family']!='unknown')),
                                     'executionVerified':False,'outcomeAttribution':None},
                                 'basis':'Recorded outer invocation only; opaque script purpose and execution unverified.'})
    inventory = [dict(r) for r in j.db.execute('SELECT * FROM inventory')
                 if providers is None or r['provider'] in providers]
    inventory_health = []
    for provider in sorted(set(providers or []) | {c['provider'] for c in calls} | {r['provider'] for r in inventory}):
        entries = [r for r in inventory if r['provider'] == provider]
        observed = [r['observed'] for r in entries]
        fresh = sum(0 <= now - at < 7 * 86400 for at in observed)
        inventory_health.append({'provider': provider, 'entries': len(entries), 'freshEntries': fresh,
                                 'state': 'unscanned' if not entries else 'current' if fresh == len(entries) else 'partly-stale',
                                 'oldestObservedAt': min(observed) if observed else None,
                                 'newestObservedAt': max(observed) if observed else None,
                                 'statuses': dict(Counter(r['status'] for r in entries)),
                                 'liveAvailabilityVerified': False})
    total = j.db.execute('SELECT count(*) FROM observation WHERE received>=?', (now - 30 * 86400,)).fetchone()[0]
    from journal import MAX_EVENTS
    return {'schemaVersion': 1, 'generatedAt': now, 'period': period, 'calls': len(calls),
            'toolGroups': rows[:50], 'toolGroupsTruncated': len(rows) > 50,
            'failureGroups': [r for r in rows if r['needsFailureReview']][:20],
            'failureGroupsTruncated': sum(r['needsFailureReview'] for r in rows) > 20,
            'inventoryHealth': inventory_health, 'analysisLimitReached': total > MAX_EVENTS,
            'commandCoverage':command_coverage,'skillEvidenceCoverage':observation_coverage(j,calls,providers),
            'resultEvidence':[{'provider':p,**result_evidence([c for c in calls if c['provider']==p])}
                              for p in sorted(set(providers or [])|{c['provider'] for c in calls})],
            'collectorVersions':[{'provider':p,'calls':len(items),
                                  'versions':dict(Counter(c.get('collectorVersion','unknown') for c in items)),
                                  'coverage':dict(Counter(c.get('collectorVersionCoverage','not-recorded') for c in items))}
                                 for p in sorted(set(providers or [])|{c['provider'] for c in calls})
                                 for items in [[c for c in calls if c['provider']==p]]],
            'completeCoverage': False, 'localOnly': True,
            'limitations': ['Rates cover only paired calls with a known native outcome.',
                           'Failure families do not establish the same cause or a missing skill.',
                           'Missing exit codes and historical error details cannot be reconstructed.',
                           'Inventory dates describe scans, not live connection or skill application.']}
