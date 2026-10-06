# Local workflow analytics

[Paged session viewing and empty-state guide](READING_ANALYTICS.md). In 0.6.1 CLI/desktop returns up to 500 calls per page, MCP up to 100. Continue with nextCursor; general-export recentCalls remains a preview.

[Русский](ANALYTICS.ru.md)

Goal: collect evidence for improving an agent workspace, then verify an improvement. All analysis is deterministic, on your device, without model calls or telemetry uploads.

## Enable observations

Settings → Local event observers → Enable Codex, GLM/ZCode or Claude. Existing native hooks and unrelated configuration are preserved; removing the observer removes its handlers only. Start a **new native client session**. Codex may require reviewing/trusting the local hook command. The installer does not bypass that trust review or start either agent. The UI confirms configuration, not live activation: verify that Workflows shows **receiving events** and paired calls after an ordinary task. A lifecycle event alone does not establish tool coverage.

Source checkout equivalents (Python 3.11+):

```sh
python3 collector.py hooks --provider codex --action install
python3 collector.py hooks --provider glm --action install
python3 collector.py hooks --provider codex --action remove
python3 collector.py journal --action report
```

Packaged Mac helper: `Agent Pulse.app/Contents/Resources/pulse-collector`. Windows: the separate `pulse-collector.exe` alongside `AgentPulse.exe`. Keep the helper at the installed path after configuring hooks; moving/deleting it breaks the registered path. Re-enable at the new location. Native clients must support the documented hook versions. ZCode uses process hooks; Codex/Claude use command hooks. Hook input is bounded at 1 MiB, has a 2-second native timeout and produces no stdout/context, permission decision or model call. It fails open; failures may lose events. Synchronous observer execution has a small CPU/time overhead, not a subscription model charge.

## Findings and their limits

- **Workflow**: 2–4 different operation categories recur in at least three distinct observed turns. Actor/session/project lanes are separated; overlaps, failed calls and gaps over ten minutes break chains. A sequence shows order, not causality.
- **Identical request**: a local HMAC fingerprint repeats at least four times across two turns. Input never persists verbatim.
- **Retries**: at least three observed failing calls with the same input. Fix the failure first; another MCP is not automatically the answer.
- **Repeated reads**: at least three reads of the same hashed resource and unchanged size/mtime in a turn. Metadata does not prove identical contents. Only explicit file-path tools support this hint; shell paths are never recovered/persisted.
- **Operation family**: ten calls across three turns, lower confidence. Known compound operations retain bounded sanitized families; unsupported/dynamic syntax stays unclassified. Static parsing does not prove branch execution.

Workflows → Inspect evidence opens an observed session. The recent UI/report preview is bounded; the desktop/CLI reads up to 500 calls per page, MCP up to 100, with nextCursor continuation. Old examples outside the preview remain accessible by hashed session ID while retained. Session wall span is displayed; overlapping tool durations are never totalled as elapsed work. A missing end is pending; shell completion without an exit status is unknown. Process launch and process completion may be different tools: this preview does not correlate all asynchronous subprocess lifecycles.

Tokens are native provider counters, not exact costs of a particular command. The journal can accept explicit native per-turn usage through its programmatic contract; **these hooks do not promise live turn-token reports**. No account-counter delta is attributed to a concurrent task or tool, and no subscription-percent-to-token conversion is made.

## Capability inventory

Explicitly scan only names from directories/configs you nominate; no skill instruction or source file is read:

```sh
python3 collector.py journal --action scan --provider codex --skills-dir /your/skills --config /your/config.toml
```

Import a JSON array with `provider`, safe `id`, `kind` (`skill/tool/mcp`), `category` (`read/search/edit/test/build/inspect/environment/remote/delegate/shell/other`), `status` (`configured/available/disabled/unavailable`). Mark `available` only after a real native connection check. Config scanning yields **configured**, never available. Inventory becomes stale after seven days. A category match is only a candidate; an absent match never establishes global absence or unnecessary use. The scanner replaces that provider's inventory and preserves the peer's timestamp.

## Compare and review

Sessions → choose session → enter a nonsensitive ASCII task label and variant (for example `test-module`, `before`), then mark accepted/failed/rework/unknown. Repeat after changing one workflow. Compare shows median observed call count/wall span and accepted/failed counts; at least three sessions per variant are needed for an observational result. Review model, effort, task difficulty and selection bias yourself. Unreported settings stay unknown. Failed/rework cases are included. This is not a causal experiment or a promised saving.

```sh
python3 collector.py journal --action compare --label test-module --before before --after after
python3 collector.py journal --action export --file /your/private/report.json
```

Reports/exports contain private activity metadata even without payloads. They are not uploaded or added to GitHub automatically. Review them before sharing.

## Optional local MCP

Start `python3 /absolute/checkout/collector.py mcp`, or register the installed `pulse-collector` helper with argument `mcp` in your native MCP client. Source-mode arguments must include the absolute collector path before `mcp`. No API key or port is required. Add global `--state /your/state` **before** `mcp` when using a custom journal. Available read-only tools: `pulse_report`, `pulse_session`, `pulse_compare`, `pulse_evidence`. No command execution, client control, skill installation or automatic agent loop is exposed. Reads may perform housekeeping of the tool's own cache. Registration is optional and does not happen silently.

## Coverage, retention and privacy

Only delivered native events are observed. Hosted tools, clients without hooks, disabled/rejected hooks, events during sleep/closed clients and internal reasoning may be absent. Imported aggregate stats and the legacy bounded Codex counter projection are **separate from this event journal**, and do not establish step-by-step tracing. Complete agent coverage remains unknown.

The own journal is SQLite, private local state, not a native conversation database. Session/project/resource/input identifiers are HMACs with a device-local key in `Secrets.json`; they are pseudonymous, not public-safe anonymity. No raw prompts, arguments, tool results, code, credentials, transcript content or absolute project paths persist in the journal. Only conservative fixed command shapes and sanitized tool/model names remain. Thirty-day/event-count housekeeping retains up to 100,000 events (checked each 500 events and on reports); reports analyze the newest 20,000 events. SQLite main database has a 256 MiB page limit; full/busy/invalid storage fails open, so events may be lost. Keep state backups together with Secrets.json; changing the key breaks correlation. No native client database is read/modified.

For the next improvement: inspect evidence → choose an existing capability or propose a tested script/skill/tool → test on comparable tasks → review quality and costs again. Agent Pulse supplies evidence; it does not silently rewrite your workspace.


Account changes: on desktop, selected supported clients' authentication/config file metadata only is checked every five seconds (no credential file contents). A change clears displayed previous values and requests a fresh read. Codex additionally verifies a native account identifier, stored only as a keyed hash, and isolates current account quota cache; previous manual billing date is cleared on a verified account switch. Failed/unknown-identity Codex reads never reuse previous-account quotas. Async replies captured before a switch are discarded. This is best-effort client-specific detection, not instant universal IDE account discovery: keychain-only logins or clients without a supported signal may require the normal minute poll/manual refresh. ZCode local usage is client history, not an automatically account-separated paid-plan total.


Work history remains continuous across account switches. The journal groups by provider/task, not login. Known Codex daily account reports are stored per hashed account/day, updated (not incremented) on each read, then summed for general daily history. Switching back does not count the same account twice. Earlier unscoped rows remain stored; if they overlap a known-account day, they are not added because identity/overlap cannot be verified. Therefore totals cover observed accounts only, not every account ever used. Current quotas and manual billing dates remain account-specific; GLM local aggregates remain client history.

[0.5.0 evidence contracts / Контракты 0.5.0](EVIDENCE.md).
