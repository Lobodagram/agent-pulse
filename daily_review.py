"""One bounded local-day review; only Pulse-owned sanitized records, no RPCs."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time

from analytics import findings
from capability_report import observation_coverage
from diagnostics import diagnostic_report, failure_review_plan, failure_envelope_evidence
from journal import MAX_EVENTS, PROVIDERS
from sanitizers import number, safe_name

SAMPLE_LIMIT = 2000


def day_bounds(day, offset):
    if not isinstance(day, str) or len(day) != 10:
        raise ValueError('invalid_date')
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise ValueError('invalid_date') from None
    if parsed.isoformat() != day:
        raise ValueError('invalid_date')
    if type(offset) is not int or not -840 <= offset <= 840:
        raise ValueError('invalid_utc_offset')
    start = datetime.combine(parsed, datetime.min.time(), timezone(timedelta(minutes=offset))).timestamp()
    return start, start + 86400


def quota_summary(rows, start, end, truncated=False):
    """Reject stale/cached points, changed/reset/unknown windows and quota corrections."""
    groups = defaultdict(list)
    scopes = set()
    ready = 0
    for stamp, payload in rows:
        if not isinstance(payload, dict):
            continue
        observed = number(payload.get('quotaObservedAt'))
        if (payload.get('quotaStatus', payload.get('status')) != 'ready' or observed is None or
                not start <= observed < end or observed > stamp + 60 or
                'cached_previous_read' in (payload.get('sourceStatus') or [])):
            continue
        ready += 1
        scope = payload.get('accountScope')
        if isinstance(scope, str) and scope:
            scopes.add(scope)
        quotas = payload.get('quotas')
        if not isinstance(quotas, list):
            continue
        for q in quotas[:32]:
            if not isinstance(q, dict) or q.get('kind') not in {'primary', 'secondary'}:
                continue
            duration = q.get('durationMinutes')
            remaining = number(q.get('remainingPercent'))
            bucket = safe_name(q.get('bucket'))
            if (number(duration) is None or duration != int(duration) or not 1 <= duration <= 525600 or
                    remaining is None or remaining > 100 or bucket == 'other'):
                continue
            groups[(bucket, q['kind'], int(duration))].append({'observedAt': observed, 'remainingPercent': remaining,
                                                   'resetsAt': number(q.get('resetsAt'))})
    windows = []
    for (bucket, kind, duration), points in sorted(groups.items()):
        points.sort(key=lambda p: p['observedAt'])
        resets = {p['resetsAt'] for p in points}
        same = len(resets) == 1 and None not in resets and all(p['observedAt'] < p['resetsAt'] for p in points)
        correction = any(b['remainingPercent'] > a['remainingPercent'] for a, b in zip(points, points[1:]))
        eligible = same and not truncated and not correction and len(scopes) <= 1 and points[0]['observedAt'] < points[-1]['observedAt']
        windows.append({'bucket': bucket, 'kind': kind, 'durationMinutes': duration, 'observations': len(points),
                        'first': points[0], 'last': points[-1], 'knownResetWindows': len(resets - {None}),
                        'sameResetWindow': same, 'nonMonotonic': correction,
                        'consumedPercentagePoints': points[0]['remainingPercent'] - points[-1]['remainingPercent'] if eligible else None,
                        'basis': 'rounded account percentages between retained observations, not per-call cost'})
    return {'status': 'observed' if windows else 'not-observed', 'sampleRowsRead': len(rows),
            'readySampleRows': ready, 'sampleLimitReached': truncated, 'windows': windows,
            'accountContinuity': 'changed' if len(scopes) > 1 else 'reported-single-scope' if scopes else 'unreported',
            'exactMidnightCoverage': False, 'completeDayConsumption': None}


def metrics_summary(state, provider, day, start, end):
    """Read this utility's metrics.sqlite. Never initialize or query a native store."""
    result = {'quota': quota_summary([], start, end),
              'usageUTC': {'date': day, 'tokens': None, 'source': 'not-observed',
                           'billingCost': None, 'perCallAttribution': None}}
    path = Path(state) / 'metrics.sqlite'
    if path.is_symlink():
        raise ValueError('symlink_metrics')
    if not path.is_file():
        return result
    db = None
    try:
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.75)
        db.execute('BEGIN')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'samples' in tables:
            raw = db.execute('SELECT at,data FROM samples WHERE provider=? AND at>=? AND at<? ORDER BY at LIMIT ?',
                             (provider, start, end, SAMPLE_LIMIT + 1)).fetchall()
            rows = []
            for stamp, text in raw[:SAMPLE_LIMIT]:
                if not isinstance(text, str) or len(text) > 1024 * 1024:
                    continue
                try:
                    rows.append((stamp, json.loads(text)))
                except (ValueError, RecursionError):
                    continue
            result['quota'] = quota_summary(rows, start, end, len(raw) > SAMPLE_LIMIT)
        tokens = []
        if 'account_daily' in tables:
            tokens = [r[0] for r in db.execute('SELECT tokens FROM account_daily WHERE provider=? AND date=?', (provider, day))]
            if tokens and all(type(t) is int and t >= 0 for t in tokens):
                result['usageUTC'].update(tokens=sum(tokens), source='retained-account-reports', accountScopes=len(tokens))
        if not tokens and 'daily' in tables:
            row = db.execute('SELECT tokens,source FROM daily WHERE provider=? AND date=?', (provider, day)).fetchone()
            if row and type(row[0]) is int and row[0] >= 0:
                source = row[1] if row[1] in {'ZCode usage/stats', 'Codex bounded local events', 'Codex account/usage/read'} else 'retained-reported-aggregate'
                result['usageUTC'].update(tokens=row[0], source=source)
    except sqlite3.Error:
        # Discard a partially read metrics snapshot. Never serialize error text.
        result = {'quota': quota_summary([], start, end),
                  'usageUTC': {'date': day, 'tokens': None, 'source': 'unavailable',
                               'billingCost': None, 'perCallAttribution': None}, 'metricsStatus': 'unavailable'}
    finally:
        if db is not None:
            db.close()
    return result


def daily_review(j, day, utc_offset_minutes=0, provider=None):
    start, end = day_bounds(day, utc_offset_minutes)
    if provider is not None and (not isinstance(provider, str) or provider not in PROVIDERS):
        raise ValueError('invalid_provider')
    all_calls = j.calls()
    selected = [c for c in all_calls if start <= (c['startedAt'] if c['startedAt'] is not None else c['endedAt'] or 0) < end]
    providers = [provider] if provider else sorted({c['provider'] for c in selected} |
                                                   {r[0] for r in j.db.execute('SELECT DISTINCT provider FROM inventory') if r[0] in PROVIDERS})
    rows = []
    for ident in providers:
        calls = [c for c in selected if c['provider'] == ident]
        known = [c for c in calls if c['paired'] and c['outcome'] in {'success', 'failed'}]
        diag = diagnostic_report(j, calls=calls, providers=[ident])
        failures = []
        # Aggregate by tool independently of the diagnostic 50-group preview.
        by_tool = defaultdict(list)
        for c in calls:
            by_tool[c['tool']].append(c)
        for tool, items in by_tool.items():
            paired = [c for c in items if c['paired'] and c['outcome'] in {'success', 'failed'}]
            failed = [c for c in paired if c['outcome'] == 'failed']
            if failed:
                classes = dict(Counter(c['failureClass'] for c in failed))
                failures.append({'tool': tool, 'calls': len(items), 'knownOutcomes': len(paired),
                                 'failed': len(failed), 'failureClasses': classes,
                                 'failureEnvelope':failure_envelope_evidence(failed),
                                 'nextSteps': failure_review_plan(classes), 'sameCauseConfirmed': False})
        failures.sort(key=lambda f: (-f['failed'], f['tool']))
        candidates = findings(j, calls)
        examples = {c['id']: c for c in calls}
        cards = []
        for f in candidates[:5]:
            cards.append({k: f[k] for k in ['id', 'kind', 'title', 'titleRu', 'occurrences', 'sessions', 'confidence', 'action']} |
                         {'operations': f.get('operations', []), 'examples': [
                             {k: examples[cid][k] for k in ['id', 'tool', 'operation', 'outcome', 'startedAt']}
                             for cid in f['evidenceIds'][:3] if cid in examples]})
        receipts = j.db.execute('SELECT status,conflict,count(*) FROM check_run WHERE provider=? AND started>=? AND started<? GROUP BY status,conflict', (ident, start, end)).fetchall()
        reviews = j.db.execute('SELECT outcome,count(*) FROM reviewed_task WHERE provider=? AND at>=? AND at<? GROUP BY outcome', (ident, start, end)).fetchall()
        rows.append({'provider': ident, 'calls': len(calls), 'sessions': len({c['session'] for c in calls}),
                     'outcomes': dict(Counter(c['outcome'] for c in calls)), 'knownPairedOutcomes': len(known),
                     'outcomeCoverage': len(known) / len(calls) if calls else None,
                     'failureRateAmongKnown': sum(c['outcome'] == 'failed' for c in known) / len(known) if known else None,
                     'tools': dict(Counter(c['tool'] for c in calls)),
                     'commandCoverage': diag['commandCoverage'], 'skillEvidence': observation_coverage(j, calls, [ident]),
                     'collectorVersions':diag['collectorVersions'],
                     'resultEvidence':diag['resultEvidence'][0],
                     'failures': failures[:10], 'failuresTruncated': len(failures) > 10,
                     'candidates': cards, 'candidatesShown': len(cards), 'candidatePreviewTruncated': len(candidates) > 5,
                     'candidateAlgorithmLimitMayBeReached': len(candidates) == 30,
                     'helperReceipts': {'runs': sum(r[2] for r in receipts),
                                        'knownResults': sum(r[2] for r in receipts if r[0] in {'success', 'failed'} and not r[1]),
                                        'conflicts': sum(r[2] for r in receipts if r[1]), 'humanAcceptance': None},
                     'reviewsRecordedOnDay': dict(reviews),
                     **metrics_summary(j.state, ident, day, start, end)})
    total = j.db.execute('SELECT count(*) FROM observation WHERE received>=?', (time.time() - 30 * 86400,)).fetchone()[0]
    return {'schemaVersion': 1, 'generatedAt': time.time(), 'period': {'date': day, 'utcOffsetMinutes': utc_offset_minutes,
             'start': start, 'endExclusive': end}, 'providers': rows, 'analysisLimitReached': total > MAX_EVENTS,
            'completeCoverage': False, 'localOnly': True, 'modelsCalled': 0, 'causalSavings': None,
            'limitations': ['Calls are not accepted tasks; unknown outcomes are not successes.',
                           'Findings overlap and do not establish wasted work.',
                           'Quota deltas cover retained endpoints, not exact midnight or per-call cost.',
                           'UTC usage dates and local operation days differ when the offset is nonzero.',
                           'Error categories do not prove a shared cause; no automatic retry.']}


def daily_markdown(review, language='en'):
    if language not in {'en', 'ru'}:
        raise ValueError('invalid_language')
    ru = language == 'ru'
    tr = lambda en, local: local if ru else en
    offset = review['period']['utcOffsetMinutes']
    zone = timezone(timedelta(minutes=offset))
    def at(stamp):
        return datetime.fromtimestamp(stamp, zone).strftime('%H:%M:%S')
    lines = [tr('# Agent Pulse — daily review', '# Agent Pulse — дневная сводка'), '',
             f"{review['period']['date']} · UTC{offset / 60:+g}", '',
             tr('Observed calls, not accepted tasks. Coverage is partial.', 'Наблюдаемые вызовы, не принятые задачи. Охват частичный.'), '']
    if review['analysisLimitReached']:
        lines += [tr('WARNING: retained event selection limit reached.', 'ВНИМАНИЕ: достигнут предел выборки событий.'), '']
    for p in review['providers']:
        o = p['outcomes']
        lines += [f"## {p['provider'].upper()}", '',
                  tr('| Calls | Success | Failed | Unknown | Missing finish |', '| Вызовы | Успех | Ошибки | Неизвестно | Нет завершения |'),
                  '|---:|---:|---:|---:|---:|',
                  f"| {p['calls']} | {o.get('success', 0)} | {o.get('failed', 0)} | {o.get('unknown', 0)} | {o.get('pending', 0)} |", '',
                  tr('Native result evidence: ', 'Основания штатных результатов: ') +
                  ', '.join(f'{k}={v}' for k,v in p.get('resultEvidence',{}).get('terminalSources',{}).items()), '',
                  tr('### Account quotas', '### Лимиты аккаунта'), '']
        if not p['quota']['windows']:
            lines += [tr('No usable quota observations.', 'Нет пригодных наблюдений квоты.'), '']
        if p['quota']['sampleLimitReached']:
            lines += [tr('Quota preview capped; endpoints are from the bounded subset, consumption unknown.', 'Выборка квот усечена; крайние точки относятся к ограниченной выборке, расход неизвестен.'), '']
        for q in p['quota']['windows']:
            delta = q['consumedPercentagePoints']
            value = tr('unknown (reset, correction or incomplete observations)', 'неизвестен (сброс, корректировка или неполные наблюдения)') if delta is None else f"{delta:g} " + tr('percentage points', 'процентных пунктов')
            lines += [f"- {q['bucket']} / {q['kind']} ({q['durationMinutes']} min): {at(q['first']['observedAt'])} {q['first']['remainingPercent']:g}% → {at(q['last']['observedAt'])} {q['last']['remainingPercent']:g}%; " + tr('observed consumption: ', 'наблюдаемый расход: ') + value]
        lines += ['', tr('### Reported tokens', '### Сообщённые токены'), '',
                  f"UTC {p['usageUTC']['date']}: {p['usageUTC']['tokens'] if p['usageUTC']['tokens'] is not None else tr('unknown', 'неизвестно')} · {p['usageUTC']['source']}",
                  tr('Separate UTC day; no billing/per-call conversion.', 'Отдельный день UTC; пересчёта в стоимость или расход одного вызова нет.'), '',
                  tr('### Failure review', '### Разбор ошибок'), '']
        for f in p['failures']:
            lines.append(f"- {f['tool']}: {f['failed']} / {f['knownOutcomes']}; " + ', '.join(f'{k}={v}' for k, v in f['failureClasses'].items()))
            for step in f['nextSteps']:
                lines.append('  - ' + step['textRu' if ru else 'text'])
        if not p['failures']:
            lines.append(tr('No paired known failures observed; unknowns remain unknown.', 'Парных известных ошибок не наблюдалось; неизвестные исходы остаются неизвестными.'))
        lines += ['', tr('### Workflow candidates', '### Кандидаты на улучшение'), '']
        for f in p['candidates']:
            lines.append(f"- {f['titleRu' if ru else 'title']}: {f['occurrences']} · {f['confidence']} · `{f['id']}`")
        if not p['candidates']:
            lines.append(tr('No candidate met the thresholds in this selection.', 'В этой выборке нет кандидатов, достигших порогов.'))
        c = p['commandCoverage'][0]
        components=c.get('components',{})
        lines += ['', tr('### Automation evidence', '### Подтверждения автоматизации'), '',
                  tr('Classified shell calls: ', 'Распознаны shell-вызовы: ') + f"{c['classified']} / {c['calls']}",
                  tr('Component evidence coverage: ', 'Охват данных частей: ') +
                      f"{components.get('recordedCalls',0)} / {c['calls']}; " +
                      tr('partial chains / known parts: ', 'частичные цепочки / известные части: ') +
                      (f"{components['partialCalls']} / {components['recognizedInPartialCalls']}" if components.get('recordedCalls') else tr('unknown', 'неизвестно')) + ' · ' +
                      tr('component execution unverified', 'выполнение отдельных частей не проверено'),
                  tr('Unknown command reasons: ', 'Причины нераспознанных команд: ') + ', '.join(f'{k}={v}' for k,v in c.get('unknownReasons',{}).items()),
                  tr('Collector versions (not model versions): ', 'Версии сборщика (не версии модели): ') + ', '.join(f'{k}={v}' for k,v in p['collectorVersions'][0]['versions'].items()),
                  tr('Helper receipts (not human acceptance): ', 'Квитанции помощников (не приёмка человеком): ') + str(p['helperReceipts']['runs']),
                  tr('Task reviews recorded on this day: ', 'Оценки задач, записанные в этот день: ') + str(sum(p['reviewsRecordedOnDay'].values())), '']
    lines += [tr('Causal subscription savings: not measured.', 'Причинная экономия подписки: не измерена.'), '']
    return '\n'.join(lines)
