# Agent Pulse 0.14.0 — widget benefit evidence (source candidate)

A collapsed-by-default Pulse benefit disclosure per client now shows finding-linked tools, observed application, an explicitly pinned task comparison and separate daily cache input. Analytics → Compare can pin or clear the exact pair; refresh re-evaluates the existing quality/cohort/counter gates. Growth, zero and unavailable are distinct. Versions do not inflate tool counts; tool calls do not become model requests. No created-by-Pulse, causal or subscription-saving claim is inferred.

Для каждого клиента добавлена раскрываемая кнопка «Польза Pulse», по умолчанию свёрнутая: связанные с находками инструменты, наблюдаемое применение, явно выбранное сравнение на принятый результат и отдельная доля кэша за день. Пара сохраняется локально и пересчитывается при обновлении. Пропуски, рост расхода и нулевое изменение не скрываются. Верхняя монохромная панель сохраняет прежний вид.

[Metric definitions](WIDGET_BENEFIT.md) · [Значение показателей](WIDGET_BENEFIT.ru.md). The local macOS 0.14.0 build41 is installed and checked, preserving settings, enabled startup, observer paths and journal. Public 0.14.0 packages and platform CI remain separate gates. Public widget screenshots show invented DEMO data, not measured savings.

# Agent Pulse 0.13.0 — reviewed improvements and direct helper metrics

Repeated work can be required checks, process waiting or a different task. Human finding decisions now retain these reasons, including false positives; dismissed findings remain inspectable and can be reopened. Linked immutable skill/MCP/tool versions show whether they await use, acceptance or a comparable before/after review.

Reviewed tasks explicitly record suitability, declared application and bounded non-use reasons. Adoption uses only suitable selected tasks with known application; old/unassessed records stay unknown. Tokens, reported model requests, cache, task intervals and subscription allowance remain separate measurements. No human acceptance, causal benefit or exact subscription savings is inferred.

Direct helper receipts now group all retained runs by client, operation and public helper version. Successes/failures, known-result coverage, incomplete/stale runs, conflicts, missing starts, failed gates and paired median time are available through CLI/MCP. Native EN/RU Overview expands version groups; Windows source shows the same counters. Preview caps are explicit and do not discard overall totals. Repeated Reporter completion retries preserve their original timestamps instead of producing false conflicts.

macOS models, collection/configuration store, widget, token charts, analytics, settings and lifecycle now have separate Swift source files. Existing monochrome menu bar, window controls, privacy opt-ins and startup behavior are preserved. No new dependencies, model calls, conversation capture or telemetry uploads.

## Проверенные улучшения

Добавлены причины ручных решений, связь находки с версией инструмента и этапы её проверки. Применимость и причины неприменения задачи дают долю применения с явным охватом оценок; старые неизвестные данные остаются неизвестными.

Прямые квитанции показывают успехи, ошибки, пропуски, противоречия и время по клиенту, операции и версии. Повторная доставка завершения больше не создаёт ложный конфликт. Метрики квитанций отдельно от штатных исходов и приёмки человеком. Экономия подписки не вычисляется из них.

Интерфейс macOS разделён на модули. На рабочем Mac проверены локальная 0.13.0, сохранённый включённый автозапуск, прежние настройки, журнал и реальные квитанции. Новый ребут 0.13.0 и физическая приёмка Windows не проводились. Платформенные CI и скачанные пакеты фиксируются отдельно в [QA](QA.md).

Public screenshots use invented, DEMO-labelled metadata. They demonstrate behavior, not measured productivity or savings. [Collection contract](COLLECTION_HEALTH.md) · [Improvement review](IMPROVEMENT_LOOP.md).
