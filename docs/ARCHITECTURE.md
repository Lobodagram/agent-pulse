# Architecture / Архитектура

Agent Pulse is a local, deterministic observer. It does not run agents or models. The desktop UI and local MCP share one Python core; they do not own separate analytics implementations.

Agent Pulse — локальный наблюдатель. Он не запускает агентов и модели. Виджет и MCP используют одно ядро анализа, а не разные реализации.

| Responsibility / Ответственность | Canonical source / Основной код |
| --- | --- |
| Provider counters and quota projection / Счётчики и квоты | `collector.py`, `providers.py`, `glm_quota.py` |
| Own opt-in keys and shared secret-write lock / Личные ключи и блокировка записи | `provider_secrets.py`; local `Secrets.json` only |
| Native hook installation/removal / Подключение и удаление наблюдателей | `instrumentation.py`; preserves other handlers |
| Silent event receiver / Приём событий | `hook_bridge.py` or packaged `pulse-collector hook` |
| Sanitized journal, pairing and deduplication / Журнал, пары и исключение повторной доставки | `journal.py`, `sanitizers.py`, `result_metadata.py` |
| Deterministic patterns, evidence, sessions and reviews / Паттерны, свидетельства, сессии и решения | `analytics.py`, `command_profile.py`, `session_view.py`, `finding_review.py` |
| Model/capability attribution / Модели и подтверждённые навыки | `model_evidence.py`, `capability_detection.py`, `capability_report.py` |
| Read-only MCP and optional bounded controls / MCP и ограниченное управление по выбору | `mcp_server.py`, `agent_control.py` |
| macOS UI / Интерфейс macOS | `Sources/AgentPulse.swift` |
| Windows UI / Интерфейс Windows | `windows/agent_pulse.py` |
| Portable setup/review skills / Навыки установки и анализа | `agent-skills/`; explicit never-overwrite installer |
| Version / Версия | `pulse_version.py`; packaging reads this value |
| Public boundary / Граница публикации | `scripts/public_export.py`; explicit files/directories and reviewed image hashes |

Flow / Поток: native counters or opt-in hooks → bounded in-memory projection → own local counters/journal → deterministic analysis → UI / CLI / local MCP. Prompts, reasoning, raw tool inputs/results and credentials do not enter the journal or exports. See [privacy](../PRIVACY.md).

Поток: штатные счётчики или явно подключённые события → ограниченная обработка в памяти → локальный журнал → анализ → интерфейс/CLI/MCP. Тексты запросов, ответы инструментов и ключи не сохраняются в аналитике и не публикуются.

`metrics.sqlite` stores reported counters/history; `journal.sqlite` stores sanitized observations. `config.json` contains preferences; `Secrets.json` contains own keys/HMAC. These runtime files belong in the user's OS-specific data directory, never the public source tree. Config patches share one cross-process lock; journal initialization and own key updates share another. Each native client keeps its authentication, permissions, tools and billing.

No folder listing can prove the absence of all future debt. Release gates cover source tests, document links, allowlisted publication, reviewed synthetic screenshots, packaged runtime and actual platform acceptance. CI and real-device checks have separate scopes. [QA](QA.md), [current limitations](AUDIT.md), [OS-aware setup](AGENT_SETUP.md).
