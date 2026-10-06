# Privacy / Приватность

0.5.0 adds bounded sanitized operation families/operators, result-source labels and reviewed capability IDs with loaded/invoked/declared counts. Skill-file locators are keyed hashes; literal paths and instructions never persist. Evidence packs remain private local exports, never automatically uploaded.

В 0.5.0 добавлены очищенные семейства операций, источники результатов и проверенные ID навыков. Пути файлов — HMAC; инструкции не сохраняются. Пакеты доказательств остаются локальными, без автоматической отправки.

Agent Pulse does not invoke models, submit prompts, upload metrics, read browser cookies, capture screens/microphones, modify native client settings or directly read native SQLite databases. It is not employee-monitoring software.

Stored locally: daily numeric token counters (180 days), provider counter samples (90 days), optional sanitized tool category counts (30 days), bounded-event hashed cursor IDs, cumulative numeric baselines and manual billing dates. Hashes/cursors are local and are not uploaded. Deleting the own state directory after quitting resets this history; deleting the app alone does not remove state. Linux/Windows/macOS paths are in README. The OS user must protect this directory; POSIX modes are 700/600, while Windows uses inherited NTFS permissions and should be installed in a private user profile, not a shared/public folder.

Optional Codex projection, off by default: metadata for up to 30 recent threads, only native-returned `.jsonl` paths inside `~/.codex/sessions`, last seven days, initial tail up to 2 MiB per file and bounded incremental reads. JSON is transiently parsed; only token-event numbers, sanitized tool identifiers and fixed command classes persist. Message/argument/result/code fields are not stored. Static indicators in command wrappers do not establish that every nested command executed. Event coverage is partial; a reset baseline adds no negative count. This is not full-session token accounting.

Claude bridge receives native status-line JSON through stdin. It discards session names, IDs, transcript paths, working directories and cost details; only allowlisted counters/quotas/context size go to its own import. Context gauge is not token spend. Normalized imports use the same projection; never import entire transcripts or provider credential dumps. Old/missing timestamps are stale. Secrets, if configured for the optional Kimi adapter, belong only in local `Secrets.json`, not metrics/config/repository. POSIX file permission 600 is required; Windows must restrict access using its user-profile ACL.

Network: Codex/ZCode native processes can use their own authentication and vendor services to answer usage requests. Agent Pulse does not guarantee they are offline or change their telemetry settings, apart from passing the documented Codex analytics override to its own metadata process. Optional Kimi sends a GET with its configured key to `https://api.kimi.com/coding/v1/usages`; redirects and environment proxies are disabled. Qwen accepts only explicitly configured HTTP loopback `127.0.0.1` or `::1` with no URL credentials; it never starts a daemon. Other import adapters are local. No corporate MCPs, remote dynamic plugins or arbitrary callback URLs are used.

Приложение не вызывает модели, не отправляет промпты/телеметрию, не читает cookies, не снимает экран/микрофон, не меняет настройки клиентов и не читает их SQLite напрямую. Это не система наблюдения за сотрудниками.

Локально сохраняются числовые счётчики по дням (180 дней), снимки счётчиков (90), опциональные категории инструментов (30), хешированные курсоры, числовые базы отсчёта и ручные даты. Они не выгружаются. После выхода удаление собственной папки данных сбрасывает историю. На POSIX используются режимы 700/600; на Windows — права NTFS профиля пользователя, поэтому общая папка не подходит.

Опциональное чтение событий Codex выключено по умолчанию: максимум 30 недавних чатов, пути штатных событий внутри `~/.codex/sessions`, последние семь дней, ограниченный хвост и последующие чтения. JSON временно разбирается, но тексты, аргументы, результаты и код не сохраняются. Статические категории не доказывают исполнение всех команд. Охват частичный.

Мост Claude отбрасывает названия/ID сессий, пути переписки и рабочие каталоги. Размер контекста не считается расходом. Импортируйте только счётчики, не переписку или секреты. Старые/недатированные данные помечаются устаревшими. Ключ Kimi хранится только в локальном `Secrets.json`, не в git и не в телеметрии.

Штатные Codex/ZCode могут обращаться к своим сервисам и имеют собственную авторизацию/телеметрию. Опциональный Kimi делает GET только в официальный API; переадресации и прокси окружения отключены. Qwen читает явно настроенный loopback и не запускает сервер. Корпоративные MCP и удалённые плагины не используются.

## Event journal (0.3.0) / Журнал событий

Opt-in native hooks transiently receive payloads and retain only allowlisted metadata, fixed command shapes and keyed input/session/project/resource fingerprints in own local SQLite. No payload, prompt, result, code, transcript or literal project path persists. Device key is in local Secrets.json. Metadata/hashes are private activity evidence, not anonymous public data. No exports are uploaded automatically. Reports are bounded; retention and native-coverage gaps are documented in [analytics](docs/ANALYTICS.md). Native hook configuration is changed only by explicit observer enable/remove, preserving other handlers; no trust bypass. Only this observer is removed. The optional local MCP reads bounded evidence and performs own-cache housekeeping; no native tools/model calls are exposed.

Добровольные хуки сохраняют очищенные метаданные, формы команд и локальные HMAC, без текстов/кода/секретов/путей проекта. Ключ в Secrets.json. Это личные сведения о работе; публичная анонимность не обещается. Экспорт не отправляется. Включение/удаление наблюдателя меняет только его обработчики в нативном конфиге. Доверие клиента не обходится. Локальный MCP читает ограниченные сведения и обслуживает свой кеш; не управляет клиентами.


Account switching observes only known auth/config file modification/size/inode attributes for selected clients, never their contents. Native Codex account/read identity is transiently hashed with the journal key; raw IDs/emails are not retained. Quota cache for an unknown/mismatched account is not reused. / Переключение аккаунтов использует только атрибуты известных файлов, без чтения секретов; штатная личность Codex сохраняется лишь как локальный HMAC.


Work history remains continuous across account switches. The journal groups by provider/task, not login. Known Codex daily account reports are stored per hashed account/day, updated (not incremented) on each read, then summed for general daily history. Switching back does not count the same account twice. Earlier unscoped rows remain stored; if they overlap a known-account day, they are not added because identity/overlap cannot be verified. Therefore totals cover observed accounts only, not every account ever used. Current quotas and manual billing dates remain account-specific; GLM local aggregates remain client history.


Optional local Codex daily tokens (0.3.1): off by default and independent of tool-pattern projection. When enabled, the native metadata API returns at most 30 recent session paths; only bounded token-count events under the native sessions root are projected. Raw records may contain conversation text but no message text, prompts, code or arguments are retained in this mode. The result is a partial device-wide UTC-day count, not a complete account bill or per-tool cost. It is never added to an account daily total. Shared general history and current account quotas remain separate.

Model evidence retains only sanitized native top-level identifiers and conflict markers. Missing call models are never inferred from current UI, configuration, response text or session-start selection. Timelines describe observed calls, not exact UI switch times.
