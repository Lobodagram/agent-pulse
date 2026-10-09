# Changelog

## 0.11.2 · 2026-10-09

- Explicit opt-in helper receipts record starts, results, versions, elapsed intervals and fixed check gates. They remain separate from native outcomes and human acceptance; conflicts and missing starts are visible.
- Analysis, task coverage and session continuation now use the complete retained window up to 100,000 events, removing the earlier 20,000-event analysis cutoff.
- Own journal health exposes quick integrity, retention, discarded-event counters and analysis truncation. Exclusive private verified backups omit credentials and native databases; no automatic restore.
- Task comparisons can show observed calls, elapsed intervals and explicit model requests independently of token availability, while retaining cohort and quality gates. Native/Windows overview and bounded MCP/review packs explain scope.
- Добавлены явные квитанции проверок, диагностика хранения и резервная копия собственного журнала без ключей. Неполные токены не блокируют доступные операционные метрики.

## 0.11.1 · 2026-10-09

- Existing opt-in Codex token collection now records a local device-day input/output/cache breakdown. Overview on macOS/Windows and the read-only efficiency MCP show cache share and breakdown coverage separately from account totals and reviewed-task metrics.
- Duplicate records, counter resets, schema gaps, skipped backlogs and UTC boundaries preserve partial coverage. Old counts are not replayed or marked complete. Malformed token payload shapes no longer interrupt collection.
- No inferred model requests, per-skill token attribution or subscription savings. The original compact menu bar remains unchanged.

## 0.11.0 · 2026-10-09

- Local immutable skill/MCP/tool versions link findings to bounded, non-overlapping reviewed tasks. Acceptance, declared application and observed name invocations remain separate.
- Per-client/version cards show tokens per accepted result including selected failed attempts, reported model requests, cache/input ratio and observed wall time with coverage.
- Reviewed-task comparisons require matching observed cohorts, reviewed quality and complete per-turn receipts. Missing counters do not produce subscription savings; default MCP remains read-only.
- Structured shell exit metadata and result-source diagnostics improve collection transparency. Historical session comparisons include observations beyond the 100-session UI preview.
- Explicit macOS app reopening restores a hidden widget or visible utility window without changing its placement preference.
- Добавлены версии навыков, приёмка отдельных задач и карточки пользы. Сравнение объясняет недостаток данных; токены, кэш и лимиты подписки учитываются отдельно.

## 0.10.4 · 2026-10-09

- Supplied Agent Pulse logo in macOS app icon/widget/utility headers, Windows executable/tray/window/header and GitHub identity.
- Exact approved artwork and native icon derivatives have a reviewed hash/format export gate; Windows source and packaged paths share resource discovery.
- Startup remains opt-in; the development account is enabled at the owner’s request after the previous acceptance restored it off. Reboot behavior is not claimed from app relaunch alone.

## 0.10.3 · 2026-10-08

- On macOS the widget has one close button that hides it while observation continues. Quit stays in the menu-bar context menu and Command-Q. Closing the widget preserves its placement preference. Header controls use their full rectangular hit area.
- Settings has visible fixed close/minimize buttons and native minimize support; closed/minimized windows reopen through the existing menu. An own-window fixture covers hide/restore and settings close/minimize/reopen.
- На Mac крестик скрывает виджет, выход остаётся в меню строки состояния. В настройках появились заметные кнопки закрытия и сворачивания.

## 0.10.2 · 2026-10-08

- Add an opt-in Launch at login checkbox: native SMAppService on macOS, a current-user Run entry on Windows, inverse removal, approval/error states and fixture isolation. Opening the app never registers startup automatically.
- Добавлена галочка «Запускать при входе в систему»: включение и отключение для текущего пользователя, без изменения автозапуска в демо.

- Prioritize exact repeated operations, retain control calls as sequence boundaries, and choose examples across sessions. Recognize fixed 3D QA and release/CI tool families without retaining arguments or reconstructing unknown shell payloads.
- Review packs expose operation classification coverage; the same frozen sample measures analyzer changes, not productivity or subscription savings.

Точные повторы получают приоритет; служебные вызовы больше не становятся примерами автоматизации. В отчёте виден охват классификации, неизвестные результаты сохраняются.

## 0.10.1 · 2026-10-07

- Display the actual installed version in the Mac/Windows Settings window title, helping identify historical copies. Correct stale candidate/publication wording in bundled EN/RU documentation. Analytics and Kimi contracts are unchanged.
- Версия установленных настроек видна в заголовке окна. Исправлены устаревшие пометки в документации; 0.10.0 tag/assets remain unchanged.

## 0.10.0 · 2026-10-07

- Add opt-in Kimi Code 2.x TOML observers and masked own-key controls on both UIs. Native snake-case tool-call IDs and numeric turns pair correctly; absent shell exits and per-call token/model fields remain unknown. Legacy Python kimi-cli and Kimi Work/Chat are separate, unverified integrations.
- Recognize declared Kimi quota windows; reject conflicting, duplicate and oversized window evidence. No quota-to-token conversion. Missing/failed/disconnected keys never restore another connection's cached quotas.
- Share the journal initialization lock with own GLM/Kimi key updates, preserving the journal HMAC and other providers. Existing glm-key CLI remains compatible; generic provider-key accepts bounded stdin only.
- Add bilingual architecture and setup boundaries, correct stale paid-plan/MCP documentation, and use precise window labels on Windows/Mac.
- Добавлены добровольные наблюдатели Kimi Code 2.x и защищённое поле ключа. Пройдены локальные проверки, CI всех платформ и сборка пакетов; живое подключение Kimi не проверено. Данные аккаунта и секреты в GitHub не переносились.

## 0.9.7 · 2026-10-07

- Fix Windows first-start contention: lock the byte range without writing a marker into an already locked region. Empty and legacy lock files both work; configuration locking follows the same rule. Journal key and SQLite WAL/schema preparation share one initialization lock. Windows acquisition polls with a bounded 750ms budget rather than one-second CRT retry intervals. Native hook deadlines remain two seconds.
- Three regression cases cover untouched lock bytes and real cross-process initialization exclusion; the packaged smoke also requires four concurrent first hook pairs to be retained.
- Bilingual agent setup now distinguishes OS/version/architecture, bundled app versus source/build dependencies, packaged MCP commands, unsupported targets and actual event-collection checks. UI and analytics algorithms are unchanged.
- Исправлены гонки одновременного первого запуска: на Windows больше нет записи в уже заблокированный байт; ключ и подготовка базы защищены одной блокировкой. Инструкция установки учитывает ОС, архитектуру и способ запуска. Физическая Windows-приёмка и доказательство экономии подписки остаются отдельными проверками.

## 0.9.6 · 2026-10-07

Conservative shell-result parsing rejects invalid wrapped exits and uninspected oversized suffixes instead of reporting false success. Seven regression tests and the frozen result/privacy-canary gate were added; Windows packaging immediately fails on a failed frozen smoke. See QA for delivered evidence.

Невалидные или неполные результаты команд сохраняются как unknown; границы анализа и приватность не ослаблены.

## 0.9.5 · 2026-10-07

MCP preference contention returns a retryable tool execution error (`isError: true`, `config_busy`) instead of an invalid-request error. Fixed literals only: no exception messages, paths or arguments. Real held-lock stdio tests verify unchanged bytes, continued ping and retry after release; packaged smoke exercises the same control path.

Mac already polls visual preferences every five seconds; verified live by changing the metric through local MCP and restoring it without restart/manual refresh. Snapshot/client-selection refresh remains separate.

Занятый файл настроек возвращает агенту понятную ошибку с возможностью повторить действие. Автоматическое подхватывание настроек на Mac подтверждено; интерфейс и доступ к данным не расширены.

## 0.9.4 · 2026-10-07

- Keep 0.9.3 immutable and source-only: ARM64 packaging failed the existing window-toggle fixture, so no release binaries were attached; Intel and Windows jobs passed.
- Fixture-only window focus checks now wait for observed active/key-window readiness with bounded deadlines, rather than assuming activation after 300ms. They additionally report and assert widget-key/utility-main/hide/restore states. Production window actions remain unchanged. The original CI failure was not reproduced in 10 local runs; an activation timing assumption is corrected, while its exact cause remains unproven.
-0.9.3 остаётся версией только с исходниками: пакеты не опубликованы из-за сбоя проверки ARM64. Тест фокуса теперь ждёт подтверждённого состояния окна и сохраняет промежуточные признаки; поведение окон продукта не менялось.

## 0.9.3 · 2026-10-07

- Serialize UI/CLI/MCP preference patches with a separate cross-process lock and monotonic configRevision. Unrelated fields merge; the last completed patch wins for the same field. Busy writes fail after one second without replacing the config. Windows also persists the selected language.
- Read-only settings inspect existing subscription rows without creating a state directory/database or running schema migrations. Unknown configuration fields and account locators remain private.
- Six regression cases cover three concurrent processes/36 writes, lock timeout/recovery, unchanged legacy database bytes and symlink rejection. UI and analytics behavior remain as in 0.9.2. First cold-start cause, signing, physical platform acceptance and measured analytical benefit remain open.
- Записи настроек из интерфейса, CLI и MCP больше не теряют изменения разных полей. Для одного поля сохраняется последнее применённое значение; при занятом файле действует ограниченный таймаут. Простое чтение настроек не создаёт базу и не меняет её схему.

## 0.9.2 · 2026-10-07

- Replace the daily Swift Charts plot with ordinary SwiftUI bars, readable zero/large-number axes and the same hover/click/day-selector details. No Swift Charts link or Metal chart initialization is required. Intel chart fixtures now run in source CI as well as packaged CI.
- 0.9.1 remains an immutable source-only preview: packaged Intel chart rendering aborted. Diagnostic run37592180734 reproduced `MTLLoader ... Target device architecture is nil`; ARM64/Windows passed. No binaries were published for0.9.1.
- График построен обычными элементами SwiftUI: сохраняются наведение, выбор дня, точные значения и понятные единицы. Проверка Intel добавлена в CI исходников. Причина прежнего падения подтверждена сообщением Metal; готовые пакеты0.9.1 не публиковались.


## 0.9.1 · 2026-10-07

- Readable K/M/B and тыс./млн/млрд token axes, daily hover/click details, accessible day selection and separate Tokens/Daily tokens views on Mac/Windows. Missing counters remain unknown.
- Repair Codex local projection: token totals no longer overwrite the file byte budget. Bounded backlog recovery resets the cumulative baseline, records a gap and labels partial history without attributing skipped older usage to today.
- Понятный график и точные дневные значения по клиентам. Исправлен пропуск свежих токенов Codex; локальный неполный охват и пропущенная история явно обозначены.

- Analytics and Settings use ordinary windows; the widget alone retains the configurable floating level. Repeated actions hide the active window, restore background/hidden/minimized windows, and reuse the same instance.
- macOS adds Analytics (⌘1) and Settings (⌘,) menu shortcuts and fixture-only window diagnostics. Windows reuses utility windows instead of opening duplicates.
- Аналитика и настройки уходят назад при переходе в другое приложение; кнопка возвращает окно, повторное нажатие скрывает активное. Виджет сохраняет режим поверх окон.

## 0.9.0 · 2026-10-07

- Portable setup/analysis skills and bilingual agent setup guide; explicit destination installer preserves existing skills.
- Read-only local settings MCP plus opt-in bounded control: preferences, manual billing dates and genuine finding/session reviews. No keys, arbitrary commands, native hook edits or model calls.
- Local visual preference synchronization, isolated Mac acceptance state/observer home, fixture language writes removed; comparison labels/results remain separate from session annotation and stale callbacks are ignored.
- Pasted GLM keys trim outer whitespace; failures carry fixed safe categories. Explicit no-key TLS diagnostic and packaged Windows CI gate.
- Prospective AGPL-3.0-only; published MIT rights/notices preserved. Public screenshot hash review and runtime-file rejection added to export.

Переносимые навыки, управление по явному выбору, безопасная диагностика GLM и переход новых версий на AGPL. Результаты проверок сборок и установленных пакетов публикуются отдельно в QA.


## 0.8.1 · 2026-10-06

- Fix frozen macOS HTTPS trust when the build Python framework CA path is absent: add OS-owned roots while retaining certificate/hostname verification and fail-closed behavior.
- Исправлено чтение квот GLM/Kimi упакованным Mac-обработчиком при отсутствующем CA-файле Python framework; проверка HTTPS остаётся обязательной.

## 0.8.0 — 2026-10-06

- Persistent Limits / Today widget switch on macOS and Windows; daily tokens never substituted by week/context totals. Menu/tray summaries retain quotas.
- Opt-in personal Z.ai Coding Plan quota adapter with masked own-state key entry/removal, five-hour/week remaining percentages, native reset times and no monthly MCP confusion. No native credentials extracted; configured-key scope is explicit; live verification awaits user connection.
- Переключатель «Лимиты / Сегодня», безопасное подключение личного ключа GLM, честные неизвестные значения.

## 0.7.2 — 2026-10-06

- Equal-window finding rechecks use the same detection/ranking/overlap rules with summary-only cards; no unnecessary inventory/capability SQL or display metadata. Separate windows are still evaluated separately.
- Regression coverage for all five pattern kinds, the top-30 limit, unknowns, provider/project/window boundaries and unchanged full finding output.
- Session pagination imports the shared numeric sanitizer directly.
- Перепроверка находок стала легче без изменения порогов, порядка и границ временных окон. Новые проверки защищают от ошибочного использования общей статистики вместо отдельных окон.

## 0.7.1 — 2026-10-06

- Unified numeric/name projections with the journal's stricter credential/path boundaries.
- Single literal version source drives wheel metadata, MCP and Mac bundle.
- Wheel excludes developer scripts; runtime hook and compatibility source entry remain.
- Chunked canonical snapshot hashing retains exact old digest and cursor compatibility.
- Isolated installed-wheel checks added to all source CI targets; Linux/headless instructions and README spacing.
 / Изменения

## 0.7.0 — reviewed improvement loop

- Literal registered skill-reader evidence, separate source counters and observed MCP namespaces; no raw command retention/backfill or arbitrary generic-category matches.
- Local manual finding decisions and bounded equal-window observational rechecks; unavailable counts remain unknown and no causal/token savings are claimed.
- Explicit UTF-8 CLI/MCP output and source reads, including legacy Windows console regression.
- Bilingual Markdown review export, fifth read-only MCP tool and one source-check/validated-handoff helper.
- Mac/Windows workflow controls; no peer runtime/configuration/model changes. Additive local tables preserve prior observer schema compatibility.


## 0.6.1 · 2026-10-06

- Clear empty-workflow states, collection timestamp/idle guidance and reviewed-label counts.
- Observed tools first, capability coverage summary, explicit unconfirmed events and optional Mac catalog expansion.
- Signed bounded snapshot session continuation on Mac/Windows/CLI/MCP; changed old evidence requires refresh, one-page JSON export and retention limits explicit.
- Full uppercase compact client names; Mac menu page fraction removed, rotation retained.
- Python version gate/package entry points, safe debug class, bilingual legacy suggestions and generated privacy canaries; 141 tests.
- Понятные пустые состояния, страницы сессий и полные названия в верхней панели без 1/2.

## 0.6.0 · 2026-10-06

- Per-call model sources, bounded observed model segments, unknown/conflicting identifiers and parallel-lane separation.
- Sessions on Mac/Windows, CLI/MCP, workflow evidence and comparisons show model evidence; missing native model data remains unknown.
- 130 unit tests include model changes, gaps, duplicates and overlapping calls; bilingual model guide and invented model-history screenshots.

## 0.5.2 · 2026-10-06

- Focus/restore fixture starts on text-only Workflows before view construction, isolating window assertions from the hosted Intel Metal chart abort diagnosed in 0.5.1. Graphs checked on the development ARM64 Mac; physical Intel graph acceptance remains open. Earlier failed tags preserved without binaries.

## 0.5.1 · 2026-10-06

- Native fixture checks launch their executable directly and wait for explicit app readiness before testing the second-instance guard. This avoids an Intel LaunchServices process-ID failure; assertions remain enforced and failures include stderr. 0.5.0 tag preserved, with no published binary assets.

## 0.5.0 · 2026-10-06

- Strict result provenance, structured exits, running-process states, conflicting-delivery reconciliation and collection gaps.
- Bounded compound-command families; parallel/nested/failed/pending calls break sequences; tool frequencies and cross-client candidates.
- Capability evidence separates registered skill loads, explicit invocations and declarations; inventory freshness and local CLI/MCP review packs.
- Mac Analytics/Settings restore and focus the existing window above ordinary windows on the active Space.
- 115 tests and 14 invented labeled mechanics cases; no full coverage, exact per-tool billing or savings claim.

## 0.4.1 · 2026-10-06

- Directory-based observer runtime removes per-event extraction; packaged hooks must pass the native two-second deadline.
- Explicit tool errors override zero exit codes. Failed, pending and invalid-timeline calls break workflow sequences.
- Unreported token components stay unknown; duplicate per-turn sources are not summed and conflicting components remain unknown.
- Lifecycle-only status differs from receiving tool calls; analytics readiness audit and current bilingual build instructions.

Исправлен запуск наблюдателя: встроенная среда в отдельной папке, проверка штатного тайм-аута. Устранены ложные успехи/цепочки/нулевые значения и повторный подсчёт токенов разных источников. Добавлен честный аудит готовности. Реальная активация хуков и применение скиллов не считаются доказанными тестовыми событиями.

## 0.4.0 · 2026-10-06

- MIT for the current original-source snapshot; copyright notice preserved. Earlier tags unchanged.
- Mac collapsed bar rotates one selected client every 8 seconds, both reported quota windows; optional foreground desktop selection with rotation fallback. No token-to-quota inference.
- Click opens the movable/resizable full widget; collapse keeps compact bar data.
- Windows small strip above taskbar, all-client pages, restore controls and native tray option.
- Integration feasibility documented; persistent injection into every desktop chat is not claimed.

## 0.3.3 · 2026-10-06

Remove redundant native Tk label padding, preserving readable fonts and fitting both English/Russian two-quota layouts at 80%.

- Keep Windows today tokens and quota resets on separate short rows so Russian two-client content fits at 80%. Test English/Russian source and packaged layouts. Windows supports `--language en|ru`.

## 0.3.2 · 2026-10-06

- Fix clipped Windows fields at 80% when both visible clients report quotas. Add a UTF-8 two-quota-client layout regression to hosted Windows checks.

## 0.3.1 · 2026-10-06

- Windows native tray: hover counters, click expand/collapse, context menu, Explorer recovery and visible fallback.

- Explicit quit button and production single-instance protection on Mac/Windows; fixture cleanup also runs on failure.
- Proportional widget sizing, 80/90/100% presets, continuous slider and lower-right resize grip; auxiliary windows retain their original size.
- Mac menu-bar-only mode, first-two-client compact indicators, icon-only option and click popover.
- Explain delayed Codex daily reporting; independent opt-in bounded local token projection supplies partial UTC-day counts without tool projection or double-counted account totals.
- Native fixture matrix and token-only privacy/dedup/pending tests.

## 0.3.0 — 2026-10-06

- Opt-in silent native Codex/ZCode/Claude observations, private SQLite journal and hashed evidence.
- Paired outcomes/durations, session timeline, workflow/retry/read discovery, explicit capability inventory and observational before/after review.
- Local bounded read-only MCP with three evidence tools; no model/API usage added.
- Mac and Windows tabbed analytics; preserved native hook configuration and separate Windows console helper.
- Codex limits refresh every minute with quota-source time; counters every five minutes. Independent reads can still briefly differ.
- Privacy/concurrency/provenance regression tests and bilingual setup/limitations.

Новый локальный журнал, сценарии, доказательства, сравнение вариантов и MCP аналитики. Лимиты Codex обновляются раз в минуту с временем получения. Все наблюдатели добровольные; полный охват каждого шага и токены каждого инструмента не обещаются.


## 0.2.2 — 2026-10-06

- Resolve the Windows demo fixture to an absolute path before the frozen executable smoke check.
- Verify macOS ARM64, macOS Intel and packaged Windows x64 before publishing downloadable archives.

Исправлен путь демонстрационных данных при проверке Windows .exe. Все три упакованные версии прошли проверочную сборку до публикации.

## 0.2.1 — 2026-10-06

- Bundle the official Python 3.12 notice when a runner omits it; verify the final macOS signature after adding runtime notices.
- Show Windows token counters and human-readable reset times in the compact panel; explicit packaging search path.
- Keep independent package builds running if another architecture fails.

Исправлена упаковка лицензий Python и финальная подпись macOS. В Windows-виджет добавлены токены и читаемые даты сброса.

## 0.2.0 — 2026-10-06 (public preview / публичная предварительная версия)

- Selectable provider catalog with native, status-line, loopback, quota API and import adapters.
- English/Russian macOS UI, paging, source-aware analytics and manual billing dates.
- Windows Tk widget source, shared portable bounded RPC transport and package workflows.
- Explicit context-versus-spend semantics; local Codex projection disabled by default.
- Public demo screenshots, bilingual guides, privacy/security/contribution policy.
- PolyForm Noncommercial 1.0.0 plus separately negotiated paid commercial licensing.

Выбор клиентов, русско-английский интерфейс, отдельный показ контекста и расхода, предварительный Windows-виджет, сборки, документация и демонстрационные скриншоты. Анализ событий Codex по умолчанию выключен. Коммерческая лицензия приобретается отдельно.
# 0.9.6

- Reject malformed exit metadata inside recognized code-mode result objects instead of silently accepting a neighbouring valid exit. Explicit failure keeps priority.
- Shell results exceeding the existing 10-block/128-KiB inspection bounds stay unknown; a skipped suffix cannot establish success. No larger payload retention or parsing budget.
- Seven outcome regression cases and a real frozen hook/journal check cover false success, privacy and conservative limits. Plain Codex shell hook stdout still cannot supply an exit code; this release does not claim broader native outcome coverage or reclassify historical events.
- Некорректный exit code в обёртке больше не маскируется соседним нулём; результат за пределами проверки остаётся неизвестным. Текст stdout Codex не превращается в доказательство успеха.
