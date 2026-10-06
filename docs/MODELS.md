# Model evidence in 0.6.0

[Русский](MODELS.ru.md)

Sessions shows the model of each observed call, its source, and bounded segments of calls with the same reported model. Workflow evidence and before/after comparison also list known models and missing model counts. This supports investigating a large-model → Flash change without silently mixing their evidence.

Only the native event's top-level `model` identifier is accepted. Response text, tool input, global configuration and the model currently selected in a window are never interpreted as historical call identity. A model supplied only at completion is labeled `call-finish-only`; disagreeing start/completion or conflicting repeated events become unknown. Unknown values do not inherit an earlier model, including a SessionStart model.

Segments follow separate provider/session/actor lanes. Missing models, invalid times, unfinished or overlapping calls break the transition interpretation. Different simultaneous models are parallel observations, not a switch. A `reported-change` means two sequential observed calls report different models; the first new call's time and the preceding observation bound the observation interval. They do not establish the exact UI switching time or uninterrupted model use between calls. At most the latest 100 segments and ten evidence IDs per segment are returned. MCP report/session caps are smaller, with truncation labels.

Subscription quotas, tool frequency and per-model call counts are distinct measurements. Reported model identifiers alone cannot establish equal task difficulty, reasoning effort, tokens per tool or a causal saving. Unknown models and outcomes stay part of the comparison.

## Native support limitation

[ZCode hooks](https://zcode.z.ai/en/docs/hooks) documents optional `model` on SessionStart but does not guarantee it on tool events or mid-session switches. The observed tool events on the development device currently omit it. Those calls therefore remain unknown; this release provides the evidence contract and timeline, not automatic identification where the host omits data. [ZCode usage/stats](https://zcode.z.ai/en/docs/usage-stats) is an aggregate source and cannot assign its model totals to particular past tools.

For any provider, first verify real per-call identifiers before relying on model comparisons. Future adapters must use supported native metadata with explicit scope/timestamps and no transcript, cookie or credential scraping. The local read-only MCP `pulse_session` and CLI `journal --action session --session HASH` include the same bounded model history.
