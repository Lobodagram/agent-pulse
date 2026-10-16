# Daily evidence and consolidated native QA

[Русский](WORKFLOW_AUTOMATION.ru.md)

These helpers consolidate existing work. They never start agents, query private client databases, change subscriptions or send telemetry elsewhere.

## One local-day review

```sh
python collector.py journal --action daily --date 2026-10-12 --utc-offset-minutes 120 --provider glm --format markdown --language en --file work/daily-glm.md
```

The read-only local MCP `pulse_daily_review` accepts `date`, optional `utcOffsetMinutes`, `provider` and `language`. Without `language` it returns JSON; with `en` or `ru` it returns Markdown. Without a provider the MCP includes clients observed on that day or present in Pulse's registry. The CLI retains its existing default provider (`codex`); specify `--provider glm` for GLM.

It reads calls once and counts the complete retained selection, independently of the 50-group diagnostic preview. It includes paired known outcomes, unknowns, five workflow candidates per client with bounded examples, fixed failure-category next steps, shell classification, skill evidence, helper receipt counts and task reviews recorded that day. A review recorded that day is not proof that a task started or finished on that day.

Quota data is read only from Pulse's own `metrics.sqlite`; no live provider requests or native client store reads are made. A missing store is not created. Stale/cached reads are excluded. Different quota buckets remain separate. A rounded percentage-point consumption is shown only between two usable observations in the same known reset window, with no account switch, upward correction or sample cap. Five-hour windows that reset during the day remain unknown for daily consumption. The sample limit is 2000 per client; capped endpoints are from the bounded subset and never establish total daily consumption.

UTC token aggregates remain a separate field with their source. A nonzero offset makes their day different from the local operation day. Cache discounts, billed tokens, per-call cost and causal subscription savings are not inferred.

## Compact economy review

```sh
python scripts/economy_review.py --date 2026-10-14 --utc-offset-minutes 180 --output work/economy-20261014
```

This repository helper queries the installed collector for Codex and GLM and prints a compact Russian report. Full sanitized evidence remains in a new local output directory. On other platforms pass `--collector /absolute/path/to/pulse-collector`. It invokes no model, background watcher or settings change; the installed application's UI is unchanged.

Priorities cover known failures, unknown command coverage, overlapping repetition hypotheses and genuine task acceptance. Repetitions are not established wasted work. Account quota endpoints, UTC token reports and accepted-task resources remain separate. For existing reviewed tasks add `--label <task-label> --before <baseline-variant> --after <improved-variant>` to reuse the existing metric-specific `compare-tasks` quality/cohort gates. No new acceptance, token estimate or causal subscription saving is inferred.

## One native fixture QA run

On macOS, pass a prepared Agent Pulse bundle, preferably a temporary candidate:

```sh
python scripts/native_qa.py --binary '/absolute/candidate/Agent Pulse.app/Contents/MacOS/AgentPulse' --output work/native-qa
python scripts/native_qa.py --binary '/absolute/candidate/Agent Pulse.app/Contents/MacOS/AgentPulse' --output work/native-qa-next --previous work/native-qa/receipt.json
```

The output must be a fresh directory. The helper runs existing widget, model timeline, chart and efficiency fixture suites sequentially, writes progress after each, and produces `receipt.json`, per-suite logs and `gallery.html` linking full-resolution screenshots. `--suites models charts` selects a narrower check. Unsupported operating systems are rejected rather than claimed tested.

Pass `--previous` only for a trusted local receipt. Reuse requires matching bundle bytes, demo fixture, runner, that suite's script and runtime/platform, plus retained hashes of every image and fixture receipt. Missing/tampered artifacts, failed suites and changed inputs invalidate reuse. The final input check invalidates results if a bundle or fixture changes during the run. A failed suite does not hide later suite results. Fixture processes use temporary copies with their own identifiers; installed app preferences and account state are not changed.

Automated assertions do not replace visual inspection. Review changed screens at full resolution, including RU/EN, minimum sizes and large/zero/missing counter cases. Reuse does not establish new human acceptance. This helper does not run source or frozen-collector checks; use the existing [build checks](BUILDING.md) and [QA contract](QA.md) for those gates.

## Error review before automation

Use `python scripts/workflow_check.py check --output work/preflight/check.json --test-log work/preflight/tests.log` to save a private bounded test log in the same run. Read that file on a failure instead of rerunning all tests for tracebacks. The summary/handoff contains only log status and size; private log contents and paths are not embedded. The optional log keeps the final 30000 UTF-8 bytes and marks truncation; it may omit earlier failures. Keep it local. This does not cache or skip required tests.

The daily report supplies fixed advice for reported syntax/reference/type/module/permission/timeout/connection categories. An unknown category remains unknown and requests a structured category on the next natural failure. Do not reconstruct historical messages, install packages without approval, or blindly retry operations that could already have changed state.

Quality-qualified before/after comparisons still require genuine task reviews, comparable scope and available resource measurements. See [the improvement loop](IMPROVEMENT_LOOP.md).
