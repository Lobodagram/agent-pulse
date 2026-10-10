"""Small bilingual human review pack from sanitized local counters, no raw payloads."""
from datetime import datetime, timezone

def markdown_pack(report,language='en'):
    if language not in {'en','ru'}:raise ValueError('invalid_language')
    def tr(en,ru):return ru if language=='ru' else en
    def value(x):return '—' if x is None else str(x).replace('|','\\|').replace('\n',' ')
    lines=['# Agent Pulse — '+tr('review pack','пакет проверки'),'',
           tr('Observed metadata only. Missing is unknown; repeated does not mean waste.','Только наблюдаемые метаданные. Пропуск неизвестен; повтор не доказывает лишнюю работу.'),'',
           f"UTC: {datetime.fromtimestamp(report['generatedAt'],timezone.utc).isoformat()}",
           tr('Observed calls: ','Получено вызовов: ')+str(report['calls']),'',
           '## '+tr('Collection','Сбор'),'',
           '| '+tr('Client | Calls | Paired | Known result | Gaps','Клиент | Вызовы | Пары | Результат известен | Пропуски')+' |','| --- | ---: | ---: | ---: | ---: |']
    for r in report['coverage']:
        lines.append('| '+' | '.join(value(r.get(k)) for k in ['provider','calls','pairedCalls','knownOutcomes','collectionGaps'])+' |')
    for source,count in sorted(report.get('quality',{}).get('outcomeSources',{}).items()):lines.append(f'- {value(source)}: {count}')
    analysis=report.get('analysisCoverage',{})
    if analysis:
        lines+=['',tr('Operation families recognized: ','Распознаны семейства операций: ')+str(analysis['typedOperationCalls'])+
                tr('; unknown: ','; неизвестны: ')+str(analysis['unknownOperationCalls'])+
                tr('; bookkeeping excluded from pattern candidates: ','; служебных вызовов исключено из кандидатов: ')+str(analysis['bookkeepingCalls'])+'.',
                tr('Exact repeats precede broad sequence hypotheses. Historical unknown shell calls remain unknown.',
                   'Точные повторы показаны раньше общих цепочек. Старые неизвестные shell-вызовы остаются неизвестными.')]
    checks=report.get('checkRuns',{})
    if checks:
        lines+=['',tr('Helper receipts: ','Квитанции помощников: ')+f"{checks['knownResults']} / {checks['runs']}"+tr(' results known; conflicts: ',' результатов известно; противоречий: ')+str(checks['conflicts'])+'.',
                tr('Separate from native tool outcomes and human acceptance.','Отдельно от штатных исходов инструментов и приёмки человеком.')]
        groups=checks.get('byOperationVersion',[])
        if groups:
            lines+=['','| '+tr('Client | Operation | Version | Runs | Success | Failed | Known | Paired ms (n)',
                              'Клиент | Операция | Версия | Запуски | Успех | Ошибки | Известно | Парное время мс (n)')+' |',
                    '| --- | --- | --- | ---: | ---: | ---: | ---: | --- |']
            for row in groups[:10]:
                lines.append('| '+' | '.join(value(row.get(k)) for k in ['provider','operation','version','runs','successes','failures','knownResults'])+' | '+value(row['medianElapsedMs'])+f" ({row['timedRuns']}) |")
            if len(groups)>10 or checks.get('operationVersionsTruncated'):
                lines.append(tr('Helper table truncated; overall totals retain the full recorded selection.','Таблица помощников усечена; общие итоги по всей записанной выборке.'))
    storage=report.get('storageHealth',{})
    if storage:
        lines+=[tr('Journal quick integrity check: ','Быстрая проверка целостности журнала: ')+str(storage['integrity'])+tr('; analysis limit reached: ','; предел выборки достигнут: ')+str(storage['analysisLimitReached'])+'.']
    lines+=['','## '+tr('Tools (top 20)','Инструменты (первые 20)'),'', '| '+tr('Client | Tool | Calls | Failed | Unknown | Pending','Клиент | Инструмент | Вызовы | Ошибки | Неизвестно | Не завершено')+' |','| --- | --- | ---: | ---: | ---: | ---: |']
    for r in report.get('toolUsage',[])[:20]:lines.append('| '+' | '.join(value(r.get(k)) for k in ['provider','tool','calls','failed','unknown','pending'])+' |')
    lines+=['','## '+tr('Findings (top 10)','Находки (первые 10)'),'']
    for r in report['findings'][:10]:
        lines.extend([f"- {value(r['titleRu'] if language=='ru' else r['title'])} · {r['provider']} · {r['occurrences']} · `{r['id']}`",'  '+(r['suggestionRu'] if language=='ru' else r['suggestion'])])
    if not report['findings']:lines.append(tr('No candidate meets the thresholds in observed data.','В наблюдаемых данных нет кандидатов, достигших порогов.'))
    lines+=['','## '+tr('Reviewed decisions (top 10)','Решения по находкам (первые 10)'),'']
    for r in report.get('findingReviews',[])[:10]:
        lines.append(f"- `{r['findingId']}` · {r['status']} · {r['reason']} · {r.get('lifecycle','unknown')} · {r['recheckState']} · {r['windowHours']}h")
        for a in r.get('linkedVersions',[])[:5]:lines.append(f"  - {value(a['assetId'])} · {value(a['version'])} · {a['declaredUses']} "+tr('declared uses','отметок применения'))
    lines+=['','## '+tr('Capability evidence','Подтверждения навыков'),'']
    caps=[r for r in report.get('capabilities',[]) if r['loaded']+r['invoked']+r['declared']]
    for r in caps[:20]:lines.append(f"- {r['provider']} · {value(r['id'])} · read {r['loaded']} · invoked {r['invoked']} · declared {r['declared']}")
    lines+=['','## '+tr('Versioned usefulness (top 20)','Польза версий (первые 20)'),'',
            '| '+tr('Client | Asset | Version | Accepted / reviewed | Tokens / accepted | Cache / input','Клиент | Навык | Версия | Принято / проверено | Токены / результат | Кэш / вход')+' |','| --- | --- | --- | --- | ---: | ---: |']
    for r in report.get('efficiency',{}).get('assets',[])[:20]:
        lines.append('| '+' | '.join(value(v) for v in [r['provider'],r['assetId'],r['version'],f"{r['accepted']} / {r['reviewed']}",r['tokensPerAccepted'],r['cacheHitRate']])+' |')
    lines+=['']
    for r in report.get('efficiency',{}).get('assets',[])[:20]:
        lines.append(f"- {value(r['provider'])} · {value(r['assetId'])} · {value(r['version'])}")
        lines.append(tr('Stage: ','Этап: ')+value(r.get('lifecycle'))+tr('; applied / eligible: ','; применено / подходит: ')+f"{r.get('usedEligibleTasks',0)} / {value(r.get('eligibleTasks'))}"+tr('; adoption: ','; применение: ')+value(r.get('adoptionRate'))+tr('; eligibility reviewed: ','; применимость оценена: ')+f"{r.get('eligibilityKnownTasks',0)} / {r['tasks']}")
        for reason,count in sorted(r.get('nonUseReasons',{}).items()):lines.append(f"- {value(reason)}: {count}")
    lines+=['',tr('Adoption covers explicitly eligible selected tasks only. Incomplete application assessment yields unknown, not zero.','Применение учитывается только среди явно подходящих выбранных задач. Неполная оценка применения даёт неизвестное, а не ноль.')]
    lines+=['',tr('Usage includes selected failed attempts. Missing is unknown; manual version attestations are not native version invocation. Subscription savings are unavailable.','Расход включает выбранные неудачные попытки. Пропуск неизвестен; ручная отметка версии не равна штатному вызову версии. Экономия подписки недоступна.'),
            '',tr('Bounded summary; use session/evidence continuation for details. No per-tool costs, causal savings or universal skill non-use claim.','Это ограниченная сводка; подробности — в страницах сессий и примерах находок. Токены каждому инструменту и экономия не приписываются; неиспользование скиллов не доказано.'),'']
    text='\n'.join(lines)
    if len(text.encode())>32768:raise ValueError('review_pack_too_large')
    return text
