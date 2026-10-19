# Agent Pulse 0.14.7 — hook rejection counters / счётчики отклонений хуков

This patch fixes a diagnostic blind spot: oversized inputs, malformed JSON/encoding and input-read failures now increment the existing provider rejection counter when the local journal is available. Source, compatibility and packaged hook entrypoints use the same bounded receiver.

- Rejection-only clients are visible in report coverage without invented activity.
- No payloads, messages, commands or exception text are retained. The 1 MiB input limit stays unchanged.
- Hooks remain silent and fail open. Native tool outcomes and old observations are not rewritten.
- Storage initialization, counter-write or process failures can still prevent counting; zero rejections is not proof of complete collection.
- Isolated regression tests cover rejection counts, bounded reads, privacy, storage failures and valid events after rejection. Packaged smoke checks enforce the existing 2-second callback budget.

This does not establish the cause of historical missing finishes or any token/subscription saving. UI is unchanged; existing public DEMO screenshots remain representative. Source/package verification and platform limits are recorded in [QA](QA.md).

## По-русски

Исправлено слепое место диагностики: слишком большие входы, некорректный JSON/кодировка и ошибки чтения теперь увеличивают существующий счётчик отклонений клиента, если журнал доступен. Исходный, совместимый и упакованный запуск используют один ограниченный обработчик.

Содержимое входов и ошибок не сохраняется. Лимит1МиБ, бесшумный режим, продолжение работы клиента при сбое и правила штатных исходов сохранены. Ошибки хранилища или процесса всё ещё могут мешать учёту; ноль отклонений не доказывает полноту сбора. Старые пропуски не восстанавливаются, их причина и экономия подписки этим исправлением не устанавливаются. Интерфейс не менялся.
