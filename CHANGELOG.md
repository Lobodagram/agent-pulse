## 0.3.3 · 2026-10-06

Remove redundant native Tk label padding, preserving readable fonts and fitting both English/Russian two-quota layouts at 80%.

- Keep Windows today tokens and quota resets on separate short rows so Russian two-client content fits at 80%. Test English/Russian source and packaged layouts. Windows supports `--language en|ru`.

## 0.3.2 · 2026-10-06

- Fix clipped Windows fields at 80% when both visible clients report quotas. Add a UTF-8 two-quota-client layout regression to hosted Windows checks.

## 0.3.1 · 2026-10-06

- Windows native tray: hover counters, click expand/collapse, context menu, Explorer recovery and visible fallback.

- Explicit quit button and production single-instance protection on Mac/Windows; fixture cleanup also runs on failure.
- Proportional widget sizing, 80/90/100% presets, continuous slider and lower-right resize grip; auxiliary windows retain their original size.
- Mac menu-bar-only mode, first-two-client compact indicators, icon-only option and click popover.
- Explain delayed Codex daily reporting; independent opt-in bounded local token projection supplies partial UTC-day counts without tool projection or double-counted account totals.
- Native fixture matrix and token-only privacy/dedup/pending tests.

# Changelog

## 0.4.0 · 2026-10-06

- MIT for the current original-source snapshot; copyright notice preserved. Earlier tags unchanged.
- Mac collapsed bar rotates one selected client every 8 seconds, both reported quota windows; optional foreground desktop selection with rotation fallback. No token-to-quota inference.
- Click opens the movable/resizable full widget; collapse keeps compact bar data.
- Windows small strip above taskbar, all-client pages, restore controls and native tray option.
- Integration feasibility documented; persistent injection into every desktop chat is not claimed.
 / Изменения

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
