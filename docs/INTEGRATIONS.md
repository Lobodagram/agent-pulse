# In-client integration / Интеграция внутри клиентов

Reviewed 2026-10-07 against official documentation. Feasibility, not an installed plugin or marketplace approval. Agent Pulse already provides optional local read-only MCP tools and opt-in event observers; the desktop widget remains the universal visible surface.

| Surface | Verified extension point | Practical next step |
| --- | --- | --- |
| Codex / ChatGPT plugins | Package skills, MCP and hooks; ChatGPT MCP Apps UI has supported conversation views | Package local analytics tools. A permanent badge injected into every Codex Desktop chat is **not established** by these contracts |
| Codex CLI | `tui.status_line` item list | Native footer settings; these do not establish arbitrary plugin UI in desktop chats |
| Claude Code terminal | Local status-line command receiving session JSON and reported rate-limit fields | Optional bounded formatter, preserving the existing status-line configuration |
| Claude Desktop | MCP tool integration | No verified global-chat badge contract in the researched docs |
| ZCode | Plugins with skills, commands, subagents, MCP and hooks | Analytics commands/MCP package; no verified permanent-chat badge API in the researched plugin contract |
| Kimi Code 2.x CLI | TOML hooks, skills, local MCP | Opt-in observer implemented; native account acceptance remains separate. Kimi Work/Chat and legacy Python kimi-cli are not automatically covered |

Reuse the local journal/collector, without a second agent loop or telemetry uploads. Installing tools differs from inserting persistent UI into a host. UI support depends on the host/version; public-directory distribution needs its normal publishing process. Do not promise automatic approval. No native client settings changed for this review.

По документации можно упаковать инструменты аналитики, команды, скиллы и MCP в плагины. В терминальном Claude Code есть постоянная настраиваемая строка статуса; Codex CLI имеет собственные настройки футера. Возможность встроить произвольный постоянно видимый индикатор **в каждый десктопный чат Codex, Claude или ZCode** этими документами не подтверждена. MCP-инструмент или карточка внутри беседы не равны глобальному индикатору. Виджет остаётся общей поверхностью, а плагины можно делать отдельными адаптерами доступа к локальной аналитике. Этот релиз их не устанавливает и настройки клиентов не меняет.

Official sources / Официальные источники:

- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [ChatGPT MCP Apps UI](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Codex CLI configuration](https://developers.openai.com/codex/config-reference/)
- [Claude Code status line](https://code.claude.com/docs/en/statusline)
- [ZCode plugin contract](https://zcode.z.ai/en/docs/plugin)
- [Kimi Code hooks](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html)

Next adapter proposal: [English](CLIENT_ADAPTERS.md) / [Русский](CLIENT_ADAPTERS.ru.md). Reviewed native model-switch and OAuth quota candidates; no new plugin installed.
