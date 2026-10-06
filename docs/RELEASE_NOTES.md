# Agent Pulse v0.3.0 · observed workflows / сценарии работы

English: opt-in native Codex/ZCode/Claude hooks now produce a private local event journal: paired starts/completions, outcomes, wall times and task boundaries. New Workflows, Sessions and Compare tabs expose repeated sequences, failed retries, evidence and manual quality review. An explicit skill/MCP inventory distinguishes configured from available; optional read-only local MCP supplies bounded evidence to agents. No models called, no raw prompts/arguments/results/code uploaded or retained.

Codex quota refresh is now one minute (counters five minutes), with the limit-read time visible. A fresh collector read matched the native desktop read during local verification; independently timed reads can still briefly differ. Percentages are quota allowance, not remaining token counts.

Русский: добавлены добровольные наблюдатели Codex/ZCode/Claude, собственный журнал, пары начала/завершения, исходы и время. Вкладки «Сценарии», «Сессии», «Сравнение» показывают повторы, ошибки, примеры и приёмку результата. Есть явный каталог скиллов/MCP и локальный MCP для чтения аналитики. Без вызовов моделей, хранения или отправки промптов/аргументов/результатов/кода.

Лимиты Codex обновляются раз в минуту, счётчики — раз в пять минут; время получения лимита видно. Свежий ответ сборщика совпал с ответом рабочего клиента при локальной проверке. Независимые обновления всё ещё могут кратковременно расходиться. Это остаток лимита, не число токенов.

Install matching Mac ARM64/Intel or Windows x64 zip. Windows includes both AgentPulse.exe and pulse-collector.exe; keep them together. Mac preview ad-hoc signed, not notarized; Windows unsigned. Source requires Python 3.11+, releases bundle Python 3.12.

After enabling an observer, start a new client session and review native hook trust if requested. Configuration does not prove activation: check paired events. Hosted/internal actions may be absent. No exact per-tool token attribution or guaranteed savings; before/after is observational. See bilingual analytics guide and QA evidence.

PolyForm Noncommercial 1.0.0; free noncommercial use, purchased separate written commercial license required. Source-available, not OSI open source.


Account changes: on desktop, selected supported clients' authentication/config file metadata only is checked every five seconds (no credential file contents). A change clears displayed previous values and requests a fresh read. Codex additionally verifies a native account identifier, stored only as a keyed hash, and isolates current account quota cache; previous manual billing date is cleared on a verified account switch. Failed/unknown-identity Codex reads never reuse previous-account quotas. Async replies captured before a switch are discarded. This is best-effort client-specific detection, not instant universal IDE account discovery: keychain-only logins or clients without a supported signal may require the normal minute poll/manual refresh. ZCode local usage is client history, not an automatically account-separated paid-plan total.


Work history remains continuous across account switches. The journal groups by provider/task, not login. Known Codex daily account reports are stored per hashed account/day, updated (not incremented) on each read, then summed for general daily history. Switching back does not count the same account twice. Earlier unscoped rows remain stored; if they overlap a known-account day, they are not added because identity/overlap cannot be verified. Therefore totals cover observed accounts only, not every account ever used. Current quotas and manual billing dates remain account-specific; GLM local aggregates remain client history.
