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
    lines+=['','## '+tr('Tools (top 20)','Инструменты (первые 20)'),'', '| '+tr('Client | Tool | Calls | Failed | Unknown | Pending','Клиент | Инструмент | Вызовы | Ошибки | Неизвестно | Не завершено')+' |','| --- | --- | ---: | ---: | ---: | ---: |']
    for r in report.get('toolUsage',[])[:20]:lines.append('| '+' | '.join(value(r.get(k)) for k in ['provider','tool','calls','failed','unknown','pending'])+' |')
    lines+=['','## '+tr('Findings (top 10)','Находки (первые 10)'),'']
    for r in report['findings'][:10]:
        lines.extend([f"- {value(r['titleRu'] if language=='ru' else r['title'])} · {r['provider']} · {r['occurrences']} · `{r['id']}`",'  '+(r['suggestionRu'] if language=='ru' else r['suggestion'])])
    if not report['findings']:lines.append(tr('No candidate meets the thresholds in observed data.','В наблюдаемых данных нет кандидатов, достигших порогов.'))
    lines+=['','## '+tr('Reviewed decisions (top 10)','Решения по находкам (первые 10)'),'']
    for r in report.get('findingReviews',[])[:10]:lines.append(f"- `{r['findingId']}` · {r['status']} · {r['recheckState']} · {r['windowHours']}h")
    lines+=['','## '+tr('Capability evidence','Подтверждения навыков'),'']
    caps=[r for r in report.get('capabilities',[]) if r['loaded']+r['invoked']+r['declared']]
    for r in caps[:20]:lines.append(f"- {r['provider']} · {value(r['id'])} · read {r['loaded']} · invoked {r['invoked']} · declared {r['declared']}")
    lines+=['',tr('Bounded summary; use session/evidence continuation for details. No per-tool costs, causal savings or universal skill non-use claim.','Это ограниченная сводка; подробности — в страницах сессий и примерах находок. Токены каждому инструменту и экономия не приписываются; неиспользование скиллов не доказано.'),'']
    text='\n'.join(lines)
    if len(text.encode())>32768:raise ValueError('review_pack_too_large')
    return text
