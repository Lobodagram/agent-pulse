# Provider setup

[Русский](PROVIDERS.ru.md)

Enable only the clients you use in Settings. Modes are visible in the catalog. Disabled adapters are not polled. Import-only selection is not an account connection. Refresh is every 5 minutes and manual; counters have UTC daily boundaries, reset timestamps display in your local time. Billing dates are always manual because no billing-renewal API is assumed.

## Own configuration

Use `collector.py` from a source checkout with Python 3.11+:

```sh
python3 collector.py catalog
python3 collector.py configure --providers codex,glm,claude --local-patterns off
python3 collector.py subscription --provider codex --kind renewal --date 2027-02-01
python3 collector.py snapshot
```

On Windows use `python` instead of `python3`. Every command accepts `--state PATH` **before** its subcommand to use an isolated test directory. `config.json` in the own state directory holds non-secret settings. Never put keys into that file or this repository.

```json
{
  "enabledProviders": ["codex", "glm"],
  "localPatterns": false
}
```

Advanced explicit runtime overrides: `codexCli`, `nodePath`, `zcodeResources`, `zcodeCli`, `zcodeBuiltin`. Paths are used only to run your installed native client; no credentials are extracted. Set only reviewed executables you own/trust. Nothing is downloaded by an adapter.

## Codex

Install/authenticate the native Codex CLI yourself and make `codex` available on PATH, or set `codexCli`. Collector starts a standalone metadata app-server, calls `initialize`, `account/rateLimits/read`, `account/usage/read` where supported, then closes it. No turn/thread start/resume call exists in the allowlist. Different versions/account plans can omit methods or fields. `rateLimitsByLimitId` is preferred; absent values stay unknown. Available reset credits are shown only if reported. Do not infer credits from quota percentages.

Optional local event analysis is off by default. Enable it in Settings or `configure --local-patterns on` only if you accept the bounded local parsing described in PRIVACY.md. `thread/list` then returns up to 30 recent metadata paths. Event counters supplement missing account tokens with a clearly marked partial count; they do not overwrite account history or prove complete coverage. Static tool identifiers from a wrapper can represent code branches that did not execute.

Source contract: [official Codex app-server](https://developers.openai.com/codex/app-server/).

## GLM / ZCode

Uses Node on PATH and the installed ZCode app's CLI to request read-only `usage/stats` for seven days in UTC. macOS default app path is `/Applications/ZCode.app/Contents/Resources`. On Windows the packaging layout may differ: explicitly configure `zcodeResources` or `zcodeCli` + `zcodeBuiltin`, and `nodePath` if necessary. The native resolver receives its installed built-in provider path and its own personal config path; Agent Pulse does not parse its credentials. No native DB is opened directly.

These are **local ZCode records**, not all GLM use on other devices or IDEs. Zero recorded sessions does not establish zero global consumption. Account-login-only remote quotas are not exposed by this CLI; the separate opt-in adapter is described below. Enter billing dates or “No plan” manually.

Source: [ZCode usage statistics](https://zcode.z.ai/en/docs/usage-stats).

## Claude Code: explicit status-line bridge

No automatic settings edit. Keep a backup of your existing Claude status-line configuration. Configure its `statusLine` command to run the reviewed bridge from this checkout (with absolute executable/script paths on your machine):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /absolute/path/to/agent-pulse/scripts/claude_statusline.py"
  }
}
```

Windows: use a suitable Python path and quote paths containing spaces. This replaces the status-line command; integrate it with your current script yourself if you want to preserve existing output. It receives official JSON on stdin and writes only projected numbers to Agent Pulse's own `imports/claude.json`. The snapshot is marked stale after 10 minutes without an event. Restart/refresh Agent Pulse after configuring.

`rate_limits.five_hour` and `seven_day` are optional; plan/gateway support varies and an initial model response may be needed by the native client. Agent Pulse **does not initiate that response**. `context_window.total_input_tokens + total_output_tokens` is displayed only as **context size**, never day/session cumulative spend. Session name, ID, transcript path, cwd and prompt fields are discarded.

Contract: [official Claude status-line JSON](https://code.claude.com/docs/en/statusline).

<a id="kimi-code"></a>

## Kimi Code 2.x: separate quota and event connections

Select the account region explicitly in Settings: .com (mainland-cn) or .ai (global). The same key is never retried against a different regional host. Official Kimi Code 2.1.1 was installed/help-checked here, but the owner cannot log into the friend-owned account; actual account quotas/native events remain unverified.

Enable Kimi in the client selection. Enter your **own Kimi Code key** in the masked Settings field and Save. It stays in local `Secrets.json` (0600 on POSIX; restrict NTFS access on Windows). A Kimi Work/Chat login is not a Kimi Code key. Agent Pulse does not extract native keys, cookies or passwords.

Only GET `https://api.kimi.com/coding/v1/usages` is used. The summary reports the weekly quota; short windows require explicit `duration/timeUnit`, never array order. Invalid/conflicting values remain unknown. A failed/disconnected key cannot resurrect previous cached percentages. Quota units are not daily token spend; a missing counter is not zero. Surrounding pasted whitespace is trimmed; internal whitespace is rejected. [Official client quota contract](https://github.com/MoonshotAI/kimi-cli/blob/main/src/kimi_cli/ui/shell/usage.py).

For analytics separately enable the KIMI observer or run `agent-pulse hooks --provider kimi --action install`. The Kimi Code 2.x TOML contract uses `~/.kimi-code/config.toml`, respecting explicit `KIMI_CODE_HOME`. Start a new native session after configuration. Silent handlers have a two-second deadline; other native bytes/handlers are preserved. Removal deletes only the marked Agent Pulse block. Legacy Python kimi-cli (`~/.kimi`) is not reconfigured automatically. [Official hooks](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html).

Tool events establish paired calls and repetition evidence. Shell outcomes without structured exit metadata remain unknown; output text is never interpreted as success. A session-selected model is not inherited by calls without model evidence. These events do not establish daily token spend.

Kimi Work/Chat, Kimi Code Desktop and terminal Kimi Code are separate surfaces. Login/subscription in one does not establish access to another's events. The development Mac has Kimi Work/Chat; separate Kimi Code and its authenticated account still require live acceptance. Schema fixtures are not that acceptance. Automatic Work/Chat collection is not claimed. See [integrations](INTEGRATIONS.md) for terminal/IDE boundaries.

## Qwen Code: existing loopback dashboard

Experimental, explicit opt-in. If you already run the native Qwen local server, set `qwenBaseUrl` in the own config to its known loopback origin, for example `http://127.0.0.1:PORT` with its real port. Agent Pulse does not guess the port or start Qwen.

Only HTTP loopback `127.0.0.1` or `::1` is accepted, with no credentials/path/query/fragment; redirects are rejected. Collector reads `/usage/dashboard?range=today&heatmapDays=30`. It projects summary tokens, daily/heatmap counters and sanitized skill names; no transcript files are opened. This does not provide paid subscription quotas or billing dates. Keep your native Qwen server private and appropriately protected.

Contracts: [official route](https://github.com/QwenLM/qwen-code/blob/main/packages/cli/src/serve/routes/usage-stats.ts), [official aggregate schema](https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/services/usage-dashboard-service.ts). Fixture verified; live native integration pending.

## Other clients / normalized import

Gemini, Cursor, Copilot, Windsurf, DeepSeek and OpenRouter currently have **import adapters only**. You supply a local counter export; the widget will not scrape their UI, credential stores, cookies or hidden APIs. The same import is also available for other catalog providers. Counters are user-provided, not verified account truth.

```sh
python3 collector.py ingest --provider cursor --file /path/to/counters.json
```

Input fields (all optional except a meaningful timestamp):

```json
{
  "observedAt": 1893492000,
  "todayTokens": 12000,
  "periodTokens": null,
  "contextTokens": null,
  "daily": [{"date": "2027-01-01", "tokens": 12000}],
  "quotas": [{"kind": "primary", "durationMinutes": 300, "remainingPercent": 70, "resetsAt": 1893500000}],
  "tools": [{"name": "run_tests", "count": 4}]
}
```

Replace the demo epoch with the actual observation time in **seconds**, not milliseconds, and only include a field you can support with evidence. Never manufacture a zero for absent data or convert cost/context/quota units to tokens. Unknown fields are discarded. Numeric values must be finite, nonnegative numbers; booleans are rejected. Names are bounded/sanitized. Imports are limited to 2 MiB. Old, future or missing timestamps are stale. Claude imports deliberately drop token-spend/history fields to preserve context semantics. No dynamic plugin code is executed.

## Troubleshooting

- Unavailable: install/authenticate the native client yourself, review the support mode/runtime paths and refresh. No source means no guessed value.
- Stale: last successful values or an old import are retained and marked. A previous day's cached token total must not become today's spend.
- Missing tokens with working quota: normal; not every plan/client exposes token totals.
- Reset is not renewal: automatic quota timestamps and manual billing dates stay separate.
- Patterns: hints for human review, not a recommendation to automatically install a skill/MCP or a measurement of per-tool cost.

Codex daily reporting may omit the current UTC day. `todayTokenStatus=account-day-pending` means waiting, not zero. Settings → Local Codex tokens today is a separate default-off option (`configure --local-tokens on`). Bounded native token events can fill a missing bucket; `todayTokenCoverage=partial-local` explicitly labels device-wide partial records across logins. Account totals take precedence when present; never add local and account figures.

### GLM remaining quotas · opt in

In Agent Pulse Settings, enter your own **personal Z.ai Coding Plan** key in the masked field and Save. Disconnect removes only this provider's key. It is stored with mode 600 in own-state `Secrets.json`, never command-line arguments, Git or telemetry. Windows users should restrict the file's NTFS access to their account. No ZCode credential is extracted; account login alone cannot connect this adapter.

The independent adapter reads only `GET https://api.z.ai/api/monitor/usage/quota/limit`, the endpoint used by the [official usage plugin](https://docs.z.ai/devpack/extension/usage-query-plugin). Redirects and environment proxies are disabled. Five-hour and week rows follow native `TOKENS_LIMIT`/`CREDIT_LIMIT` unit/window fields; percentages are **remaining**, native resets are milliseconds converted to seconds. Monthly MCP `TIME_LIMIT` is excluded. Missing/ambiguous/invalid windows remain unknown; failed reads clear quota values rather than reusing another key's data. The endpoint is experimental, not a guaranteed stable analytics API.

Quotas belong to the **configured key**, while local tokens belong to **ZCode records on this device**; these may cover different accounts. Token/task history continues across account changes. Changing ZCode login does not switch the separately configured key. Manual subscription dates remain separate. Remote quotas refresh with the five-minute snapshot or Refresh; Codex's existing minute refresh remains. Without a key, local ZCode tokens still work and quota values show unavailable. Live five-hour/week quota and reset fields were verified on the development Mac using a user-configured personal key; this is not a guarantee for every account or regional endpoint.

The widget's **Limits ⇄ / Today ⇄** button selects remaining subscription percentages or today's reported tokens (UTC), and retains the choice after restart. Today never substitutes a seven-day total/context gauge. The menu bar/Windows compact mode and tray tooltip always keep quota summaries.


Frozen Mac 0.8.1 adds OS-owned /etc/ssl/cert.pem roots to the verified HTTPS context because the build Python framework CA path may be absent. Certificate/hostname verification remains required; invalid roots fail closed. / Сборка Mac 0.8.1 использует также системные CA; проверка сертификата и имени сервера сохраняется.

GLM read failures report a fixed `quotaError` category: configuration, authentication, TLS, network, remote, schema or unavailable. No exception message, response body or key is retained. Outer paste whitespace is removed; internal whitespace stays invalid. `agent-pulse tls-check` explicitly verifies a fixed public HTTPS quota endpoint without a key. The packaged Windows release gate runs this diagnostic; it uses CPython's Windows CA/ROOT trust, certificate and hostname checks remain required. Physical user-machine trust coverage is separate.

Ошибки GLM различаются безопасными категориями без текста ответа и ключа. Пробелы по краям вставки убираются; внутренние запрещены. Проверка tls-check не передаёт ключ и не вызывает модели. Сборка Windows проверяется отдельно; это не физическая приёмка каждого компьютера.
