#!/usr/bin/env python3
"""Compact economy triage from the installed collector; no models or new telemetry."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

DEFAULT_COLLECTOR = Path('/Applications/Agent Pulse.app/Contents/Resources/pulse-collector')


def validate_period(day, offset):
    if date.fromisoformat(day).isoformat() != day or type(offset) is not int or not -840 <= offset <= 840:
        raise ValueError('invalid_period')


def summarize(dailies, comparisons=None):
    if not dailies:
        raise ValueError('missing_daily_review')
    period = dailies[0]['period']
    validate_period(period['date'], period['utcOffsetMinutes'])
    seen = set()
    providers = []
    for daily in dailies:
        if daily['period'] != period:
            raise ValueError('different_periods')
        for p in daily['providers']:
            ident = p['provider']
            if ident not in {'codex', 'glm'} or ident in seen:
                raise ValueError('invalid_or_duplicate_provider')
            seen.add(ident)
            unknown = sum(c['unknown'] for c in p['commandCoverage'])
            priority = []
            if p['failures']:
                priority.append('review-known-failures')
            if unknown:
                priority.append('resolve-command-coverage')
            if p['candidates']:
                priority.append('review-repetition-candidates')
            if not p['reviewsRecordedOnDay']:
                priority.append('collect-real-task-acceptance')
            candidates = [{'id': c['id'], 'kind': c['kind'], 'occurrences': c['occurrences'],
                           'operations': c['operations'], 'confidence': c['confidence'],
                           'automationReady': False} for c in p['candidates'][:3]]
            comparison = (comparisons or {}).get(ident)
            # Reuse the existing quality/cohort gates; never calculate a new reduction.
            metrics = None if comparison is None else {
                k: {f: v[f] for f in ('before', 'after', 'reduction', 'reasons', 'confidence')}
                for k, v in comparison['metrics'].items()}
            providers.append({'provider': ident, 'calls': p['calls'], 'outcomes': p['outcomes'],
                'knownPairedOutcomes': p['knownPairedOutcomes'], 'outcomeCoverage': p['outcomeCoverage'],
                'failureRateAmongKnown': p['failureRateAmongKnown'], 'commandCoverage': p['commandCoverage'],
                'resultEvidence':p.get('resultEvidence'),
                'failurePreview':[{'tool':f['tool'],'failed':f['failed'],'knownOutcomes':f['knownOutcomes'],
                    'failureClasses':f['failureClasses'],'failureEnvelope':f.get('failureEnvelope')}
                    for f in p['failures'][:3]],
                'quota': p['quota'], 'usageUTC': p['usageUTC'], 'priorities': priority,
                'candidatePreview': candidates, 'candidatesOverlap': True,
                'helperReceiptRuns': p['helperReceipts']['runs'],
                'reviewsRecordedOnDay': p['reviewsRecordedOnDay'],
                'comparison': None if comparison is None else {'metrics': metrics,
                    'reasons': comparison['reasons'], 'confidence': comparison['confidence'],
                    'causalClaim': False, 'subscriptionSavings': None}})
    return {'schemaVersion': 1, 'period': period, 'providers': providers,
        'generatedAt': max(d['generatedAt'] for d in dailies),
        'analysisLimitReached': any(d['analysisLimitReached'] for d in dailies),
        'completeCoverage': False, 'localOnly': True, 'modelsCalled': 0,
        'automaticActions': [], 'tokenSavings': None, 'subscriptionSavings': None,
        'acceptedTasksInferred': False}


def markdown(report):
    period = report['period']
    zone = timezone(timedelta(minutes=period['utcOffsetMinutes']))
    def at(stamp):
        return datetime.fromtimestamp(stamp, zone).strftime('%H:%M')
    lines = [f"# Pulse — экономия · {period['date']} · UTC{period['utcOffsetMinutes']/60:+g}", '',
        'Вызовы инструментов; охват частичный. Расход аккаунта не равен стоимости вызова.', '',
        '| Клиент | Вызовы | Успех | Ошибки | Неизвестно / ожидается |',
        '|---|---:|---:|---:|---:|']
    for p in report['providers']:
        o = p['outcomes']
        lines.append(f"| {p['provider'].upper()} | {p['calls']} | {o.get('success',0)} | {o.get('failed',0)} | {o.get('unknown',0)} / {o.get('pending',0)} |")
    if report['analysisLimitReached']:
        lines += ['', 'Достигнут предел анализа; счётчики относятся к ограниченной выборке.']
    for p in report['providers']:
        lines += ['', f"## {p['provider'].upper()}", '']
        if not p['quota']['windows']:
            lines.append('Лимиты: пригодных наблюдений нет.')
        for q in p['quota']['windows']:
            delta = q['consumedPercentagePoints']
            value = 'неизвестно' if delta is None else f'{delta:g} п.п.'
            a, b = q['first'], q['last']
            lines.append(f"- Лимит {q['bucket']}/{q['kind']}, {q['durationMinutes']} мин: {at(a['observedAt'])} {a['remainingPercent']:g}% → {at(b['observedAt'])} {b['remainingPercent']:g}%; расход между точками: {value}.")
        if p['quota']['sampleLimitReached']:
            lines.append('- Выборка квот усечена; полный расход неизвестен.')
        u = p['usageUTC']
        lines.append(f"- Сообщённые токены за отдельный день UTC {u['date']}: {u['tokens'] if u['tokens'] is not None else 'неизвестно'}. Это не стоимость подписки.")
        c = p['commandCoverage'][0]
        lines.append(f"- Shell: распознано {c['classified']}/{c['calls']}; неизвестно {c['unknown']}.")
        components=c.get('components')
        if components and components['recordedCalls']:
            lines.append(f"- Частичные цепочки: {components['partialCalls']}; известных частей в них: {components['recognizedInPartialCalls']}. Выполнение отдельных частей не подтверждено.")
        if p['failureRateAmongKnown'] is not None:
            lines.append(f"- Ошибки среди {p['knownPairedOutcomes']} известных парных результатов: {p['failureRateAmongKnown']:.1%}.")
        result=p.get('resultEvidence')
        if result:
            sources=result['terminalSources']
            lines.append(f"- Пропуски результата: без завершения {result['missingFinish']}; завершены с неизвестным исходом {result['unknownFinished']}; из них без распознаваемого кода {sources.get('exit-not-reported',0)}.")
            if result['unknownEnvelopeRecorded']:
                lines.append('- Формат неизвестных ответов (первая доставка): '+', '.join(f'{k}={v}' for k,v in result['unknownResponseKinds'].items())+'.')
        for failure in p.get('failurePreview',[]):
            lines.append(f"- Ошибки {failure['tool']}: {failure['failed']}/{failure['knownOutcomes']} известных результатов; категории: "+
                         ', '.join(f'{k}={v}' for k,v in failure['failureClasses'].items())+'.')
        advice = {'review-known-failures': 'Разобрать известные ошибки перед повтором; общая причина пока не подтверждена.',
            'resolve-command-coverage': 'Посмотреть новые причины неизвестных команд перед автоматизацией.',
            'review-repetition-candidates': 'Проверить повторы на одинаковую цель; гипотезы пересекаются и не доказывают лишнюю работу.',
            'collect-real-task-acceptance': 'Для сравнения ресурса нужны реальные принятые задачи с одинаковым критерием.'}
        for key in p['priorities']:
            lines.append('- ' + advice[key])
        comparison = p['comparison']
        if comparison is not None:
            names = {'tokensPerAccepted':'Токены', 'observedCallsPerAccepted':'Вызовы',
                     'elapsedMsPerAccepted':'Время (мс)', 'modelRequestsPerAccepted':'Запросы модели'}
            for key, m in comparison['metrics'].items():
                reduction = m['reduction']
                result = 'не оценено (' + ', '.join(m['reasons']) + ')' if reduction is None else f'снижение {reduction:.1%}; наблюдаемое сравнение'
                lines.append(f"- {names.get(key,key)} на принятый результат: {result}.")
    lines += ['', 'Экономия токенов и подписки пока не установлена. Повторы и ошибки не пересчитываются в потерянные токены.',
        'Сводка работает без вызова модели. Полные очищенные данные остаются в локальных файлах.', '']
    return '\n'.join(lines)


def collect(collector, day, offset, providers, variants=None):
    def run(*args):
        result = subprocess.run([str(collector), 'journal', *args], capture_output=True,
                                timeout=45, check=True)
        if len(result.stdout) > 8 * 1024 * 1024:
            raise ValueError('collector_output_limit')
        return json.loads(result.stdout)
    dailies = []
    comparisons = {}
    for provider in providers:
        dailies.append(run('--action', 'daily', '--date', day, '--utc-offset-minutes', str(offset), '--provider', provider))
        if variants:
            label, before, after = variants
            comparisons[provider] = run('--action', 'compare-tasks', '--provider', provider,
                                        '--label', label, '--before', before, '--after', after)
    return dailies, comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    parser.add_argument('--utc-offset-minutes', required=True, type=int)
    parser.add_argument('--provider', nargs='+', choices=['codex','glm'], default=['codex','glm'])
    parser.add_argument('--collector', type=Path, default=DEFAULT_COLLECTOR)
    parser.add_argument('--output', type=Path, help='New local evidence directory')
    parser.add_argument('--label')
    parser.add_argument('--before')
    parser.add_argument('--after')
    args = parser.parse_args()
    try:
        validate_period(args.date, args.utc_offset_minutes)
        if len(set(args.provider)) != len(args.provider):
            raise ValueError('duplicate_provider')
        variants = (args.label, args.before, args.after)
        if any(variants) and not all(variants):
            raise ValueError('comparison_requires_label_before_after')
        if args.output and args.output.exists():
            raise ValueError('output_directory_must_be_new')
        dailies, comparisons = collect(args.collector, args.date, args.utc_offset_minutes,
                                      args.provider, variants if all(variants) else None)
        result = summarize(dailies, comparisons)
        text = markdown(result)
        if args.output:
            args.output.mkdir(parents=True, mode=0o700)
            evidence = {'dailyReviews': dailies, 'comparisons': comparisons}
            (args.output/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False)+'\n')
            (args.output/'summary.json').write_text(json.dumps(result, ensure_ascii=False)+'\n')
            (args.output/'review.md').write_text(text)
            for file in args.output.iterdir():
                file.chmod(0o600)
        print(text)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        # Native stdout/stderr and arbitrary exception text are not report content.
        print('Economy review failed; check date, collector and fresh output directory.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
