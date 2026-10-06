Agent Pulse v0.6.0 — Model evidence / История моделей

Sessions now shows native per-call model identifiers and their source, plus bounded segments and observed changes. Unknown/conflicting values, unfinished calls and parallel actor lanes remain explicit. Findings and before/after comparisons include models and missing-model counts. CLI/MCP exposes the same local evidence. Current UI selection is never applied to historical tools.

Important limitation: observed ZCode tool hooks currently omit model identity; their model remains unknown, even with an active subscription. This release adds the model evidence contract and timeline, not an invented reconstruction of GLM-5.3 → Flash. See docs/MODELS.md and docs/MODELS.ru.md.

В «Сессиях» добавлены модели вызовов, источники и участки истории с наблюдаемыми изменениями. Пропуски, противоречия, незавершённые и параллельные вызовы сохраняются явно. Данные входят в сценарии, сравнение и локальный CLI/MCP. Текущий выбор модели не подставляется в историю. Наблюдаемые хуки инструментов ZCode пока не сообщают модель: для таких шагов она остаётся неизвестной.

130 unit tests; model examples and screenshots use invented fixture data. Inherits 0.5.2 strict outcomes, collection gaps, capability evidence, focus/restore fix and continuous account history. No model calls, telemetry uploads, credential scraping or automated optimization. MIT source; macOS 14+ ARM64/Intel ad-hoc signed, Windows 10/11 x64 unsigned preview. Complete native coverage and physical Windows DPI/Intel graph acceptance remain open.
