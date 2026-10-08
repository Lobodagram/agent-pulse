Agent Pulse 0.10.3 — startup, window controls and workflow evidence / автозапуск, окна и анализ повторов

This release includes the previously local 0.10.2 improvements and the 0.10.3 macOS controls.

- Optional **Launch at login** checkbox: macOS SMAppService and Windows current-user startup entry. Uncheck to disable. Opening Agent Pulse does not enable startup automatically; demo mode cannot change it.
- On macOS **× hides the widget** while observation continues. Click Pulse in the menu bar to restore; right-click/two-finger click → **Quit Agent Pulse**, or Command-Q. Settings now has visible fixed close/minimize controls and supports reopening.
- Exact repeated calls receive priority, bookkeeping calls break sequences, and examples span distinct sessions. Fixed 3D QA/release/CI families improve classification; historical unknown shell payloads remain unknown. Reports expose classification coverage.
- Updated English/Russian setup guidance and eight reviewed synthetic screenshots. No personal activity, account screenshots, credentials or private Git history are included.

Добавлена галочка автозапуска с обратимым отключением. На Mac крестик скрывает виджет, а полный выход доступен через меню Pulse; в настройках появились отдельные кнопки закрытия и сворачивания. Анализ чаще показывает конкретные повторы, исключает служебные вызовы из рекомендаций и явно отражает неполноту данных.

Local checks passed:230 tests, privacy export/syntax/document links, Swift build,23 widget scenarios and actual button clicks in an isolated fixture. Native macOS startup enable/disable and app-relaunch persistence were checked, then restored off. Platform CI and downloaded package verification are recorded in [QA](https://github.com/Lobodagram/agent-pulse/blob/main/docs/QA.md) when completed; an earlier release's results do not certify these bytes.

Public preview / предварительная версия. Actual computer reboot, physical Windows DPI/tray/sleep-wake, Mac Spaces/multi-display, live Kimi account acceptance and signing/notarization remain separate. Improved classification is not measured productivity or subscription savings. AGPL-3.0-only; earlier MIT grants remain valid. Verify SHA256SUMS; checksums are not signing.

[English agent setup](https://github.com/Lobodagram/agent-pulse/blob/v0.10.3/docs/AGENT_SETUP.md) · [Установка агентом по ОС](https://github.com/Lobodagram/agent-pulse/blob/v0.10.3/docs/AGENT_SETUP.ru.md)
