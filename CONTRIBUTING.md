# Contributing / Участие

Bug reports, documentation corrections and synthetic adapter fixtures are welcome. Read PRIVACY.md and the provider contract before changing an adapter. Each provider needs honest provenance, missing/stale behavior, bounded reads and a fixture test. Never use private session dumps. Run the unit suite; UI work needs actual renders using the public demo fixture. Native client settings must remain unchanged unless a user explicitly configures an opt-in bridge.

macOS source boundaries: `Sources/PulseModels.swift` owns Codable contracts and shared presentation helpers; `PulseStore.swift` owns collection/configuration state; `WidgetViews.swift`, `TokenHistory.swift`, `AnalysisView.swift`, `HelperMetricView.swift` and `SettingsView.swift` own their views. `AppDelegate.swift` owns windows, menu bar and lifecycle; `AgentPulse.swift` is the entrypoint. `build.sh` compiles `Sources/*.swift`. Keep state ownership in the store and preserve menu-bar/window behavior when moving views.

Contributions to v0.9.0 and later are distributed under AGPL-3.0-only. Submit original or documented compatible work. Contributors retain copyright; submitting a PR does not transfer it or grant the owner separate commercial relicensing rights. Preserve third-party and historical MIT notices. Any additional commercial rights need a separate explicit agreement.

Сообщения об ошибках, правки документации и вымышленные тестовые данные приветствуются. Соблюдайте приватность и контракты; нужны тесты пропусков/устаревания и ограниченные чтения. Не прикладывайте переписку или ключи.

Вклад в новые версии распространяется по AGPL-3.0-only. Автор сохраняет свои права; PR не передаёт авторские права или отдельное право коммерческого перелицензирования. Сохраняйте сторонние и прежние MIT-уведомления. Дополнительные права оформляются отдельным явным соглашением.
