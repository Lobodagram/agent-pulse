Agent Pulse 0.9.7 — concurrent startup and OS-aware setup / одновременный запуск и установка по ОС

Agent Pulse analyzes sanitized coding-agent activity to identify repeated workflows and candidates for skills, scripts or MCP tools. Quotas and daily tokens are supporting views; no model calls, raw prompts/results or telemetry uploads.

This correction removes a Windows mandatory-byte-lock race found by fresh CI on 0.9.6, and a separately reproduced simultaneous SQLite WAL initialization race. Empty/legacy lock files remain compatible. Windows journal acquisition uses bounded polling; native hooks retain their two-second timeout. Three new regression cases and the packaged four-concurrent-hook-pair gate protect the actual failure paths. See docs/QA.md for completed source/package/installed checks and remaining limits.

The EN/RU agent setup guide identifies OS/version/architecture before choosing dependencies: bundled Mac ARM64/Intel and Windows x64 packages need no system Python; Linux supports source collector/MCP only. Two portable skills cover setup and evidence review; local stdio MCP is read-only by default with explicit opt-in bounded control. Users supply their own keys locally. UI, analytics algorithms and reviewed synthetic screenshots are unchanged.

Исправлены гонки одновременного первого запуска на Windows и подготовки SQLite. Добавлены проверки неизменности lock-файлов и блокировки подготовки базы; готовый обработчик проверяет четыре параллельные пары событий. Инструкция установки учитывает ОС и архитектуру, различает готовые пакеты, исходники и сборочные зависимости. Два переносимых навыка и локальный MCP помогают агенту настроить систему и анализировать свидетельства без раскрытия ключей.

Public preview / предварительная версия. Actual Mac Codex/GLM use establishes collection and diagnostic value, not all-client completeness or proven subscription savings. Physical Windows DPI/tray/sleep-wake, Mac Spaces/multi-display, true cold first-start and signing/notarization remain open. AGPL-3.0-only; prior MIT grants remain valid. Check download SHA256SUMS; checksums are not code signing.

Delivered checks / Проверки опубликованной версии:

- [Source checks](https://github.com/Lobodagram/agent-pulse/actions/runs/37619930324):210tests, Linux/Windows/Mac ARM64/Intel passed. [Packaged builds](https://github.com/Lobodagram/agent-pulse/actions/runs/37620315697):all three binaries and publication passed, including concurrent first hooks.
- All three downloaded SHA256/runtime/notices checks passed. In-memory comparisons against two own local credential stores found zero raw/base64/hex matches in files and four decoded Python archives. Downloaded ARM64 signature, strict two-second hook/MCP and parallel first pairs,20widget and5chart scenarios passed.
- Downloaded0.9.7/build28 installed on the development Mac with prior0.9.6 retained; keys/0600/settings/observer path preserved. Actual six analytics sections, settings, Limits/Today/back and Quit/relaunch checked. Comparison has no accepted task pairs yet, rather than a zero saving claim. UI and reviewed synthetic screenshots unchanged.
- Все архивы сверены, ключей в проверенном публичном содержимом нет. На Mac проверены живой виджет, разделы аналитики и настройки. Физическая Windows-приёмка и холодный запуск на чистом устройстве остаются открытыми.

[English agent setup](https://github.com/Lobodagram/agent-pulse/blob/v0.9.7/docs/AGENT_SETUP.md) · [Установка агентом по ОС](https://github.com/Lobodagram/agent-pulse/blob/v0.9.7/docs/AGENT_SETUP.ru.md)
