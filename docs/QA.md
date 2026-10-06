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

Core analytics uses invented scenarios, no private counters in public artifacts. A local CLI event → journal → report and bounded MCP path is covered; live Codex/GLM event delivery still requires an activated/trusted native hook and new session. Final package and delivered-byte outcomes are recorded below.

66 тест прошёл локально; нативное Mac-окно собралось. Новые сценарии проверены на вымышленных событиях, без заявления о включённых живых хуках во всех клиентах. Свежий лимит сборщика совпал со штатным ответом в интервале проверки; прошлый кеш был примерно на четыре минуты старше. Причина прошлой пары 7%/8% предположительна; отдельное минутное обновление и время источника добавлены.


Account-switch regressions verify preserving general history, clearing account billing date and rejecting previous-account cached quota after a failed identity read. Metadata watching is implemented on both desktop clients; actual interactive switch-after-launch acceptance remains a separate check. No claim of universal IDE account discovery.


Final local source checks: 66 tests pass, including native quota fast-read isolation, account-scoped daily upserts/general aggregation and per-account manual-date restoration. Synthetic executable bridge → SQLite → journal report is silent and passes; round trip for two source hook processes plus report measured about 293 ms (not a model charge, not a universal latency guarantee). Codex and GLM observers are configured on the development machine; a new native session/trust review is still required to assert live delivery. Existing native configuration was preserved. Public figures use only invented data.

66 тестов и синтетический полный путь событий прошли. Наблюдатели Codex/GLM настроены локально; активация в новой сессии/проверка доверия ещё нужны для утверждения о живой доставке. Общая история сохраняется через смену аккаунтов; квоты и ручные даты разделены.


Native macOS interaction acceptance (isolated QA bundle, invented data): clicked Analytics → Workflows → Inspect evidence and verified paired failing calls in Sessions; edited task label and clicked Save review (demo correctly refused persistence), then opened Compare. The same installed user widget was not clicked or quit. EN/RU own-window captures and the 620×520 scrollable layout inspected. Hierarchy, typography, composition and product-specific evidence score 4/5 or better; no new permissions granted.

Нативные клики в отдельной тестовой сборке прошли: аналитика → сценарии → примеры → сессия, редактирование метки и безопасный отказ сохранения в демо, вкладка сравнения. Рабочий пользовательский виджет не закрывался. Окна EN/RU и минимальная ширина просмотрены.


## v0.3.0 pre-release packages

[Checks 37429341671](https://github.com/Lobodagram/agent-pulse/actions/runs/37429341671) passed on Linux, macOS and Windows. [Pre-release packages 37429418213](https://github.com/Lobodagram/agent-pulse/actions/runs/37429418213) passed all three builds (Mac ARM64, Mac Intel, Windows x64) at source 5ae2ba82032731325e0ed53701139a2a99cc98ad. Each job ran all 66 tests; frozen helper checks exercised silent hook input → paired journal report → bounded read-only MCP. Mac own-window fixture/codesign and packaged Windows GUI tab smoke passed. Publication was intentionally skipped because this was a manual pre-tag run.

Проверки и все три упакованные сборки прошли. Каждый пакет проверил 66 тестов и полный синтетический путь событий через встроенную среду; Mac-окно/подпись и Windows-вкладки прошли. Это проверка поставляемой программы, не утверждение о живых аккаунтах всех провайдеров или полном охвате действий.


## Published v0.3.0 and delivered bytes

[Tagged packages and publication 37429892643](https://github.com/Lobodagram/agent-pulse/actions/runs/37429892643) passed all jobs. [Final source checks 37429809995](https://github.com/Lobodagram/agent-pulse/actions/runs/37429809995) passed Linux/macOS/Windows. The [v0.3.0 release](https://github.com/Lobodagram/agent-pulse/releases/tag/v0.3.0) contains Mac ARM64, Mac Intel, Windows x64 and SHA256SUMS.txt. All three published archives were downloaded back; every SHA256 matched. The Windows archive contains both the GUI and console collector executables.

The downloaded ARM64 app passed strict/deep signature verification, the bundled silent hook → paired journal → read-only MCP smoke, and an inspected Russian Workflows own-window fixture on the development Mac. The verified package replaced the existing widget, was launched through macOS LaunchServices, and its exact installed executable process was confirmed. Live installed-window inspection was blocked by the UI automation service retaining the prior bundle identifier; this is not counted as an additional live UI acceptance pass. The downloaded fixture and earlier isolated native clicks remain the rendering/interaction evidence. No private usage figures were published.

The local Codex/ZCode observers point to the installed frozen helper, preserving other settings. New client sessions and any native hook trust review remain necessary to establish live event delivery; configured inventory is not proof of receiving events. Interactive account switching, full desktop placement and Windows live-client acceptance remain open. Release tag is immutable; documentation follow-ups do not rebuild its packages.

Релиз опубликован, все три скачанных архива проверены по SHA256. Скачанная Mac-версия прошла подпись, синтетический полный путь событий и визуальную проверку сценариев. Виджет заменён и запущен; дополнительная проверка его живого окна через автоматизацию не засчитана из-за старого идентификатора в сервисе управления UI. Для живых событий нужны новые сессии клиентов и проверка доверия, если её запросит клиент.


## v0.3.1 local verification · 2026-10-06

69 Python 3.12 tests pass on the development Mac. New regressions distinguish delayed daily reporting from zero and verify token-only opt-in projection/deduplication without tool payload retention. A fresh native Codex usage report omitted the current UTC-day bucket; bounded local token projection provided a partial current-day counter on this device. Only availability is recorded, no private counts.

Mac Swift build and own-window fixture matrix cover 288×216 compact, 288×344 detail, synthetic resize-handler 348×261, real menu-only startup/popover and own status-button rendering, English/Russian, unknown today and two quota-bearing clients. Isolated native interactions verified Settings size/placement selection and accessible grip increment (80% to 85%); physical drag, multiple displays/Spaces/fullscreen and sleep/wake remain acceptance cases. Fixtures are invented.

Windows implements its own Win32 notification icon using Shell_NotifyIconW, no global input hooks: hover counters, click show/hide, context menu, Explorer restart re-registration and visible fallback. Source and packaged Windows smoke verify supported native tray registration/callback/recovery or explicitly report unavailable Explorer. Hosted platform results are recorded after the run; Windows live-client and DPI acceptance are not inferred from source compilation.

69 тестов прошли на Mac. Отсутствующий день отделён от нуля; локальные токены включаются отдельно и помечены частичным охватом UTC. Mac-матрица проверяет минимальные размеры, изменение масштаба, запуск в строке меню, настоящее всплывающее табло и вымышленные значения EN/RU. Windows-трей проверяется на Windows; ручная приёмка дисплеев и живых клиентов остаётся отдельной проверкой.


The Mac native fixture also verifies a second production launch exits while the existing fixture instance completes. Explicit quit/collapse controls and cleanup of fixture processes on failure prevent leftover test windows. Windows smoke additionally exercises session-local named-mutex lifecycle; its final hosted result follows below.


## v0.3.1 published evidence and v0.3.2 correction

[Checks 37441098618](https://github.com/Lobodagram/agent-pulse/actions/runs/37441098618) and [pre-release packages 37441176093](https://github.com/Lobodagram/agent-pulse/actions/runs/37441176093) passed at 871638ab47a4ddb7523c768a38bc39488d9e536c. [Tagged publication 37441584980](https://github.com/Lobodagram/agent-pulse/actions/runs/37441584980) passed all three packages and upload. All three v0.3.1 archives downloaded and matched SHA256; downloaded ARM64 signature and frozen hook/journal/MCP smoke passed. Windows source smoke reported actual tray registration, callback, collapse and restore; the native mutex lifecycle assertions passed. Mac source second-instance guard passed. Leftover development fixtures were closed; the original installed widget was retained while release delivery was verified.

An additional two-quota-client fixture first failed because the Windows test generator used the locale encoding; explicit UTF-8 repaired the test. The real layout regression [37442089212](https://github.com/Lobodagram/agent-pulse/actions/runs/37442089212) then found clipped fields at 80% on Windows. v0.3.2 reduces vertical padding and adds this case to source and packaged checks. The v0.3.1 tag/assets remain immutable; this is a separate patch release, not rewritten evidence. Final v0.3.2 outcomes follow below.

Базовые проверки и публикация v0.3.1 прошли, скачанные архивы совпали по SHA256. Дополнительная проверка Windows с двумя клиентами, у которых есть квоты, обнаружила обрезание при 80%. Исправление и этот тест входят в отдельный v0.3.2; старые файлы не подменяются.
