# Reference contracts · reviewed 2026-10-06

Independent implementation, no reference project code copied or framework deployed.

- [OpenAI Codex hooks](https://learn.chatgpt.com/docs/hooks): lifecycle/tool events, native trust, fail-open observational hooks. Installed Codex contract also checked; hosted/internal events do not imply complete coverage.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server): read-only account limits/usage and native metadata. A separate process is not a global live-event observer.
- [ZCode hooks](https://zcode.z.ai/en/docs/hooks) and [usage stats](https://zcode.z.ai/en/docs/usage-stats): process hook input/event names and local aggregates. Installed native adapter inspected to verify normalized hook fields.
- [Claude hooks](https://code.claude.com/docs/en/hooks) and [monitoring](https://code.claude.com/docs/en/monitoring-usage): tool IDs, observations/usage separation. Live Claude account acceptance remains pending.
- [Langfuse](https://github.com/langfuse/langfuse): reference for traces, observations and evidence; not adopted.
- [Phoenix](https://github.com/Arize-ai/phoenix): reference for trace/evaluation separation; not adopted.
- [PM4Py](https://github.com/process-intelligence-solutions/pm4py): reference for workflow sequences and process-discovery limits; no code copied or dependency added.

Эталонные проекты использованы для выбора принципов: трасса, доказательства, оценка качества и осторожное выявление сценариев. Код/скиллы/шаблоны из них не копировались. Нативные контракты — источники совместимости, а не обещание полного охвата.
