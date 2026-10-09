# Skill, MCP and tool usefulness

[Русский](EFFICIENCY.ru.md)

Version 0.11.0 links an observed finding → immutable public asset version → bounded reviewed task → acceptance. All writes stay local; no model or paid evaluator is called.

Register a version in Capabilities, optionally linked to a finding. In Sessions select contiguous first/last calls on the current page, public task-family/variant/acceptance-criterion labels and genuine acceptance. Select one primary asset version if appropriate. Its application checkbox is a manual attestation, distinct from observed name invocations. Overlapping tasks are rejected. Re-reviewing the same selection and identity updates outcome/application without duplication. Long tasks cannot be split just to improve a score. Task boundaries must belong to one client, session, actor and project.

Cards show accepted/reviewed tasks, token coverage, reported model requests and observed wall-time coverage. Tokens per accepted result include input+output of **all** selected attempts, including failures, rework and unreviewed attempts. Cached input is already a subset of input; cache/input is a ratio, not subscription savings. Unknown model-request counts are never replaced by tool-call or turn counts. Median wall time includes waits and parallel activity, not active model time. Name invocation cannot establish version invocation. Adoption remains unknown without an eligible-task denominator.

Usage requires complete native per-turn counters, an explicit reporter completeness flag, paired calls and the entire observed turn inside the selection. Split/shared turns, late calls, conflicts, unknown turn boundaries and the event cap block completeness. Reporter completeness is not independently verified. Old receipts without completeness remain partial. Current hooks do not promise token receipts; a dash is expected until actual counters are available. Never invent receipts to populate a card.

Compare reviewed tasks per client in Compare; legacy session comparison remains available. A token difference requires at least three tasks per variant, matching observed project/model/criterion mixtures, all reviewed outcomes, complete usage and no acceptance-rate decline. This is a minimal display gate, not statistical significance or proof of equal difficulty. Reasoning settings, invisible work and causation remain unverified. The difference is observational. Quotas, credits, reported tokens and costs remain separate; no subscription savings conversion is performed.

CLI metadata uses `journal --action asset|task|usage --file metadata.json`, or bounded `--metadata` JSON, maximum 64 KiB. An asset requires `provider`, `assetId`, `version`, `kind` (skill/mcp/tool); optional `findingId` and explicit operation-family `operations`. Version definitions are immutable. A task requires `provider`, ephemeral `taskId`, safe public `label`, `variant`, `criterion`, `outcome`, hashed `callIds`; optional `assetId`, `version`, `applied`. Reuse the original ephemeral taskId for re-review; only its HMAC is retained. UI uses selection boundaries for this identity. Get call IDs from `pulse_session`, not display numbers.

Actual native usage import requires `provider`, native `sessionId`, `turnId`, nonnegative integer `input`, `cached_input`, `output`; optional integer `modelRequests` and boolean `complete` (false by default). Native IDs are immediately HMACed. Arbitrary source strings, content and estimated receipts are unsupported. No conversation database or stdout scraping is added.

```sh
python collector.py journal --action asset --metadata '{"provider":"codex","assetId":"release-helper","version":"1.0.0","kind":"skill"}'
python collector.py journal --action compare-tasks --provider codex --label release-check --before before --after after
```

Default MCP adds read-only `pulse_efficiency` and `pulse_compare_tasks`. Explicit `--allow-control` also exposes `pulse_register_asset`, `pulse_record_task`, `pulse_record_usage`. These affect only Pulse metadata, never native hooks, permissions or models. MCP previews mark truncation; use local CLI report for the full bounded report.

Task/usage evidence follows the existing 30-day window, up to 1000 tasks. The public version catalog persists until own-state cleanup, capped at 200 versions. One primary asset per task avoids independently crediting savings to several assets. Synthetic tests verify accounting, not production benefit. First genuine pilots: release checks and 3D export QA with stable acceptance criteria and both successful and failed attempts retained.
