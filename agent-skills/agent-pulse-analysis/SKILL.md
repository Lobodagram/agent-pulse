---
name: agent-pulse-analysis
description: Analyze Agent Pulse local workflow evidence and review improvements to an agent workspace. Use for repeated command patterns, capability coverage and before/after observations, not generic subscription advice.
---

Start with `pulse_review_pack` (language en/ru) or `agent-pulse journal --format markdown --language en`. Read collection gaps, paired calls and unknown outcomes before interpreting findings. Expand only the relevant `pulse_evidence` or bounded `pulse_session` pages. Continue signed cursors unchanged; refresh a changed snapshot rather than merging incompatible pages.

A recurring call is a hypothesis, not proof that a new skill/MCP will help. Configured capability is not live availability; an observed skill read is not its application. Model history describes observed calls, not continuous use. Never infer exact per-tool token cost or subscription savings from call counts.

Choose the smallest improvement supported by the evidence: a reusable script for deterministic checks, a skill for routing/review, or MCP only when an actual tool contract warrants it. Check existing capabilities before proposing a duplicate. Preserve the owner-approved stack and privacy boundaries.

Agree a comparable task label, baseline, acceptance criterion, model/coverage caveats and intervention date. Implement and verify the real change before marking a finding actioned. Opt-in `pulse_review_finding` and `pulse_annotate_session` record manual decisions; without write access use the documented journal CLI or app UI. Never invent accepted/failed task labels merely to populate charts. Recheck equal windows and use `pulse_compare`; disclose differences in task difficulty, models, missing events and outcomes. Results are observational, not causal savings claims.

Return decisive evidence, the proposed or implemented improvement, verification, and the next meaningful observation. Keep personal counters/reports local; any public example must be synthetic.

Начинайте с здоровья сбора. Паттерн — гипотеза; отсутствие событий не доказывает отсутствие навыка. Решения и принятые результаты должны соответствовать реально проверенной работе.


For 0.11.2+, inspect `pulse_collection_health` and `pulse_check_receipts` when coverage/storage affects the decision. Analysis includes the whole retained window up to100,000 events; retention loss and UI preview truncation are separate. Counters are unknown before their tracking-start date. Helper provider/status is reporter-declared: keep it separate from native tool outcomes, native skill invocation and human acceptance. A100% helper result rate covers only recorded helper runs.

When the owner has authorized helper instrumentation, run a genuine source check with `--pulse-state <private Pulse state> --pulse-provider <actual client>` and inspect `receiptSaved`. Do not manufacture a receipt from command completion, guessed output or a test fixture. For other helpers, explicitly controlled `pulse_record_check` may import an actual bounded receipt; it does not independently verify the producer. Verified journal backup is local/exclusive and excludes credentials/native databases; do not perform restoration automatically.

Use `pulse_compare_tasks` for actual reviewed task selections. Operational metrics have separate completeness gates: unavailable tokens do not block available observed-call/time metrics, but unknown review/cohort or decreased quality still blocks the comparison. Summed task intervals include waiting and can overlap; never call them active model time. See `docs/COLLECTION_HEALTH.md` in the product source for limits.
