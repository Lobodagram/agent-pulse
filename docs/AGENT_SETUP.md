# Agent setup and control

From 0.9.5, temporary preference contention returns a tool execution result with `isError: true` and fixed text JSON `{"error":"config_busy","retryable":true}`. Retry after the other operation completes; there is no automatic agent retry loop. Disabled controls and invalid arguments remain protocol errors. No path, input or exception message is included. Mac already calls `loadPreferences()` every five seconds; visual preferences need no restart or manual refresh.

Give your agent this repository URL and ask: “Read docs/AGENT_SETUP.md, inspect my existing Agent Pulse installation, configure the requested providers without exposing keys, and explain collection coverage.” This guide is for the local runtime, not a permanently embedded chat UI. The agent's own subscription may be used when you ask it to analyze; Agent Pulse itself makes no model calls.

## Identify the OS and installation route first

Check the OS, OS version and processor architecture using native system information. Choose a **release package** or **source installation**. Do not install build dependencies to run a packaged app, or upgrade system Python/OS/native clients without need and owner authorization. Stop and explain unsupported environments.

| Environment | Release package | User dependencies and limits |
| --- | --- | --- |
| macOS 14+, Apple Silicon ARM64 | `agent-pulse-macos-arm64.zip` | Python/runtime are inside the `.app`; no external Python, Xcode or PyInstaller needed. Choose a stable location, such as `/Applications`, before installing observers. |
| macOS 14+, Intel x64 | `agent-pulse-macos-x64.zip` | Same rules; match the architecture. Signing is ad-hoc, without Apple notarization; do not bypass Gatekeeper automatically. |
| Windows 10/11 x64 | `agent-pulse-windows-x64.zip` | Python/Tk/runtime are bundled. Extract the **whole** folder to a stable location: keep `AgentPulse.exe`, `pulse-collector.exe` and `pulse-runtime` together. No system Python needed for the app. |
| Linux | No packaged desktop GUI | Source collector/local MCP only: Python 3.11+ in a dedicated venv; [headless instructions](HEADLESS.md). Provider adapters vary by client. |
| Windows ARM64 or other platforms/architectures | No separately verified package | Do not promise native support or tested emulation. Establish compatibility first rather than choosing a mismatched download. |

Download the matching architecture from [releases](https://github.com/Lobodagram/agent-pulse/releases/latest), verify SHA256 against `SHA256SUMS.txt`, and read that version's limits. Checksums verify agreement with the manifest, not code signing. Do not reuse Mac shell commands in PowerShell.

Packaged MCP needs no external Python: on Mac, command is the absolute path to `Agent Pulse.app/Contents/Resources/pulse-collector`; on Windows, the extracted `pulse-collector.exe`; arguments are `["mcp"]`. Set the path as a distinct command field in the native client configuration, preserving spaces. Do not use GUI `AgentPulse.exe` for stdio. Additional controls require the owner's separate request.

For **source** installs on Mac/Linux: `python3 -m venv .venv`, then `.venv/bin/python -m pip install .`. On Windows: `py -3.12 -m venv .venv` (or a verified Python 3.11+), then `.venv\Scripts\python.exe -m pip install .`. For the Windows source widget, check Tk (`python -c "import tkinter"`) in the selected environment. The runtime collector uses the standard library. **Building the app** separately requires Xcode Command Line Tools on Mac and pinned PyInstaller in a build-venv; see [platform-specific build commands](BUILDING.md).

The portable skill installer below requires Python 3.11+ and reviewed source; it is an optional separate step. An app/MCP-only user does not need Python just for skills: an agent can read `agent-skills/*/SKILL.md` directly from reviewed source.

Core analytics checks are shared across platforms; the macOS menu and Windows tray differ. Green CI does not replace physical Windows DPI/tray/sleep-wake acceptance; installation does not prove event collection. Report installed version/path/OS/architecture, selected clients, actual MCP tools and subsequent real events, plus unverified functions. Users enter their own credentials locally; never copy another person's configuration or keys.

## Install reviewed skills

Clone or download a reviewed release source. In that checkout, install the two skills to an explicit directory using Python 3.11+:

```sh
python scripts/install_agent_skills.py --destination ~/.agents/skills
```

Codex discovers user skills there. For ZCode use `~/.zcode/skills`; for another client choose its documented skill directory or read the SKILL.md files manually. The installer refuses existing names and symlink destinations; it does not modify MCP/client configs or launch an agent. Skills are selected for relevant tasks rather than all loaded on every task. Restart/reload skill discovery using the client's normal workflow.

## Local runtime and MCP

In a dedicated venv, `python -m pip install .` provides `agent-pulse` and `agent-pulse-mcp`. Alternatively use `python collector.py` from the reviewed checkout, or the packaged `pulse-collector` helper (inside the Mac app's Contents/Resources; next to Windows AgentPulse.exe). Use absolute executable paths in client configs. No hosted Agent Pulse service or corporate server is required.

```sh
agent-pulse catalog
agent-pulse settings
agent-pulse journal --format markdown --language en
agent-pulse-mcp
```

Read-only MCP tools: `pulse_report`, `pulse_session`, `pulse_evidence`, `pulse_compare`, `pulse_review_pack`, `pulse_settings`. To add it to Codex CLI with an installed executable on PATH:

```sh
codex mcp add agent-pulse -- agent-pulse-mcp
```

For ZCode add a STDIO server in its MCP settings panel. Set command to your absolute `agent-pulse-mcp` executable and args to `[]`. Its native config uses `mcp.servers`; `.agents/mcp.json` with `mcpServers` is a fallback and is skipped when native servers exist in that scope. Preserve existing registrations. Claude, Kimi or another MCP client can connect to the same local STDIO command through their current native configuration; verify their tool list rather than assume installation means connection.

## Optional bounded control

Only if requested, start `agent-pulse-mcp --allow-control` (packaged helper: `pulse-collector mcp --allow-control`). Four extra tools allow local settings, manual subscription dates, finding review and session annotation. They do not accept secrets, file destinations, shell commands, native hook edits or model calls.

`pulse_configure` takes `changes`: allowed fields are enabledProviders, localPatterns, localTokens, language (en/ru), widgetScale (0.8–1), displayMode (floating/menu/compact/tray), metricMode (limits/today), topmost, menuNumbers and menuFollowActive. Mac maps compact/tray to menu mode; Windows maps menu to tray. Floating is common. macOS menu flags are platform-specific. Visual changes are polled within about five seconds; provider snapshots refresh on their normal schedule or manually. The equivalent CLI reads bounded JSON from stdin:

```sh
printf '%s' '{"enabledProviders":["codex","glm"],"metricMode":"limits","widgetScale":0.8}' | agent-pulse settings --update
agent-pulse settings
```

Set billing dates only when supplied by the user; quota reset dates are unrelated. Enter personal GLM/Kimi keys through the documented local settings/Secrets.json workflow, never chat or command arguments. `pulse_settings` excludes unknown config fields and credentials. Errors are fixed categories, not remote payloads.

## Observe and review

Native observers are a separate explicit opt-in: `agent-pulse hooks --provider codex --action install` (also glm/claude). The inverse is `--action remove`; existing unrelated hooks are preserved. Review any native trust prompt normally. This is not available through MCP control and never starts a native agent session.

Check real subsequent calls and pairing/gaps in the dashboard or review pack. Zero findings can mean thresholds were not met; unavailable counters are not zero. Do not inject test receipts into production. Use isolated `--state` directories for tests. For finding decisions, actual implemented changes and genuinely reviewed task outcomes are required. Follow [Improvement loop](IMPROVEMENT_LOOP.md). Settings/UI can also be used manually without skills or MCP.

Contracts checked 2026-10-07: [Codex skills](https://developers.openai.com/codex/skills), [Codex MCP](https://developers.openai.com/codex/mcp), [ZCode skills](https://zcode.z.ai/en/docs/skill), [ZCode MCP](https://zcode.z.ai/en/docs/mcp-services). Third-party discovery can change; this release does not certify every client/version combination.

## Concurrent preferences

All built-in UI, CLI and MCP preference writes use a locked, atomic patch and increment `configRevision`, returned by `pulse_settings` and successful configure calls. Unrelated fields are preserved. Changes to the same field use the last completed patch; there is no conflict prompt or compare-and-swap guarantee. An open client-selection form is a draft: Apply intentionally replaces that entire selection group. A busy write fails after one second without changing the config; retry after the other operation finishes. Do not write config.json directly while the app runs.

Mac and Windows poll visual preferences about every five seconds; snapshots/provider selection refresh separately. This is not immediate synchronization of every open form. Reading `pulse_settings` does not create a missing state directory/database, initialize a schema or run migrations.

`pulse_settings.config` reports configured fields, not every effective UI default. Legacy Mac visual preferences can remain in native UserDefaults when absent from config. Do not infer their current values from absence; explicitly configure a requested field or inspect the owner’s app UI.
