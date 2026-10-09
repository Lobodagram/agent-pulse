# Agent Pulse 0.11.1 — local cache metrics / локальная аналитика кэша

The existing opt-in Codex token collector now reports local device-day input, output and cached input. Overview on macOS and Windows shows cache share and breakdown coverage; read-only `pulse_efficiency` returns saved counters without starting native collection. Account totals, task/version metrics and subscription allowance remain separate.

Validated vector deltas handle duplicate observations, UTC boundaries, missing schemas, resets and skipped backlogs conservatively. Older counts remain unprofiled; missing counters remain unknown. No model-request count, skill savings or subscription savings is inferred. Compact widget/menu-bar behavior is unchanged.

В «Обзоре» появились входные, выходные и кэшированные токены, доля кэша и охват детализации. Используется прежний добровольный локальный сбор. Эти данные показывают работу кэша на устройстве; экономия конкретного навыка требует полных счётчиков сопоставимых принятых задач. Проценты подписки не переводятся в токены.

Preview scope and actual checks are recorded in [QA](QA.md). The Codex transcript format may change; unsupported breakdowns stay unknown. Real reboot, physical Windows/Intel, multiple displays, live Kimi and notarization remain separate acceptance cases. No model calls or private telemetry publication.

---

# Agent Pulse 0.11.0 — reviewed-task efficiency / эффективность задач

Agent Pulse now links reviewed tasks to a specific skill, MCP server or tool version. Capabilities shows applied versions, observed identity-level invocations and task acceptance. Compare reports before/after differences only for sufficiently covered, comparable groups without a decline in acceptance.

Explicit native per-turn receipts can report input/output tokens, cached input and model requests. Tokens per accepted result include failed and rework attempts. Missing counters remain unknown; cache share, model requests, account allowance and subscription savings are separate measurements. Observed invocation names do not prove which version ran, and an observational difference does not prove causation.

The macOS and Windows analytics interfaces include asset registration and task-review forms. Local MCP adds bounded efficiency/comparison reads; writes require explicit --allow-control. Structured result metadata is interpreted conservatively. Reopening a hidden Mac widget restores it without changing placement. The original menu-bar ECG and compact quota text are retained.

Теперь Pulse связывает принятые задачи с версиями скиллов, MCP-серверов и инструментов. Можно оценить применение, качество результата, время, вызовы модели, токены и кэш — когда источник действительно сообщает эти данные. Сравнение «до/после» учитывает неудачные попытки и переделки; недостаточный охват и неизвестная экономия показываются явно.

Сборки остаются публичной предварительной версией. Результаты проверок записываются в [QA](QA.md). Реальные сопоставимые задачи нужны для оценки пользы; тестовые сценарии её не доказывают. Перезагрузка с включённым автозапуском, физическая Windows/DPI, Mac Spaces/разные экраны, живой Kimi и нотариализация остаются отдельными проверками. Модели не вызывались, приватная активность не публикуется.
