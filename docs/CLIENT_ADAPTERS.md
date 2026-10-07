# Client adapters — reviewed 2026-10-07

[Русский](CLIENT_ADAPTERS.ru.md). Proposal, not installed plugins. See [current integrations](INTEGRATIONS.md) and [model evidence](MODELS.md).

Use one local Agent Pulse journal/collector with small host-specific adapters. The host retains inference, tools, sessions, authentication, permissions and billing. Packaging a hook as a plugin improves installation and removal; it does not grant otherwise unavailable account or model metadata.

| Client | Verified extension candidate | Current Agent Pulse status |
| --- | --- | --- |
| Codex | Plugin lifecycle hooks and local MCP; native account usage RPC | Own observers/read-only MCP exist; no separately published plugin or billing renewal API established. [Official plugin packaging](https://developers.openai.com/plugins/build/plugins) |
| ZCode | Plugin hooks/MCP; native app and Coding Plan aggregate statistics | Local observers and opt-in Z.ai plan quotas are delivered. Per-call model coverage remains partial. [Plugins](https://zcode.z.ai/en/docs/plugin), [hooks](https://zcode.z.ai/en/docs/hooks) |
| Claude Code | `PostModelSwitch` in v2.1.251+ | Future session-model transition adapter. This event does not cover every per-turn fallback, so session-selected and actual call models must stay separate. [Hooks](https://code.claude.com/docs/en/hooks#postmodelswitch) |
| Kimi Code | Authenticated local `GET /api/v1/oauth/usage` | OAuth quota adapter remains a proposal. Own-key quota adapter and Kimi Code 2.x TOML observers are implemented; live acceptance separate. Kimi Work/Chat compatibility not proved. [Server API](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/server-api.html) |

## Proposed implementation gates

1. Discover the user's explicitly selected installed client and supported version, without searching private sessions or extracting credentials. Disabled clients are not polled.
2. Review a concrete adapter manifest: events/GET methods, accepted metadata fields, identity scope, refresh interval, size/time bounds, storage and removal. Preserve existing user handlers; avoid installing both plugin and user hook for the same event.
3. Keep native hook review/authorization. A plugin installation does not bypass host trust. Freeze opt-in configuration for active sessions; do not interrupt a running peer to activate changes.
4. Project only IDs, native model/switch metadata, numeric usage, quota windows and explicit billing dates. Raw prompts, reasoning, arguments, results, cookies and screenshots are excluded. Credentials remain managed by the host; any explicitly supplied own adapter key stays local in Secrets.json.
5. Persist provenance and observation time; hash identity locally. Separate account quotas from continuous work history, session-selected model from per-call model, quota reset from subscription renewal, native date from manual date. Never infer renewal from a monthly reset.
6. Validate real starts/completions, model changes, account changes, errors, removal and duplicate delivery. Inspect documented side effects: a GET that resumes a session is outside a passive collector contract.

Preferred order: complete known-client model event coverage, then Kimi Code local quota integration and ZCode remote plan integration where supported. A dashboard can be inspected by a user, but private endpoint/cookie scraping or unrestricted screen capture is not the adapter design. No broad legal assurance is made: use supported vendor interfaces under applicable access/extension terms; no authorization or paywall bypass. Missing fields retain manual input/unavailable state.

Distribution can begin as reviewed local/GitHub adapter bundles. Public OpenAI directory submission has its own review and local-MCP constraints; do not publish a local telemetry service on the internet merely to meet a marketplace requirement.
