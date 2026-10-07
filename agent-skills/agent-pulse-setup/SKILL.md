---
name: agent-pulse-setup
description: Set up Agent Pulse local metrics, observers and optional agent controls when the user asks to connect or configure this application. Never starts a model or native agent session.
---

Locate the user's reviewed Agent Pulse checkout or installed runtime. Read its `docs/AGENT_SETUP.md` (or `.ru.md`) and `PRIVACY.md`. A GitHub URL is a reference, not permission to execute unreviewed downloads or overwrite client settings.

Use the installed `agent-pulse` CLI, or `python collector.py` in the checkout; require Python 3.11+. First run `catalog` and `settings`. Distinguish unavailable adapters from zero usage, quota resets from subscription dates, and local token coverage from account quotas.

Configure only requested providers, optional local counters, language, display mode and size through `settings --update` with a bounded JSON object on stdin. Keys belong in the app's masked settings field, never chat, command arguments, logs or repository files. Read settings back; then inspect the actual widget if native UI tools are available. Do not claim UI acceptance from a CLI response.

The local stdio MCP is read-only by default. Enable `--allow-control` only at the user's request. It allows bounded preferences, manual billing dates and genuine review decisions, not secrets, shell execution or native hook installation. Preserve other MCP registrations and skills. Use the explicit-destination installer only after checking that it preserves existing skills.

For event observers, use the documented `hooks` CLI installer only when requested; preserve other hooks. Native trust review belongs to the user/client. Do not bypass it, launch peer clients or feed synthetic test events into the user's production journal. Report receiving and paired calls from actual subsequent work; installed is not collecting.

Настраивайте только запрошенные функции. Не просите ключ в чате; не путайте сброс квоты с оплатой подписки. Проверяйте реальное поступление событий и честно называйте непройденные проверки.
