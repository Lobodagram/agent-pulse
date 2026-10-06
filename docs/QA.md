# Verification — 2026-10-06 / Проверка

Prepublication evidence, public counters excluded:

- 26 unit tests passed on Python 3.12/macOS. Quota clamping, unknown versus zero, data projection, secret omission, incremental/deduplicated counters, date validation, state permissions, cache behavior, provider selection, actual Qwen aggregate shape, Claude context semantics, Kimi quota units, loopback/redirect restriction and bounded portable RPC cleanup are covered.
- Native macOS app compiled with Swift 6.2.3, macOS 14 target. Own-window fixture captures inspected in English/Russian; compact 360×270, details 360×430, analytics 760×620, scrollable settings 560×620.
- Window diagnostics confirm floating level, all-spaces/fullscreen auxiliary flags, movable background, menu-bar item and hide/restore. Dragging, OS fullscreen behavior and sleep/wake still need interactive acceptance; flags are not proof of every desktop scenario.
- Live native Codex limits and account tokens RPCs responded, as did ZCode local usage/stats. No account values are published in this evidence.
- Claude/Kimi/Qwen adapters use current primary contracts and synthetic fixtures; no live account integration test is claimed.
- Windows source compiles as Python; actual Windows builds and demo UI are checked by the public workflow. Interactive DPI/tray/live client acceptance is pending. Linux support is collector/tests only.
- Public images use invented 2027 demo counters, not user screenshots or telemetry. Publication tree is allowlisted and starts a fresh Git history.

До публикации пройдены 26 тестов, сборка macOS и просмотр реальных изображений собственного окна. Штатная статистика Codex/ZCode на Mac ответила; личные значения не публикуются. Claude/Kimi/Qwen пока проверены на контрактах и вымышленных примерах. Windows проверяется workflow; ручная приёмка DPI/fullscreen/живых клиентов остаётся отдельной работой. Это предварительный релиз, не обещание полной проверки всех аккаунтов и ОС.

## Public CI

[Checks run 37422139777](https://github.com/Lobodagram/agent-pulse/actions/runs/37422139777) passed on Linux, macOS and Windows. Windows source demo UI smoke and macOS build/native fixture render passed. Package verification is recorded by the Release packages workflow; interactive acceptance and experimental live accounts remain pending.

Публичный CI прошёл на трёх ОС, включая запуск Windows-демо и сборку/изображение macOS. Упакованные сборки проверяет workflow релиза; ручная приёмка и экспериментальные аккаунты остаются открытыми.

## Package verification before v0.2.2

[Release packages run 37423000057](https://github.com/Lobodagram/agent-pulse/actions/runs/37423000057) passed for macOS ARM64, macOS Intel and Windows x64. Each package ran 26 tests. Both macOS applications rendered their own demo window, their frozen collectors listed the provider catalog, and final bundle signatures verified. The packaged Windows .exe completed the fixture UI smoke check, including its topmost state. Publication was intentionally skipped for this manual pre-release run; the tagged release performs the same checks and uploads the archives.

До v0.2.2 прошли сборки и проверки всех трёх пакетов: два macOS и Windows x64, включая запуск упакованного .exe. Финальная подпись macOS проверена. Ручная приёмка на разных дисплеях, sleep/wake и живых аккаунтах экспериментальных адаптеров остаётся открытой.

## Published v0.2.2

[Tagged run 37423472094](https://github.com/Lobodagram/agent-pulse/actions/runs/37423472094) completed successfully, including all three package jobs and the publication job. [Release v0.2.2](https://github.com/Lobodagram/agent-pulse/releases/tag/v0.2.2) contains Mac ARM64, Mac Intel and Windows x64 archives plus SHA256SUMS.txt. All three archives were downloaded back from the public release and their SHA256 hashes matched; project/runtime notices were found inside each package. This checks the delivered bytes in addition to the pre-release build.

Финальный workflow v0.2.2 прошёл полностью, архивы опубликованы. Все три пакета скачаны с публичного релиза; SHA256 совпали, лицензии проекта и среды присутствуют.

The downloaded macOS ARM64 package was extracted and tested on the development Mac: strict/deep code-signature verification passed, the bundled frozen collector returned its 11-client catalog, and the packaged app rendered its demo window. Own-window diagnostics passed floating level, all-spaces flags, hide/restore and menu-bar presence. This did not query accounts or replace the user's installed app.

Скачанный Mac ARM64-пакет проверен локально: подпись, встроенный сборщик и демонстрационное окно прошли; это не заменяет ручную приёмку всех сценариев рабочего стола.


## v0.3.0 local verification (2026-10-06)

66 unit tests pass on Python 3.12/macOS, including journal pairing, deduplication, failure/unknown outcomes, payload omission, concurrency/key stability, parallel/actor/turn separation, inventory provenance, comparison quality, native configuration preservation/removal and silent fail-open bridge/MCP rejection. These are contract tests with synthetic events, not proof that native live hooks are active in every client.

The native Mac app compiled with Swift 6.2.3/macOS 14 target. Actual own-window fixtures are rendered and inspected at 760×620 and 620×520, in English/Russian. Fresh Codex quota read matched the native desktop-tool read in the same verification interval; the previous cached metric was about four minutes old. This supports refresh timing as the likely discrepancy source, without proving the earlier 7%/8% pair. Fast quota reads do not query account tokens, create turns, call models or start peers. Independent reads can still briefly differ.

Core analytics uses invented scenarios, no private counters in public artifacts. A local CLI event → journal → report and bounded MCP path is covered; live Codex/GLM event delivery still requires an activated/trusted native hook and new session. New release/Windows/frozen-package outcomes will be recorded only after those checks finish.

66 тест прошёл локально; нативное Mac-окно собралось. Новые сценарии проверены на вымышленных событиях, без заявления о включённых живых хуках во всех клиентах. Свежий лимит сборщика совпал со штатным ответом в интервале проверки; прошлый кеш был примерно на четыре минуты старше. Причина прошлой пары 7%/8% предположительна; отдельное минутное обновление и время источника добавлены.


Account-switch regressions verify preserving general history, clearing account billing date and rejecting previous-account cached quota after a failed identity read. Metadata watching is implemented on both desktop clients; actual interactive switch-after-launch acceptance remains a separate check. No claim of universal IDE account discovery.


Final local source checks: 66 tests pass, including native quota fast-read isolation, account-scoped daily upserts/general aggregation and per-account manual-date restoration. Synthetic executable bridge → SQLite → journal report is silent and passes; round trip for two source hook processes plus report measured about 293 ms (not a model charge, not a universal latency guarantee). Codex and GLM observers are configured on the development machine; a new native session/trust review is still required to assert live delivery. Existing native configuration was preserved. Public figures use only invented data.

66 тестов и синтетический полный путь событий прошли. Наблюдатели Codex/GLM настроены локально; активация в новой сессии/проверка доверия ещё нужны для утверждения о живой доставке. Общая история сохраняется через смену аккаунтов; квоты и ручные даты разделены.


Native macOS interaction acceptance (isolated QA bundle, invented data): clicked Analytics → Workflows → Inspect evidence and verified paired failing calls in Sessions; edited task label and clicked Save review (demo correctly refused persistence), then opened Compare. The same installed user widget was not clicked or quit. EN/RU own-window captures and the 620×520 scrollable layout inspected. Hierarchy, typography, composition and product-specific evidence score 4/5 or better; no new permissions granted.

Нативные клики в отдельной тестовой сборке прошли: аналитика → сценарии → примеры → сессия, редактирование метки и безопасный отказ сохранения в демо, вкладка сравнения. Рабочий пользовательский виджет не закрывался. Окна EN/RU и минимальная ширина просмотрены.
