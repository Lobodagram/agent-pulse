import AppKit
import SwiftUI
import Combine
import ServiceManagement

struct SubscriptionRow: View {
    var provider: Provider; @ObservedObject var store: PulseStore
    @State var date = ""; @State var kind = "renewal"
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(provider.name).font(.system(size: 13, weight: .semibold))
            HStack { Picker("Type", selection: $kind) { Text(tr("Renewal", "Продление")).tag("renewal"); Text(tr("Expiry", "Окончание")).tag("expiry"); Text(tr("No plan", "Без подписки")).tag("none") }.labelsHidden().frame(width: 146)
                TextField("YYYY-MM-DD", text: $date).textFieldStyle(.roundedBorder).disabled(kind == "none").frame(width: 134)
                Button(tr("Save", "Сохранить")) { store.save(provider: provider.id, date: date, kind: kind) }
            }
        }.onAppear { date = provider.subscription.date ?? ""; kind = provider.subscription.kind }
    }
}
struct LaunchAtLoginSettings: View {
    @ObservedObject var controller: LaunchAtLoginController
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Toggle(tr("Launch at login", "Запускать при входе в систему"), isOn: Binding(get: { controller.checked }, set: { controller.setEnabled($0) }))
                .disabled(controller.preview || !controller.allowed)
            if controller.preview {
                Text(tr("Demo: login items are unchanged.", "Демо: автозапуск не меняется."))
            } else if !controller.allowed {
                Text(tr("Move Agent Pulse to Applications to manage launch at login.", "Переместите Agent Pulse в Программы, чтобы настроить автозапуск."))
            } else if controller.status == .requiresApproval {
                Text(tr("Allow Agent Pulse in System Settings → General → Login Items.", "Разрешите Agent Pulse в Настройках системы → Основные → Объекты входа."))
                Button(tr("Open Login Items", "Открыть объекты входа")) { SMAppService.openSystemSettingsLoginItems() }
            } else {
                Text(controller.status == .enabled ? tr("Enabled for your account. Uncheck to disable.", "Включено для вашей учётной записи. Снимите галочку для отключения.") : controller.status == .disabled ? tr("Off. Enable to start after you sign in.", "Выключено. Включите для запуска после входа в систему.") : tr("System status is unavailable.", "Состояние в системе недоступно."))
            }
            if controller.failed { Text(tr("Could not change launch at login. The checkbox shows the current system state.", "Не удалось изменить автозапуск. Галочка показывает текущее состояние системы.")).foregroundStyle(amber) }
        }.font(.system(size: 12)).onAppear { controller.refresh() }
            .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in controller.refresh() }
    }
}
struct SettingsView: View {
    @ObservedObject var store: PulseStore; var actions: AppDelegate
    @State var providerKeys: [String:String] = [:]
    @State var kimiRegion = "mainland-cn"
    @State var selected: Set<String> = []; @State var patterns = false; @State var tokens = false
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                PulseBrandMark(size: 30)
                Text(tr("Agent Pulse settings", "Настройки Agent Pulse")).font(.system(size: 23, weight: .medium))
                Spacer()
                ActionButton(symbol: "minus", help: tr("Minimize settings", "Свернуть настройки"), action: actions.minimizeSettings)
                ActionButton(symbol: "xmark", help: tr("Close settings", "Закрыть настройки"), action: actions.closeSettings)
            }.padding(.horizontal, 26).padding(.top, 18).padding(.bottom, 8)
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Picker(tr("Language", "Язык"), selection: $store.language) { Text("English").tag("en"); Text("Русский").tag("ru") }.frame(width: 260)
                LaunchAtLoginSettings(controller: store.launchAtLogin)
                Toggle(tr("Keep widget above windows", "Держать поверх окон"), isOn: $store.topmost).onChange(of: store.topmost) { _, value in actions.panel?.level = value ? .floating : .normal }
                Text(tr("Widget size", "Размер виджета")).font(.system(size: 16, weight: .semibold))
                HStack { ForEach([0.8, 0.9, 1.0], id: \.self) { value in Button("\(Int(value * 100))%") { actions.setScale(value) } }; Text("\(Int(store.widgetScale * 100))%") }
                Slider(value: Binding(get: { store.widgetScale }, set: { actions.setScale($0) }), in: 0.8...1).frame(width: 300)
                Text(tr("Or drag the lower-right corner. Details and analytics stay available.", "Можно тянуть за нижний правый угол. Детали и аналитика остаются доступны.")).font(.system(size: 11)).foregroundStyle(quiet)
                Picker(tr("Placement", "Размещение"), selection: Binding(get: { store.displayMode }, set: { actions.setDisplayMode($0) })) {
                    Text(tr("Floating widget", "Плавающий виджет")).tag("floating"); Text(tr("Menu bar only", "Только строка меню")).tag("menu")
                }.frame(width: 350)
                Toggle(tr("Compact values in menu bar", "Короткие значения в строке меню"), isOn: $store.menuNumbers)
                Toggle(tr("Follow the active app in the menu bar", "Следовать за активным приложением сверху"), isOn: $store.menuFollowActive)
                Text(tr("Recognizes Codex, ZCode and Claude desktop app IDs only. Terminals and other windows use rotation; no window titles or chat content are read.", "Распознаёт идентификаторы приложений Codex, ZCode и Claude. В терминалах и других окнах — чередование; заголовки окон и чаты не читаются.")).font(.system(size: 11)).foregroundStyle(quiet)
                Text(tr("Remaining percentages for selected clients; one client at a time, rotating every 8 seconds. Click to show/hide the movable widget; — means unavailable.", "Проценты остатка выбранных клиентов; один клиент за раз, смена каждые 8 секунд. Нажатие показывает/скрывает подвижное табло; — значит нет данных.")).font(.system(size: 11)).foregroundStyle(quiet)
                Picker(tr("Widget metric", "Показатель виджета"), selection: $store.metricMode) { Text(tr("Remaining limits", "Остаток лимитов")).tag("limits"); Text(tr("Tokens today · UTC", "Токены сегодня · UTC")).tag("today") }.frame(width: 350)
                ForEach(["glm", "kimi"], id: \.self) { id in
                    Text(id == "glm" ? "GLM Coding Plan · Z.ai" : "Kimi Code · API key").font(.system(size: 16, weight: .semibold))
                    if id == "kimi" { Picker(tr("Kimi key region", "Регион ключа Kimi"), selection: $kimiRegion) { Text("kimi.com").tag("mainland-cn"); Text("kimi.ai").tag("global") }.frame(width: 350) }
                    SecureField(tr("Own provider key", "Личный ключ провайдера"), text: Binding(get: { providerKeys[id] ?? "" }, set: { providerKeys[id] = $0 })).textFieldStyle(.roundedBorder).frame(width: 350)
                    HStack {
                        Button(tr("Save key", "Сохранить ключ")) { store.saveProviderKey(id, providerKeys[id] ?? "", region: id == "kimi" ? kimiRegion : "mainland-cn"); providerKeys[id] = "" }.disabled((providerKeys[id] ?? "").isEmpty || store.isFixture || store.providerKeySaving)
                        Button(tr("Disconnect quotas", "Отключить квоты")) { store.saveProviderKey(id, ""); providerKeys[id] = "" }.disabled(store.isFixture || store.providerKeySaving)
                    }
                }
                Text(tr("Own keys stay in private Secrets.json, outside Git. Native credentials are never read. Kimi Chat/Work login is not a Kimi Code key; quotas do not report token spend.", "Личные ключи хранятся в закрытом Secrets.json вне Git. Ключи приложений не читаются. Вход в Kimi Chat/Work не заменяет ключ Kimi Code; квоты не передают расход токенов.")).font(.system(size: 11)).foregroundStyle(quiet)
                Text(tr("Clients", "Клиенты")).font(.system(size: 16, weight: .semibold))
                ForEach(store.snapshot?.catalog ?? []) { spec in
                    Toggle(isOn: Binding(get: { selected.contains(spec.id) }, set: { on in if on { selected.insert(spec.id) } else { selected.remove(spec.id) } })) { VStack(alignment: .leading, spacing: 2) { Text(spec.name); Text(spec.mode == "import" ? tr("Import only; no automatic quota adapter", "Только импорт; автоматических лимитов нет") : spec.mode == "native" ? tr("Built-in client statistics", "Штатная статистика клиента") : spec.mode == "statusline" ? tr("Local status-line bridge", "Локальный мост status-line") : spec.mode == "loopback" ? tr("Existing local dashboard", "Уже запущенное локальное табло") : tr("Optional quota API", "Опциональное чтение квот")).font(.system(size: 10)).foregroundStyle(quiet) } }
                }
                Toggle(tr("Local Codex tokens today · partial", "Локальные токены Codex за сегодня · частично"), isOn: $tokens)
                Text(tr("Off by default. Reads bounded token events from native session paths when account daily reporting lags. No conversation text is saved. UTC day; partial device-wide work across accounts.", "По умолчанию выключено. Читает ограниченные события токенов по путям штатного клиента, когда дневной отчёт задерживается. Тексты чатов не сохраняются. День UTC; частичная работа на устройстве через смену аккаунтов.")).font(.system(size: 11)).foregroundStyle(quiet)
                Toggle(tr("Optional local Codex event projection", "Опциональный анализ локальных событий Codex"), isOn: $patterns)
                Text(tr("Off by default. Transient parsing of bounded recent event files; only counters and tool categories are retained.", "По умолчанию выключено. Ограниченное чтение недавних событий; сохраняются только счётчики и категории инструментов.")).font(.system(size: 11)).foregroundStyle(quiet)
                Button(tr("Apply client selection", "Применить выбор клиентов")) { store.configure((store.snapshot?.catalog ?? []).filter { selected.contains($0.id) }.map { $0.id }, patterns: patterns, tokens: tokens) }
                Divider().overlay(divider)
                Text(tr("Local event observers · opt in", "Локальные наблюдатели · по выбору")).font(.system(size: 16, weight: .semibold))
                Text(tr("Records sanitized metadata only. Start a new client session after setup; native hook trust review may be required. Existing hooks are preserved.", "Записываются только очищенные метаданные. После настройки начните новую сессию; клиент может запросить доверие хуку. Существующие хуки сохраняются.")).font(.system(size: 11)).foregroundStyle(quiet)
                ForEach(["codex", "glm", "claude", "kimi"], id: \.self) { id in
                    HStack { Text(id.uppercased()).frame(width: 70, alignment: .leading); Button(tr("Enable", "Включить")) { store.observer(id, enable: true) }; Button(tr("Remove", "Удалить")) { store.observer(id, enable: false) } }
                }
                Divider().overlay(divider)
                Text(tr("Billing dates · manual", "Даты подписок · вручную")).font(.system(size: 16, weight: .semibold))
                ForEach(store.snapshot?.providers ?? []) { p in SubscriptionRow(provider: p, store: store) }
                if let m = store.settingsMessage { Text(m).foregroundStyle(mint) }
                Text(tr("Counters every 5 minutes; Codex limits every minute. Configure bridges/imports as documented in the provider guide. No screen, microphone or Accessibility permission required.", "Счётчики — каждые 5 минут; лимиты Codex — каждую минуту. Мосты и импорт настраиваются по инструкции. Доступ к экрану, микрофону и Accessibility не требуется.")).font(.system(size: 11)).foregroundStyle(quiet)
            }.padding(26)
        }
        }.frame(width: 560, height: 620).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .onAppear { selected = Set((store.snapshot?.providers ?? []).map { $0.id }); patterns = store.snapshot?.localPatterns ?? false; tokens = store.snapshot?.localTokens ?? false }
    }
}

