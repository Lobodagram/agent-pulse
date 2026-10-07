Agent Pulse 0.9.7 — concurrent startup and OS-aware setup / одновременный запуск и установка по ОС

Agent Pulse analyzes sanitized coding-agent activity to identify repeated workflows and candidates for skills, scripts or MCP tools. Quotas and daily tokens are supporting views; no model calls, raw prompts/results or telemetry uploads.

This correction removes a Windows mandatory-byte-lock race found by fresh CI on 0.9.6, and a separately reproduced simultaneous SQLite WAL initialization race. Empty/legacy lock files remain compatible. Windows journal acquisition uses bounded polling; native hooks retain their two-second timeout. Three new regression cases and the packaged four-concurrent-hook-pair gate protect the actual failure paths. See docs/QA.md for completed source/package/installed checks and remaining limits.

The EN/RU agent setup guide identifies OS/version/architecture before choosing dependencies: bundled Mac ARM64/Intel and Windows x64 packages need no system Python; Linux supports source collector/MCP only. Two portable skills cover setup and evidence review; local stdio MCP is read-only by default with explicit opt-in bounded control. Users supply their own keys locally. UI, analytics algorithms and reviewed synthetic screenshots are unchanged.

Исправлены гонки одновременного первого запуска на Windows и подготовки SQLite. Добавлены проверки неизменности lock-файлов и блокировки подготовки базы; готовый обработчик проверяет четыре параллельные пары событий. Инструкция установки учитывает ОС и архитектуру, различает готовые пакеты, исходники и сборочные зависимости. Два переносимых навыка и локальный MCP помогают агенту настроить систему и анализировать свидетельства без раскрытия ключей.

Public preview / предварительная версия. Actual Mac Codex/GLM use establishes collection and diagnostic value, not all-client completeness or proven subscription savings. Physical Windows DPI/tray/sleep-wake, Mac Spaces/multi-display, true cold first-start and signing/notarization remain open. AGPL-3.0-only; prior MIT grants remain valid. Check download SHA256SUMS; checksums are not code signing.
