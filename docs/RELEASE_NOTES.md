Agent Pulse 0.9.2 — daily token details and ordinary utility windows / дневные токены и поведение окон

The daily plot uses ordinary SwiftUI bars and no Swift Charts link. The previous0.9.1 package gate failed on Intel with a confirmed Metal loader assertion and remains source-only; its tag is unchanged. The same Intel chart checks must pass before packaging0.9.2.

Analytics/Settings are ordinary reusable windows: restore from background/hidden/minimized state, hide on repeat while active. The widget retains its configurable floating level. Mac shortcuts: Cmd+1 / Cmd+comma. Windows preserves settings drafts and refreshes reused analytics.

Mac Tokens view: readable K/M/B or тыс./млн/млрд axes; hover previews exact per-client UTC-day counters, clicking pins the day, and an accessible date selector offers the same details. Windows adds Daily tokens with day selection and exact per-client counters. No hourly counts are invented from daily totals. Synthetic screenshots and EN/RU instructions are updated.

Codex local-token repair separates cumulative tokens from the file byte budget. Recent bounded backlog recovery resets the baseline and records a gap instead of assigning skipped historical usage to today. Counts remain partial/device-local, opt-in and subordinate to available native account totals; unknown is not zero. No raw message bodies, arguments, results, credentials or paths are retained in telemetry. No model calls or peer launch.

Окна аналитики/настроек возвращаются на передний план, повторное действие скрывает активное окно; виджет сохраняет свой режим поверх окон. График показывает понятные единицы и точные дневные значения по клиентам. Исправлен сбор свежих локальных токенов Codex, пропуски и неполный охват обозначены; старый расход не приписывается текущему дню.

AGPL-3.0-only; prior published MIT grants remain valid. Code assessment 8.5/10; analytical effectiveness 7/10 pending genuine accepted comparable tasks. Signing/notarization, true cold first-start and physical Windows DPI/Intel graphics/Spaces/multi-display/sleep-wake remain open. See docs/QA.md for actual source, GUI and package evidence; these are distinct gates.
