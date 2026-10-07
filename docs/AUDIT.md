## 0.9.5 delivered · 2026-10-07

[Source checks37606792500](https://github.com/Lobodagram/agent-pulse/actions/runs/37606792500) passed Linux, Windows, Mac ARM64 and Intel; [packages37607259728](https://github.com/Lobodagram/agent-pulse/actions/runs/37607259728) passed all three binaries/publication. Immutable tag59cd2fe1809da89b222930c3d8d7453066089303;130public hashes/modes verified.200tests, all3downloaded archive hashes/version26/notices/paths and two own credential stores raw/base64/hex over source/entries/four decoded runtimes passed with zero matches. Downloaded ARM64 strict/deep ad-hoc signature, first strict2s hook/journal/MCP, actual frozen busy/ping/retry,20widgetcases and5chartcases passed. Installed downloaded0.9.5 with prior0.9.4 retained, local keybytes0600/config semantics/observer path preserved. First native UI lookup timed out while exactly one app ran; exact-path retry succeeded.

Windows job112745666986 log contains parsed `mcpConfigBusyRetry: passed`, with no traceback. Code review also found that its next command could overwrite the smoke exit code: the main-only workflow follow-up now immediately throws on a nonzero smoke result. It does not rewrite the immutable tag or claim that this additional guard was used in0.9.5. No production payloads/events or client/model configuration changes. Current runtime and UI screenshots are unchanged apart from the stated MCP error semantics/version.

The Mac polling suspicion was disproved: the existing five-second timer calls `loadPreferences()`. Installed0.9.4 accepted Limits→Today→Limits via local MCP without restart/manual refresh; the requested field was restored and revision advanced normally. MCP lock contention was confirmed and corrected to a retryable fixed-literal tool execution result; only typed ConfigBusy is classified. Generic timeouts remain generic. Tests use actual independent processes, verify unchanged bytes and continued ping/retry. [MCP tool errors](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#error-handling) distinguish execution failures from protocol errors.

Prospective benefit gates below remain unchanged and precede any human-reviewed corpus. No causal/subscription-saving claim. Code remains9/10; analytical effectiveness7/10. Cold-first-launch cause, signing and physical acceptance remain open.

Подозрение о настройках Mac не подтвердилось; автоматическое переключение проверено в работающем виджете. Ошибка занятой блокировки исправлена без выдачи приватных данных. Критерии пользы не изменены и заданы до эксперимента.

## 0.9.4 delivered acceptance · 2026-10-07

[Source checks37601456705](https://github.com/Lobodagram/agent-pulse/actions/runs/37601456705) passed Linux, Windows, Mac ARM64 and Intel. [Packages37601980097](https://github.com/Lobodagram/agent-pulse/actions/runs/37601980097) passed all three binaries and publication. Immutable v0.9.4 is49e825e93f95b47a60adfd27f18444df8e7a6ca2;130 allowlisted source files matched hashes/modes.198 tests; isolated runtime wheel, entry points and six new settings regression cases passed. Frozen MCP settings read on absent state creates no directory/database. Native two-second synthetic hook/journal/MCP deadline remains unchanged and passed.

Three downloaded archives matched SHA256SUMS/runtime/notices/version/path checks. Two own local credential stores were compared raw/base64/hex over archive entries and four decoded Python archive surfaces: zero matches. This is the inspected scope, not a guarantee over every historical surface. ARM64 strict/deep ad-hoc signature,20 downloaded widget cases and five chart fixtures passed; all five charts visually inspected. UI design is unchanged from0.9.2 and the existing invented-data screenshots still represent it. No personal screenshots, state, conversations or private Git history were published.

Installed0.9.4/build25 at the stable development dist path using ditto; prior0.9.2 retained. Key bytes/0600 and configuration values survived replacement. Actual Codex and GLM quotas/day counters were received. Live installed UI confirmed all six analytics sections, legitimate empty comparison state, Settings hide/restore and Limits/Today/back. Non-sensitive toggles increment configRevision; original visual values were restored. Legacy visual preferences absent from config remain in native UserDefaults and were confirmed in the UI, not inferred from config. One installed instance. Initial native automation lookup timed out while the app was already running; retry against its exact path succeeded. No fake production events/reviews, peer launch, native hook/trust changes or model calls.

Code quality assessment9/10 is consistent with the supplied independent0.9.2 review; analytical effectiveness remains7/10. This release fixes configuration correctness, not proof of analytical benefit. Original0.9.3 focus-test CI cause remains unproven; its immutable source-only release records the failure. Readiness checks strengthen the fixture without changing production window behavior. Cold first-start, notarization/signing, physical Windows/Intel/Spaces/multi-display/sleep-wake and genuine accepted before/after corpus remain open.

## 0.9.4 focus-fixture correction · 2026-10-07

The 0.9.3 [package run37600531862](https://github.com/Lobodagram/agent-pulse/actions/runs/37600531862) failed on ARM64: window-focus reported utilityTogglePassed=false while restore/focus/placement passed. Intel and Windows passed; publication was skipped, tag9b72e61e8511d7c0981558f382af9fb651315693 remains immutable and source-only. Ten local repeated original focus cases passed; the exact CI cause is unproven.

The fixture assumed activation after 300ms. 0.9.4 waits for actual app-active/settings-key readiness with bounded deadlines before exercising the nonactivating widget, then records widget-key, utility-main, hidden and restored state. Assertions are extended, not waived. This changes fixture diagnostics only; production window behavior remains unchanged. Updated full gates are pending below.

## 0.9.3 settings consistency · 2026-10-07

Confirmed both GLM findings against 0.9.2: settings reads created metrics.sqlite and configuration used unsynchronized read/merge/replace. All built-in preference writers now share a bounded cross-process patch lock; revisions count completed writes, different fields merge, same-field conflicts remain explicitly last-completed-patch-wins. Read-only settings query existing subscription rows with SQLite mode=ro and no Store/schema initialization. Local verification passed: 198 unit tests, privacy export, Python syntax, 122 document links and isolated wheel/CLI/hook/MCP entry points. Six new regression cases include 36 writes from three independent spawned processes and timeout/recovery. The new frozen helper passed the native two-second synthetic hook/journal/MCP check; 20 own-window Mac fixture cases passed. Interactive isolated UI/MCP acceptance preserved language, metric mode, size, topmost and client selection across both writers. Public platform builds and downloaded/installed acceptance remain pending until separately recorded.

Cold-start phase timing inside the hook and automatic warm-up are deferred: pre-interpreter/quarantine time cannot be measured from inside Python, and warm-cache success cannot establish first-launch reliability. No unmeasured runtime warm-up or extra health writes were introduced. First-launch cause remains unknown. The prospective real before/after benefit gates already documented below remain unchanged; no invented reviews or acceptance labels. Development install remains the stable dist app; end users should choose a permanent location before installing observers.

0.9.2 delivered: source checks passed four platforms, package checks passed all three binaries, downloaded ARM64 installed/live acceptance passed; 192 tests and scoped source/archive key comparisons found no matches. See QA.md. Code 8.5/10; analytics 7/10; physical acceptance and large-session timeline/accessibility remain open.

## 0.9.2 · 2026-10-07

- Replace the daily Swift Charts plot with ordinary SwiftUI bars, readable zero/large-number axes and the same hover/click/day-selector details. No Swift Charts link or Metal chart initialization is required. Intel chart fixtures now run in source CI as well as packaged CI.
- 0.9.1 remains an immutable source-only preview: packaged Intel chart rendering aborted. Diagnostic run37592180734 reproduced `MTLLoader ... Target device architecture is nil`; ARM64/Windows passed. No binaries were published for0.9.1.
- График построен обычными элементами SwiftUI: сохраняются наведение, выбор дня, точные значения и понятные единицы. Проверка Intel добавлена в CI исходников. Причина прежнего падения подтверждена сообщением Metal; готовые пакеты0.9.1 не публиковались.

Final source, Intel and downloaded-package acceptance for0.9.2 are separate pending gates below. Physical Intel graphics still require user-machine acceptance.


### 0.9.1 daily counters and chart verification

Codex's local projection reused `total` for the file-byte budget and cumulative tokens. Large counters prematurely stopped reading and left a native-returned eligible file 278,576,866 bytes behind on this Mac. Separate `bytes_read` and `cumulative_total` fix the defect. A backlog over 4 MiB resumes from the bounded 2 MiB tail; its cumulative baseline resets, a hashed/dated gap is retained for 30 days, and the UI explicitly labels recent-only partial coverage. No skipped historical usage is assigned to today. Native account-day totals retain precedence. Regression tests cover 200-million counters, a 5 MiB oversized private line, backlog reset, deduplication and no path/body retention. The normal source snapshot now returns a nonzero partial Codex UTC-day counter; no invented events were inserted.

Mac Tokens view uses categorical UTC dates (avoiding date-bin timezone drift), readable axes, exact hover/selected-day details and a keyboard-accessible date selector. Windows Daily tokens supports day selection and exact per-enabled-client counts. Daily sources do not supply hourly counts. EN/RU, large/zero/missing values and minimum-size renders passed; long details scroll. Synthetic screenshots were regenerated for the changed analytics navigation. Source unit tests: 192 passed. Final frozen/platform checks are recorded separately after publication.

## 0.9.1 window behavior · 2026-10-07

Analytics/Settings use normal window level; the configurable floating level belongs only to the widget. Actions restore a background, hidden or minimized existing window and hide an already active window. macOS tests include a key nonactivating widget with a main utility window. Native menu shortcuts are Cmd+1 / Cmd+comma. Windows reuses its utility windows, rebuilds stale analytics on restore while retaining the selected tab, and leaves Settings edits intact.

Local source checks: 190 unit tests, privacy export, syntax and document links passed; 20 own-window Mac cases passed, including minimize/hidden restoration, toggle, key focus and normal utility versus floating widget. Interactive own synthetic Mac windows confirmed open/hide and application deactivation; the automation observation activates the selected app, so a separate physical background-click claim is not made. Platform CI and downloaded-package acceptance follow publication and are recorded separately.

Development installation is explicitly `dist/Agent Pulse.app` in the local product checkout; `/Applications` is the recommended end-user location, not the current development installation. Stable observer paths are preserved across replacement. No credentials or private state are included in packages or synthetic screenshots.

The supplied GLM audit was of 0.8.1, not 0.9.0. Key trimming, bounded safe failure categories and frozen Windows HTTPS verification already shipped in 0.9.0. Code remains 8.5/10; analytical effectiveness 7/10. Notarization, signing, physical Windows/Intel/Spaces/multi-display/sleep-wake and true cold first-start remain open. Gatekeeper is a hypothesis for the first-start delay, not a verified cause; signing does not guarantee that warning/reputation issues disappear.

Prospective benefit gates: at least three genuinely comparable before/after task pairs with an unchanged human acceptance criterion and accepted/failed/rework labels; 1/3/7-day observational rechecks with explicit models/gaps/unknowns. Separately review at least 20 real finding candidates with true/false/indeterminate verdicts and publish precision with its denominator and coverage limits. Pairing among received events is not absolute expected-event coverage. Sustained multiweek observations and physical checks must be actual evidence, not promises or synthetic data. No automatic model calls, peer launch, invented labels or causal subscription-saving estimate.

## 0.9.0 delivered verification · 2026-10-07

[Source Checks 37575139840](https://github.com/Lobodagram/agent-pulse/actions/runs/37575139840) and [tagged packages37575357265](https://github.com/Lobodagram/agent-pulse/actions/runs/37575357265) passed all targets. Immutable v0.9.0 is719a5ae1185a6327d0b20781e715a9a3bf4f370a;126public files matched hashes/modes.190tests, installed wheel/CLI/hook/MCP, both portable skill validators and actual isolated Mac button/section checks passed. Windows frozen HTTPS verified certificates/hostname against the fixed Z.ai endpoint without a credential. Physical Windows user-machine acceptance is separate.

All three [release archives](https://github.com/Lobodagram/agent-pulse/releases/tag/v0.9.0) downloaded and matched SHA256SUMS/runtime/notices/version/path checks. Exact personal key comparisons(raw/base64/hex) found no matches in entries or four decoded embedded CArchive/PYZ surfaces. ARM64 strict/deep signature, actual two-second hook/journal/six-tool MCP,20widgetcases and EN/RU model-history renders passed; renders inspected. Installed0.9.0/build21: single instance, stable observer path and key bytes/0600 preserved, prior bundle retained. Live own quotas, Limits/Today, foreground analytics/settings and configured capability inventory confirmed. Visual preferences remain correct; config bytes were reserialized by preference synchronization.

Staging default Python copytree dereferenced framework symlinks and signature validation rejected that copy before production replacement. Follow-on shell commands exercised the old helper and failed its version assertion; no state/credential change. Corrected to checked native ditto preservation; installed package then passed signature/helper/live acceptance. No inference, peer launch, native trust bypass, production fake events or invented review decisions. Current code assessment8.5/10, analytical effectiveness 7/10; unknown token/outcome fields remain unknown. Prior public confidentiality audit has partial CI scope, described below; these release files were independently checked.

Проверены исходники и пакеты всех платформ, скачанные архивы и установленная Mac-версия. Навыки и ограниченное MCP-управление доступны по инструкции; новые версии — AGPL-3.0-only, прежние MIT-права сохранены. Реальная польза улучшений, холодный старт, подпись/нотаризация и физические проверки платформ остаются отдельными этапами.

## 0.8.1 delivered verification · 2026-10-06

182 tests and isolated runtime wheel/CLI/hook/MCP pass. [Source Checks 37529586577](https://github.com/Lobodagram/agent-pulse/actions/runs/37529586577) passed Linux/Mac/Windows; [packages37529892811](https://github.com/Lobodagram/agent-pulse/actions/runs/37529892811) passed Mac ARM64/Intel, Windows and publication. Immutable v0.8.1 at51f0d21f5bfb5dc76acf2538c96d6e0d8bfcb186;116 public hashes/modes matched.

All three [release archives](https://github.com/Lobodagram/agent-pulse/releases/tag/v0.8.1) downloaded and matched SHA256SUMS/runtime/notices/path checks; Mac embedded versions0.8.1 verified. Exact private key absent from every archive entry. Downloaded ARM64 strict/deep signature, actual two-second frozen hook/journal/MCP,20 widget cases and EN/RU model renders passed, changed renders inspected. Live GLM five-hour/week percentages and reset fields verified using the normal downloaded helper, without environment overrides. Installed that release0.8.1/build20: one instance, config stable, prior/source bundles preserved. Installed strict helper passed; own live UI confirmed quotas, Today switch and returning to quotas. Private live account screenshots are excluded from public export.

Personal key remains only in local own Secrets.json mode0600, supplied through masked Settings for other users. No inference, peer start/config/trust change, native credential read or telemetry upload. Core analytics effectiveness remains7/10 pending accepted comparable tasks; cold first-start, signing/notarization and physical Windows DPI/Intel charts/Spaces/fullscreen/multi-display/sleep-wake remain open.

## 0.8.1 frozen macOS HTTPS correction · 2026-10-06

Live installed 0.8.0 exposed an HTTPS trust-path packaging defect: the frozen Python framework CA file was absent on the development Mac, while source reads worked. A scoped comparison with the OS-owned /etc/ssl/cert.pem made the same frozen quota GET succeed. 0.8.1 adds OS roots to the frozen Mac HTTPS context with certificate/hostname verification required; no insecure TLS fallback, redirects, proxies or credential changes. Missing/invalid roots remain fail-closed. Four regressions cover strict verification, Mac roots, other runtimes/platforms and invalid roots. Native package/live acceptance is recorded after verification.

## 0.8.0 GLM quotas and metric selection · 2026-10-06

178 tests and isolated wheel/console/hook/MCP pass. Source Mac strict two-second frozen helper and 20 own-widget cases pass, EN/RU model-history fixtures inspected. Live personal Z.ai five-hour/week quota percentages and native reset fields verified on the development Mac. Source CI and release-package verification remain independent gates. Local tokens and configured-key quotas remain separate. No native credentials/config/session or model calls changed. No subscription savings claim; analytics effectiveness remains 7/10 and cold-start/physical/signing risks stay open.

## 0.7.2 window review · 2026-10-06

Third peer audit verified against canonical 0.7.1. A global finding list cannot replace separate provider/project/time-window detections: it would change qualification. Rechecks now use lightweight cards through the same detector, rank, overlap suppression and top-30 limit. Complete display cards remain unchanged. Session pagination imports the numeric sanitizer directly from its source.

Local fixture benchmark: 19,980 calls and 30 distinct completed review windows. Full cards and review results equal the previous committed implementation. Recheck SQL statements decrease from 61 to 1; median of three runs 79.63 → 75.37 ms on this Mac, peak traced allocation 155,656 → 135,774 bytes. These are fixture-only review measurements, not whole-app speed, native collection completeness or subscription savings. Distinct windows still require distinct detection passes.

The first downloaded0.7.2 frozen hook timed out at2seconds (cause unknown). Fresh copied-path diagnostics also exceeded that deadline on prior0.7.1 (3.4058s);0.7.2 measured0.3578s and later downloaded/installed strict tests passed. OS caches were not reset. Cold-start reliability is still open; native timeout/trust settings unchanged.

Five added regressions cover all pattern kinds, ranking/overlap/counts, top-30, unknowns, provider/project/window scope and no inventory/capability queries in the summary path. Engineering hygiene improves; effectiveness against the core analytics goal stays **7/10** pending representative accepted tasks and observational follow-up. Signing, slow-device hook starts and physical platform acceptance remain open.

Общий список находок нельзя подставлять вместо отдельных окон сравнения. Облегчённый расчёт сохраняет прежние результаты; замер на синтетическом журнале не доказывает экономию подписки или полноту сбора реальных событий.

## 0.7.1 audit hygiene · 2026-10-06

Shared strict sanitizers, canonical version and isolated runtime-only wheel checks close drift/package hygiene findings. Chunked hashing preserves exact snapshot integrity and previous cursors while reducing temporary allocation in a fixture benchmark. README spacing and Linux/headless guidance cleaned. Main-goal assessment stays 7/10 pending representative accepted effect evidence and stronger native outcomes/model coverage. Source quality and analytics effectiveness are separate judgements.

## 0.7.0 improvement-loop update · 2026-10-06

Manual finding decisions and equal-window rechecks, strict registered shell-read attribution, namespace counters, human Markdown packs and consolidated source/handoff checks are implemented. Mechanics tests pass (157), including provider scopes, reader false positives, partial outcomes, recheck absence/unknowns, CLI export and metadata validation. These additions improve the route from evidence to a reviewed change. Main-goal readiness remains 7/10 until comparable accepted real tasks demonstrate effectiveness and native client/model coverage is strengthened. A newly created shared helper/skill is an experiment, not proof of savings. Native Mac fixture/package checks and platform CI are separate gates; see QA for final delivery evidence. Prior assessments below are historical.

# Analytics readiness audit · 2026-10-06

## Current 0.6.1 assessment

**7/10 against the primary analytics goal.** Evidence is easier to inspect: observed tools precede registry entries, no qualifying patterns is distinguished from no calls, last collection time and reviewed-label counts are visible, and long sessions have signed bounded continuation. Python startup/packaging and privacy regression coverage improved; 141 tests. [Reading guide](READING_ANALYTICS.md), [verification](QA.md).

These repairs do not establish universal skill attribution, complete native collection or measured improvement effects. The thresholds were not lowered to manufacture findings. Local cold helper startup exceeded the native two-second budget on first trials; the downloaded release and installed helper subsequently passed that actual deadline. Full cold-start reliability remains an explicit limit. Native adapters, representative reviewed tasks and physical-platform checks remain the next gates. Earlier states follow.

## Historical 0.6.0 assessment

**7/10 against the analytics goal.** Native per-call model evidence, conservative observed-change timelines and bounded exports are implemented and covered by 130 tests. Real user-started ZCode work now supplies paired Read/Skill/Bash events including structured shell exits. This improves collection evidence but does not prove every step, sustained coverage or representative pattern accuracy. Observed ZCode tool events omit models: their model remains unknown. See [models](MODELS.md), [adapter proposal](CLIENT_ADAPTERS.md) and [dated verification](QA.md).

Model history must distinguish missing/conflicting identity, parallel work and unknown gaps; current UI selection is not historical evidence. A client plugin can package observers, but cannot expose undocumented billing data. Kimi Work/Chat compatibility with Kimi Code OAuth usage is unverified; remote paid ZCode plan and renewal adapters are not delivered. Subscription renewals remain manual unless a supported source explicitly reports them.

Remaining gates: supported native model/plan adapters, reviewed comparable real tasks and actual improvement acceptance; physical Windows DPI, Intel charts, multiple displays/Spaces/fullscreen/sleep-wake. Local fixtures and hosted package tests do not establish causal savings or a complete universal trace. The dated sections below describe earlier states.

## Historical 0.5.2 update

**7/10 against the primary analytics goal**: collection 6, bounded mechanics 8, capability attribution 6, effect evaluation 5, privacy 8, delivery 8. Engineering judgements, not certification. Representative reviewed real repeated tasks, completed ZCode shell outcomes and physical Windows acceptance remain missing. Synthetic precision is not production accuracy.

115 tests and 14 invented labeled mechanics cases cover operation distinctions, strict outcomes, parallel/nested barriers, registered capability evidence, provider isolation, retention and review packs. [OpenAI native payload code](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/context.rs) can deliver stdout-only shell hook responses; those deliberately remain unknown. See [current evidence contracts](EVIDENCE.md).

Source/tag 0.5.2 and three platform packages are verified in [QA](QA.md). Physical Intel chart rendering remains unverified; hosted focus checks use text-only Workflows.

The 0.4.1 sections below are historical. Generic compound grouping and absent capability attribution are superseded by bounded families and registered evidence. Semantic code interpretation and universal non-use proof remain unavailable.

[Русский](AUDIT.ru.md)

The product's primary goal is evidence for improving agent workspaces, not a quota meter. Readiness must include a real event path, useful findings and verified effects of subsequent changes. Current status: **public preview; not yet a complete continuous agent-work analysis system**.

## Findings corrected in 0.4.1

- The one-file frozen observer took 6–7 seconds to start on the development Mac, exceeding its configured 2-second hook deadline. Packages now use a directory runtime without per-event extraction. Packaged smoke tests enforce the actual 2-second budget, rather than a permissive 20 seconds. Native trust and new-session activation remain required.
- An explicit tool error alongside exit code zero could be reported as success. Explicit failure now takes precedence.
- Dropping failed calls before sequence analysis joined operations across failures. Failures and incomplete calls now break chains.
- A finish timestamp before its start could contribute to a sequence. Invalid timelines now break chains.
- A missing input/output token component could appear as zero. An unreported component remains unknown.
- Multiple sources for the same turn could double-count tokens. Matching values are counted once; conflicting components remain unknown.
- Lifecycle-only activity no longer has the same status as receiving tool events.
- Build guides now describe the current runtime/tray modes; the changelog is ordered and both READMEs describe analytics first.

## Verification and boundaries

83 unit tests cover pairing, retries, sequential versus parallel execution, actor isolation, incomplete/invalid calls, unknown values, inventory status, retention, privacy, inverse configuration and account history. Synthetic hook → private journal → report → local MCP verifies the event path without model calls. This does **not** establish delivery from a running native client.

For native acceptance: enable an observer, start a new session, review trust when prompted, execute a normal read/edit/test task and confirm receiving tool events, paired calls and inspectable evidence. Repeat similar tasks in at least three observed turns before expecting a workflow finding. Do not inject demonstration events into your real journal to pass this check.

Explicitly authorized native read/status acceptance on the development Mac subsequently established receiving and paired calls from Codex CLI 0.160.0 after its standard hook review. Shell outcomes remained `unknown`, with measured hook-wall durations; paired events alone do not establish an exit status. ZCode desktop 3.14.4 delivered a successful Read pair and the start of Bash, then displayed an overload error. Bash remained pending, so complete ZCode task/outcome coverage has not passed. The bundled ZCode CLI 0.16.9 independently failed during model creation before hooks. No raw hook payloads were retained or published; native conversation stores were not read; no model/account/subscription setting was changed. These were human-authorized acceptance tasks, not an Agent Pulse agent loop.

Native Codex and ZCode usage counters have been verified on macOS. These counters are independent of the workflow journal. Other providers vary from explicit bridges to imports; Windows hosted tests are not physical-device/DPI acceptance. See [QA](QA.md) for dated build/package evidence and [provider coverage](PROVIDERS.md) for each adapter.

## Important gaps relative to the goal

| Goal | Current evidence | Remaining work |
| --- | --- | --- |
| Continuous event collection | Deadline tests, real Codex pairs and ZCode desktop Read pair | Completed ZCode task, correct native shell outcomes, sustained and per-client coverage |
| Repeated work discovery | Deterministic category sequences, identical-input fingerprints, retries/read hints | More representative real tasks; reviewed false-positive/negative evaluation |
| Similar commands | Fixed command shapes and operation families | Compound commands collapse to a generic shape; no semantic code analysis |
| Skill/tool utilization | Sanitized tool calls and explicitly supplied inventory | Reading a skill is not proof of following it; no verified universal skill-use/non-use attribution |
| Missing MCP/skill discovery | Category-matched candidates with evidence | No match in an incomplete inventory does not prove absence; maintain reviewed live availability |
| Improvement evaluation | Manual quality/variant labels and observational comparison | Comparable tasks and verified acceptance; no causal or guaranteed token-saving claim |
| Multi-client coverage | Three opt-in native hook clients; other clients' counters/imports | Counters from a selected provider do not create a full command trace |

## Assessment

**6/10 against the primary analytics goal**, rather than the appearance of the widget. Collection readiness: 6/10 after bounded native acceptance; deterministic analytics: 7/10; capability attribution: 4/10; quality/effect evaluation: 5/10; privacy and bounded processing: 8/10; packaging/documentation: 8/10. These are engineering judgements, not benchmark results or a security certification. Real event receipt improves collection evidence, but the remaining unknown/pending outcomes and absence of representative repeated tasks prevent a higher overall readiness claim.

Priority: (1) prove the real event path, (2) collect and manually review repeated tasks, (3) add explicit skill-use evidence and inventory freshness, (4) evaluate precision of findings, (5) automate only a confirmed pattern and compare quality/work counts afterwards. A new model-driven loop, plugin catalog or vector database is not required to pass the first gate.

## Official contracts checked

[OpenAI hooks](https://learn.chatgpt.com/docs/hooks) require review of non-managed hook definitions and describe tool-coverage exceptions. [ZCode hooks](https://zcode.z.ai/en/docs/hooks) describe user configuration and session-start snapshots. The observer preserves these boundaries; it does not bypass trust or start agents.

## 0.9.0 candidate · 2026-10-07

Portable setup/analysis skills and explicit bounded local control now connect evidence to owner-requested settings and manual review actions. Read-only remains default; keys/native hooks/arbitrary execution are outside MCP control. Native hooks retain separate opt-in/trust. External agent inference follows that client's own policy; this utility itself makes no model calls.

GLM diagnostics distinguish fixed safe categories, pasted keys trim surrounding whitespace, Windows frozen TLS gets an actual packaged HTTPS gate. UI acceptance revealed comparison-message carryover and stale resize accessibility state; both were corrected. Fixture language no longer writes production preferences. Export rejects runtime-like files and requires reviewed screenshot hashes. Prospective AGPL transition preserves historical MIT grants and contributor copyright.

Code assessment remains 8.5/10, main analytical effectiveness 7/10. More controls and passing synthetic mechanics do not prove measured benefit. Need representative accepted before/after tasks, honest outcome/model/coverage review, and outstanding signing/physical/cold-start acceptance. No new causal subscription-saving claim. Candidate checks are recorded in QA; publication gates are pending.
# 0.9.6 conservative result correction — delivered

Contract review found a reproducible false-success case: malformed non-null exit_code inside a recognized code-mode object was ignored when another location supplied zero. The same problem existed past the ten-block inspection prefix. Invalid metadata now reports unknown; exceeded inspection bounds report fixed `result-limit-exceeded`. Native failure still wins; parsing remains bounded, no stdout heuristics or retained outputs. Seven focused regressions and the packaged helper gate cover these mechanics; final delivery evidence is recorded in QA.

207tests and source Checks37610410539 passed all four platforms. Immutable tag7ef6544932e9a6288fc44a6201dfa8da42c17eb7 and package/publication37610828204 passed all three targets; Windows logs explicitly confirm the new result gate. All downloaded archives passed SHA/version27/runtime/license/path checks and in-memory comparisons against two own Secrets stores over ZIP entries and four decoded Python surfaces: zero raw/base64/hex matches. Downloaded ARM64 signature, first isolated strict2s hook/MCP/result gate,20widget and5chart scenarios passed. Installed0.9.6 with keybytes0600/config semantics retained and prior0.9.5 available for rollback; actual widget and Settings/Analytics open-close checked. UI source and prior accepted demo screenshots are unchanged, no fresh chart visual acceptance claimed. One local test used a wrong helper path and failed before execution, then corrected; it is not a binary-start failure. These checks do not prove a true cold first launch or measured analytical benefit.

Codex 0.160.0 native source and current official hooks documentation confirm that the inspected ordinary shell hook path does not supply the structured code-mode exit object. No observer rewrite, child executor, model call, private native DB read or production backfill is introduced. Real metadata-only own-journal review confirms both missing Codex shell exits and existing GLM structured exits; personal counts stay local. Previously stored outcomes cannot be recomputed without raw results, which this product deliberately excludes. This correction improves confidence against false success, not coverage or measured benefit. Code9/10 and analytical usefulness7/10 stay unchanged; prospective corpus gates remain unchanged.
