# Agent Pulse 0.11.2 — explicit results and storage health / результаты и хранение

Existing helper calls can complete without a native exit code, leaving outcomes unknown. Opt-in check receipts now retain explicit starts/results, public helper version, elapsed interval, source-tree digest and fixed check gates. Reporter evidence remains separate from native tool outcomes and human task acceptance; conflicting deliveries stay unknown. Missing starts and stale/incomplete runs are visible. No raw command, tool result, conversation, path or credential is retained in these receipts.

Analysis now includes the whole retained window up to 100,000 events, removing the earlier 20,000-event analysis cutoff. Own-journal diagnostics expose a quick integrity check, retention policy, stored-event count, analysis truncation and discard counters with a tracking-start date. A verified private SQLite snapshot can be saved without replacing an existing file; it excludes credentials and native databases. No automatic restore or repair. Manual snapshots do not expire with active journal retention.

Reviewed-task comparisons use separate coverage gates for observed calls, summed task intervals, reported model requests and tokens per accepted result. Missing tokens no longer block otherwise available operational comparisons; quality/cohort gates remain. Time includes waiting and overlapping intervals, and is not active model time.

Read-only MCP health/receipt tools and the EN/RU native/Windows overview show the scope. Receipt imports and backups require explicitly enabled control tools. Existing collection opt-ins, observer paths, settings and compact monochrome menu bar remain unchanged. No causal benefit, whole-agent visibility or subscription savings is inferred.

---

Добавлены явные квитанции помощников: начало, результат, версия, длительность и разрешённые статусы проверок. Они отдельно от нативных исходов и приёмки человеком. Повторы не суммируются, противоречия остаются неизвестными; команды, вывод, разговоры и ключи не сохраняются.

Диагностика собственного журнала показывает целостность, срок хранения, усечение анализа и удаления с датой начала счётчика. Проверенная резервная копия не перезаписывает существующий файл и не содержит ключей/нативных баз. Доступные операционные метрики сравниваются независимо от токенов, с сохранением критериев качества. Полный охват агентов и экономия подписки не заявляются.
