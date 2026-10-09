# Collection and storage health

[Русский](COLLECTION_HEALTH.ru.md)

Version 0.11.2 separates native tool outcomes, helper-reported checks, and human task acceptance. A completed command is not a successful check. Helper receipts do not rewrite old native events or make unobserved activity visible.

Explicit helper receipt collection:

```sh
python scripts/workflow_check.py check --output work/check.json --pulse-state /absolute/private/pulse-state --pulse-provider codex
python collector.py journal --action checks
python collector.py journal --action health
python collector.py journal --action backup --file /absolute/private/backups/journal.sqlite
```

Only the fixed operation, public version, hashed run identity, timestamps, status, source-tree digest and allowlisted gate statuses persist. Provider assignment is reporter-declared. A receipt's start and finish deduplicate; mismatching final deliveries remain unknown. Missing starts, pending/stale runs and conflicts are exposed. Telemetry failure does not change the check result; the command's `receiptSaved` reports that failure. Receipts are retained for 30 days, with a 5,000-record bound. Source checks are opt-in; no native hook or model setting is changed.

`pulse_collection_health` and `pulse_check_receipts` are read-only MCP tools. `pulse_record_check` and `pulse_backup_journal` require an explicitly started `--allow-control` server. They never execute arbitrary commands, call models or restore a backup. Check receipts are reporter-supplied evidence, not independently verified native tool outcomes or user acceptance.

Health exposes a quick SQLite integrity check, stored-event count, the shared 100,000-event analysis/retention bound, 30-day retention policy, and counters for aged/capped events and aged receipts. Each counter records when tracking started: previously discarded data is unknown. The quick check is not a full integrity/recovery procedure; corruption is not automatically repaired.

Backup uses SQLite's consistent backup API, verifies the copy, and publishes exclusively without overwriting an existing file. POSIX file mode is 0600; Windows relies on the private user's filesystem permissions. The copied journal contains sanitized counters/HMAC identities, not Secrets.json, credentials or native databases. A keyed identity fingerprint binds it to the original local collector identity. No restore is performed. Keep the existing local identity for future collection after a deliberate recovery; credentials are not recoverable from this snapshot. Manual backup files do not expire with active journal retention.

Task comparisons expose independent coverage gates for observed calls per accepted result, the sum of observed task intervals per accepted result, explicit model requests per accepted result and tokens per accepted result. All include selected failed attempts; all retain cohort, review and quality gates. Missing tokens do not block an otherwise available operational metric. Time includes waiting; overlapping intervals can double-count clock time. These are observations, not causal proof or subscription savings.

Scope matters: 100% known helper receipts means all **recorded helper runs** have a result. It does not mean 100% native agent visibility. Hosted/specialized tools can lack hooks, and outputs vary by tool; see the [official hook coverage contract](https://learn.chatgpt.com/docs/hooks), checked 2026-10-09. Unknown results stay unknown.


Use the same original ephemeral runId for start/finish/retry. The returned runId is HMAC, not the original nonce; do not feed it back as a new producer identity.
