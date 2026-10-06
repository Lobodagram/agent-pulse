# Changelog / Изменения

## 0.3.0 — 2026-10-06

- Opt-in silent native Codex/ZCode/Claude observations, private SQLite journal and hashed evidence.
- Paired outcomes/durations, session timeline, workflow/retry/read discovery, explicit capability inventory and observational before/after review.
- Local bounded read-only MCP with three evidence tools; no model/API usage added.
- Mac and Windows tabbed analytics; preserved native hook configuration and separate Windows console helper.
- Codex limits refresh every minute with quota-source time; counters every five minutes. Independent reads can still briefly differ.
- Privacy/concurrency/provenance regression tests and bilingual setup/limitations.

Новый локальный журнал, сценарии, доказательства, сравнение вариантов и MCP аналитики. Лимиты Codex обновляются раз в минуту с временем получения. Все наблюдатели добровольные; полный охват каждого шага и токены каждого инструмента не обещаются.


## 0.2.2 — 2026-10-06

- Resolve the Windows demo fixture to an absolute path before the frozen executable smoke check.
- Verify macOS ARM64, macOS Intel and packaged Windows x64 before publishing downloadable archives.

Исправлен путь демонстрационных данных при проверке Windows .exe. Все три упакованные версии прошли проверочную сборку до публикации.

## 0.2.1 — 2026-10-06

- Bundle the official Python 3.12 notice when a runner omits it; verify the final macOS signature after adding runtime notices.
- Show Windows token counters and human-readable reset times in the compact panel; explicit packaging search path.
- Keep independent package builds running if another architecture fails.

Исправлена упаковка лицензий Python и финальная подпись macOS. В Windows-виджет добавлены токены и читаемые даты сброса.

## 0.2.0 — 2026-10-06 (public preview / публичная предварительная версия)

- Selectable provider catalog with native, status-line, loopback, quota API and import adapters.
- English/Russian macOS UI, paging, source-aware analytics and manual billing dates.
- Windows Tk widget source, shared portable bounded RPC transport and package workflows.
- Explicit context-versus-spend semantics; local Codex projection disabled by default.
- Public demo screenshots, bilingual guides, privacy/security/contribution policy.
- PolyForm Noncommercial 1.0.0 plus separately negotiated paid commercial licensing.

Выбор клиентов, русско-английский интерфейс, отдельный показ контекста и расхода, предварительный Windows-виджет, сборки, документация и демонстрационные скриншоты. Анализ событий Codex по умолчанию выключен. Коммерческая лицензия приобретается отдельно.
