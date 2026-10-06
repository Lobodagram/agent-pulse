import AppKit
import SwiftUI
import Charts

var russian: Bool { UserDefaults.standard.string(forKey: "language") == "ru" }
func tr(_ en: String, _ ru: String) -> String { russian ? ru : en }
struct Quota: Codable, Identifiable {
    var bucket: String; var kind: String; var durationMinutes: Double?; var remainingPercent: Double?; var resetsAt: Double?
    var id: String { bucket + kind + String(durationMinutes ?? 0) }
    var label: String {
        if let m = durationMinutes { return m >= 10080 ? tr("Week", "Неделя") : m == 300 ? tr("5 hours", "5 часов") : "\(Int(m / 60)) h" }
        return tr("Window", "Окно")
    }
}
struct Subscription: Codable { var date: String?; var kind: String; var source: String }
struct Provider: Codable, Identifiable {
    var id: String; var name: String; var status: String; var quotas: [Quota]
    var todayTokens: Double?; var lifetimeTokens: Double?; var periodTokens: Double?; var contextTokens: Double?
    var sessions: Double?; var resetCredits: Double?; var sourceStatus: [String]
    var observedAt: Double?; var lastSuccessfulAt: Double?; var tokenSource: String?; var tokenCoverage: String?; var todayTokenCoverage: String?; var subscription: Subscription
}
struct ProviderSpec: Codable, Identifiable { var id: String; var name: String; var mode: String; var support: String }
struct DayUsage: Codable, Identifiable {
    var provider: String; var date: String; var tokens: Double
    var id: String { provider + date }
    var day: Date { isoDay.date(from: date) ?? .distantPast }
}
struct Pattern: Codable, Identifiable {
    var provider: String; var name: String; var count: Double; var errors: Double?; var source: String; var suggestion: String
    var id: String { provider + name }
}
struct Snapshot: Codable {
    var generatedAt: Double; var providers: [Provider]; var history: [DayUsage]; var patterns: [Pattern]
    var patternCoverage: String; var privacy: String; var catalog: [ProviderSpec]?; var localPatterns: Bool?
}
let isoDay: DateFormatter = { let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(secondsFromGMT: 0); f.dateFormat = "yyyy-MM-dd"; return f }()
let bg = Color(red: 0.082, green: 0.102, blue: 0.114)
let ink = Color(red: 0.949, green: 0.965, blue: 0.957)
let quiet = Color(red: 0.651, green: 0.706, blue: 0.690)
let mint = Color(red: 0.643, green: 0.910, blue: 0.804)
let amber = Color(red: 0.945, green: 0.757, blue: 0.482)
let divider = Color(red: 0.188, green: 0.224, blue: 0.239)
func shortNumber(_ value: Double?) -> String {
    guard let v = value, v.isFinite else { return "—" }
    let f = NumberFormatter(); f.locale = Locale(identifier: russian ? "ru_RU" : "en_US"); f.maximumFractionDigits = v < 1000 ? 0 : 1
    let scale: Double; let suffix: String
    if v >= 1e9 { scale = 1e9; suffix = tr("B", " млрд") }
    else if v >= 1e6 { scale = 1e6; suffix = tr("M", " млн") }
    else if v >= 1000 { scale = 1000; suffix = tr("K", " тыс.") }
    else { scale = 1; suffix = "" }
    return (f.string(from: NSNumber(value: v / scale)) ?? "—") + suffix
}
func fullNumber(_ value: Double?) -> String {
    guard let v = value else { return tr("not reported", "не передано") }
    let f = NumberFormatter(); f.numberStyle = .decimal; f.locale = Locale(identifier: russian ? "ru_RU" : "en_US"); f.maximumFractionDigits = 0
    return f.string(from: NSNumber(value: v)) ?? "—"
}
func stamp(_ value: Double?, compact: Bool = false) -> String {
    guard let value else { return tr("not reported", "не передано") }
    let f = DateFormatter(); f.locale = Locale(identifier: russian ? "ru_RU" : "en_US"); f.dateFormat = compact ? "d MMM, HH:mm" : "d MMMM, HH:mm"
    return f.string(from: Date(timeIntervalSince1970: value))
}
func subscriptionText(_ s: Subscription) -> String {
    if s.kind == "none" { return tr("No subscription", "Без подписки") }
    guard let d = s.date else { return tr("Billing date not set", "Дата подписки не указана") }
    return (s.kind == "expiry" ? tr("Expiry: ", "Окончание: ") : tr("Renewal: ", "Продление: ")) + d + tr(" · manual", " · вручную")
}
@MainActor final class PulseStore: ObservableObject {
    @Published var snapshot: Snapshot?; @Published var loading = false; @Published var error: String?; @Published var settingsMessage: String?
    @Published var expanded = false; @Published var topmost = true; @Published var page = 0
    @Published var language: String = UserDefaults.standard.string(forKey: "language") ?? "en" { didSet { UserDefaults.standard.set(language, forKey: "language") } }
    let fixture: String?; private var timer: Timer?
    init() {
        let args = CommandLine.arguments
        fixture = args.firstIndex(of: "--fixture").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        if let i = args.firstIndex(of: "--language"), i + 1 < args.count { language = args[i + 1]; UserDefaults.standard.set(language, forKey: "language") }
        if let fixture {
            do { snapshot = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: URL(fileURLWithPath: fixture))) }
            catch { self.error = tr("Could not load demo", "Не удалось прочитать демо") }
        } else {
            refresh(); timer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } }
        }
    }
    var isFixture: Bool { fixture != nil }
    var pages: Int { max(1, ((snapshot?.providers.count ?? 0) + 1) / 2) }
    var visibleProviders: [Provider] { Array((snapshot?.providers ?? []).dropFirst(min(page, pages - 1) * 2).prefix(2)) }
    func run(_ arguments: [String], completion: @escaping @MainActor (Result<Data, Error>) -> Void) {
        let resources = Bundle.main.resourceURL!
        DispatchQueue.global(qos: .utility).async {
            do {
                let process = Process(); let bundled = resources.appendingPathComponent("pulse-collector")
                if FileManager.default.isExecutableFile(atPath: bundled.path) { process.executableURL = bundled; process.arguments = arguments }
                else { process.executableURL = URL(fileURLWithPath: "/usr/bin/env"); process.arguments = ["python3", resources.appendingPathComponent("collector.py").path] + arguments }
                var env = ProcessInfo.processInfo.environment
                env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin")
                process.environment = env
                let output = Pipe(); process.standardOutput = output; process.standardError = FileHandle.nullDevice
                try process.run(); let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
                guard process.terminationStatus == 0 else { throw NSError(domain: "AgentPulse", code: Int(process.terminationStatus)) }
                Task { @MainActor in completion(.success(data)) }
            } catch { Task { @MainActor in completion(.failure(error)) } }
        }
    }
    func refresh() {
        guard !loading, !isFixture else { return }; loading = true; error = nil
        run(["snapshot"]) { [weak self] result in
            guard let self else { return }; self.loading = false
            switch result {
            case .success(let data):
                do { self.snapshot = try JSONDecoder().decode(Snapshot.self, from: data); self.page = min(self.page, self.pages - 1) }
                catch { self.error = tr("Invalid metrics response", "Неполный ответ источника") }
            case .failure: self.error = tr("Refresh failed; last data retained", "Не удалось обновить; сохранены последние данные")
            }
        }
    }
    func configure(_ ids: [String], patterns: Bool) {
        guard !isFixture else { settingsMessage = tr("Demo: settings are not saved", "Демо: настройки не сохраняются"); return }
        run(["configure", "--providers", ids.joined(separator: ","), "--local-patterns", patterns ? "on" : "off"]) { [weak self] result in
            if case .success = result { self?.refresh() }
            else { self?.settingsMessage = tr("Could not save", "Не удалось сохранить") }
        }
    }
    func save(provider: String, date: String, kind: String) {
        guard !isFixture else { settingsMessage = tr("Demo: settings are not saved", "Демо: настройки не сохраняются"); return }
        let value = date.trimmingCharacters(in: .whitespacesAndNewlines)
        if !value.isEmpty && (isoDay.date(from: value) == nil || isoDay.string(from: isoDay.date(from: value)!) != value) { settingsMessage = tr("Use a valid YYYY-MM-DD date", "Введите существующую дату ГГГГ-ММ-ДД"); return }
        run(["subscription", "--provider", provider, "--date", kind == "none" ? "" : value, "--kind", kind]) { [weak self] r in
            guard let self else { return }
            if case .success = r {
                self.settingsMessage = tr("Saved locally", "Сохранено локально")
                if let index = self.snapshot?.providers.firstIndex(where: { $0.id == provider }) { self.snapshot?.providers[index].subscription = Subscription(date: value.isEmpty || kind == "none" ? nil : value, kind: kind, source: "manual") }
            } else { self.settingsMessage = tr("Could not save date", "Не удалось сохранить дату") }
        }
    }
}
struct DragHandle: NSViewRepresentable {
    final class Grip: NSView { override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) } }
    func makeNSView(context: Context) -> Grip { Grip() }; func updateNSView(_ nsView: Grip, context: Context) {}
}
struct ActionButton: View {
    var symbol: String; var help: String; var action: () -> Void
    var body: some View { Button(action: action) { Image(systemName: symbol).frame(width: 26, height: 26) }.buttonStyle(.plain).foregroundStyle(quiet).help(help).accessibilityLabel(help) }
}
struct ProviderLine: View {
    let provider: Provider
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(provider.name.uppercased()).font(.system(size: 10, weight: .bold, design: .monospaced)).tracking(1).foregroundStyle(quiet)
                Spacer()
                Text(provider.status == "ready" ? tr("reported", "получено") : provider.status == "stale" ? tr("stale", "устарело") : tr("unavailable", "нет данных")).font(.system(size: 10)).foregroundStyle(provider.status == "ready" ? quiet : amber)
            }
            if !provider.quotas.isEmpty {
                HStack(spacing: 18) {
                    ForEach(provider.quotas.prefix(2)) { q in
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            Text(q.remainingPercent.map { String(format: "%.0f%%", $0) } ?? "—").font(.system(size: 23, weight: .medium, design: .monospaced)).foregroundStyle((q.remainingPercent ?? 100) < 15 ? amber : mint)
                            VStack(alignment: .leading, spacing: 1) { Text(q.label).font(.system(size: 10)); Text(stamp(q.resetsAt, compact: true)).font(.system(size: 9)).foregroundStyle(quiet) }
                        }
                    }
                }
                Text(tr("Tokens today: ", "Токены сегодня: ") + shortNumber(provider.todayTokens) + (provider.todayTokenCoverage == "partial-local" ? tr(" · partial", " · частично") : "")).font(.system(size: 10)).foregroundStyle(quiet)
            } else {
                HStack(alignment: .firstTextBaseline) {
                    Text(shortNumber(provider.todayTokens ?? provider.periodTokens ?? provider.contextTokens)).font(.system(size: 23, weight: .medium, design: .monospaced))
                    Text(provider.contextTokens != nil && provider.todayTokens == nil && provider.periodTokens == nil ? tr("context size", "размер контекста") : provider.todayTokens != nil ? tr("tokens today · UTC", "токены сегодня · UTC") : provider.periodTokens != nil ? tr("local tokens · 7 days", "локально · 7 дней") : tr("not reported", "не передано")).font(.system(size: 10)).foregroundStyle(quiet)
                }
                Text(subscriptionText(provider.subscription)).font(.system(size: 10)).foregroundStyle(quiet)
            }
        }.foregroundStyle(ink)
    }
}
struct WidgetView: View {
    @ObservedObject var store: PulseStore; var actions: AppDelegate
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 4) {
                HStack(spacing: 4) { Circle().fill(store.loading ? amber : mint).frame(width: 6, height: 6); Text("AGENT PULSE").font(.system(size: 11, weight: .semibold)).tracking(1); if store.isFixture { Text("DEMO").font(.system(size: 9)).foregroundStyle(amber) } }.frame(height: 26).overlay(DragHandle()).help(tr("Drag by this title", "Перетащить за заголовок"))
                Spacer()
                ActionButton(symbol: "arrow.clockwise", help: tr("Refresh", "Обновить"), action: store.refresh)
                ActionButton(symbol: "chart.bar.xaxis", help: tr("Analytics", "Аналитика"), action: actions.showAnalysis)
                ActionButton(symbol: "gearshape", help: tr("Settings", "Настройки"), action: actions.showSettings)
                ActionButton(symbol: "minus", help: tr("Hide to menu bar", "Скрыть в строку меню"), action: actions.hidePanel)
            }
            if let snapshot = store.snapshot {
                ForEach(store.visibleProviders) { p in ProviderLine(provider: p); Rectangle().fill(divider).frame(height: 1) }
                if store.visibleProviders.isEmpty { Text(tr("Choose clients in Settings", "Выберите клиентов в настройках")).foregroundStyle(quiet); Spacer() }
                if store.expanded {
                    ForEach(store.visibleProviders) { p in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(p.name).font(.system(size: 12, weight: .semibold))
                            Text(subscriptionText(p.subscription)).font(.system(size: 11)).foregroundStyle(quiet)
                            Text(tr("Today: ", "Сегодня: ") + fullNumber(p.todayTokens)).font(.system(size: 10)).foregroundStyle(quiet)
                            if p.id == "codex" { Text(tr("Reset credits: ", "Доступные сбросы: ") + fullNumber(p.resetCredits)).font(.system(size: 10)).foregroundStyle(quiet) }
                        }
                    }
                    Text(tr("Quotas, token counts and billing dates are separate measurements.", "Лимиты, токены и даты оплаты — разные измерения.")).font(.system(size: 10)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                HStack(spacing: 8) {
                    if store.pages > 1 { Button("‹") { store.page = (store.page + store.pages - 1) % store.pages }.buttonStyle(.plain); Text("\(store.page + 1)/\(store.pages)"); Button("›") { store.page = (store.page + 1) % store.pages }.buttonStyle(.plain) }
                    Text(store.error ?? (store.loading ? tr("Updating…", "Обновление…") : stamp(snapshot.generatedAt, compact: true))).lineLimit(1)
                    Spacer(); Button(store.expanded ? tr("Less ↑", "Меньше ↑") : tr("Details ↓", "Детали ↓")) { actions.toggleExpanded() }.buttonStyle(.plain).foregroundStyle(mint)
                }.font(.system(size: 9)).foregroundStyle(store.error == nil ? quiet : amber)
            } else { Spacer(); Text(store.error ?? tr("Reading client counters…", "Читаю счётчики клиентов…")).font(.system(size: 12)).foregroundStyle(quiet); Spacer() }
        }.padding(.horizontal, 18).padding(.vertical, 10).frame(width: 360, height: store.expanded ? 430 : 270, alignment: .topLeading).background(bg).foregroundStyle(ink).colorScheme(.dark)
    }
}
struct AnalysisView: View {
    @ObservedObject var store: PulseStore
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack { Text(tr("Agent activity", "Работа агентов")).font(.system(size: 26, weight: .medium)); Spacer(); Button(tr("Refresh", "Обновить"), action: store.refresh).disabled(store.loading || store.isFixture) }
                Text(tr("Reported counters. Missing days are unknown, not zero. Daily history uses UTC.", "Счётчики источников. Пропущенные дни неизвестны, а не равны нулю. История по UTC.")).font(.system(size: 12)).foregroundStyle(quiet)
                if let snapshot = store.snapshot {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 16) {
                        ForEach(snapshot.providers) { p in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(p.name).font(.system(size: 16, weight: .semibold))
                                Text(tr("Tokens today: ", "Токены сегодня: ") + fullNumber(p.todayTokens)).font(.system(size: 12))
                                if let context = p.contextTokens { Text(tr("Context gauge: ", "Размер контекста: ") + fullNumber(context)).font(.system(size: 11)).foregroundStyle(amber) }
                                Text(subscriptionText(p.subscription)).font(.system(size: 11)).foregroundStyle(quiet)
                                Text(p.tokenSource ?? tr("Source unavailable", "Источник недоступен")).font(.system(size: 10)).foregroundStyle(quiet)
                                Text(p.tokenCoverage ?? p.todayTokenCoverage ?? "").font(.system(size: 10)).foregroundStyle(quiet)
                                Text(p.status).font(.system(size: 10)).foregroundStyle(p.status == "ready" ? mint : amber)
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    Divider().overlay(divider)
                    Text(tr("Tokens by day", "Токены по дням")).font(.system(size: 16, weight: .semibold))
                    if snapshot.history.isEmpty { Text(tr("No history reported", "История ещё не получена")).foregroundStyle(quiet) }
                    else {
                        Chart(snapshot.history) { item in BarMark(x: .value("Date", item.day, unit: .day), y: .value("Tokens", item.tokens)).foregroundStyle(by: .value("Client", item.provider)).position(by: .value("Client", item.provider)) }.chartXAxis { AxisMarks(values: .stride(by: .day, count: 4)) { _ in AxisValueLabel(format: .dateTime.day().month(.abbreviated)) } }.frame(height: 160)
                    }
                    Text(tr("Coverage differs by client. Context size and subscription quotas are not token spend; do not total them as billed usage.", "Охват различается. Размер контекста и лимиты подписки не равны расходу токенов; их нельзя суммировать как оплаченный расход.")).font(.system(size: 11)).foregroundStyle(quiet)
                    Divider().overlay(divider)
                    Text(tr("Repeated calls · 7 days", "Повторяющиеся вызовы · 7 дней")).font(.system(size: 16, weight: .semibold))
                    Text(tr("Optional partial Codex events and client aggregates. Static command categories are hints, not proof of execution. Counts do not attribute tokens to tools.", "Опциональная выборка событий Codex и агрегаты клиентов. Статические группы команд — признаки, а не доказательство исполнения. Токены инструментам не приписываются.")).font(.system(size: 11)).foregroundStyle(quiet)
                    if snapshot.patterns.isEmpty { Text(tr("Not enough records yet", "Пока недостаточно записей")).foregroundStyle(quiet) }
                    ForEach(snapshot.patterns.prefix(15)) { p in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack { Text(p.name).font(.system(size: 12, weight: .medium, design: .monospaced)); Spacer(); Text(p.provider + " · " + shortNumber(p.count)).font(.system(size: 12, design: .monospaced)).foregroundStyle(mint) }
                            Text(tr("Review the workflow before adding a skill, tool or MCP.", "Изучите сценарий перед созданием скилла, инструмента или MCP.")).font(.system(size: 11)).foregroundStyle(quiet)
                            Text(p.source).font(.system(size: 10)).foregroundStyle(quiet)
                        }.padding(.vertical, 5)
                        Rectangle().fill(divider).frame(height: 1)
                    }
                    Text(tr("Only counters and sanitized tool names persist. No prompts, arguments, results or code. No model calls.", "Сохраняются счётчики и безопасные имена инструментов. Без промптов, аргументов, результатов и кода. Модели не вызываются.")).font(.system(size: 11)).foregroundStyle(quiet)
                }
            }.padding(28)
        }.background(bg).foregroundStyle(ink).colorScheme(.dark).environment(\.locale, Locale(identifier: store.language == "ru" ? "ru_RU" : "en_US"))
    }
}
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
struct SettingsView: View {
    @ObservedObject var store: PulseStore; var actions: AppDelegate
    @State var selected: Set<String> = []; @State var patterns = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(tr("Agent Pulse settings", "Настройки Agent Pulse")).font(.system(size: 23, weight: .medium))
                Picker(tr("Language", "Язык"), selection: $store.language) { Text("English").tag("en"); Text("Русский").tag("ru") }.frame(width: 260)
                Toggle(tr("Keep widget above windows", "Держать поверх окон"), isOn: $store.topmost).onChange(of: store.topmost) { _, value in actions.panel?.level = value ? .floating : .normal }
                Text(tr("Clients", "Клиенты")).font(.system(size: 16, weight: .semibold))
                ForEach(store.snapshot?.catalog ?? []) { spec in
                    Toggle(isOn: Binding(get: { selected.contains(spec.id) }, set: { on in if on { selected.insert(spec.id) } else { selected.remove(spec.id) } })) { VStack(alignment: .leading, spacing: 2) { Text(spec.name); Text(spec.mode == "import" ? tr("Import only; no automatic quota adapter", "Только импорт; автоматических лимитов нет") : spec.mode == "native" ? tr("Built-in client statistics", "Штатная статистика клиента") : spec.mode == "statusline" ? tr("Local status-line bridge", "Локальный мост status-line") : spec.mode == "loopback" ? tr("Existing local dashboard", "Уже запущенное локальное табло") : tr("Optional quota API", "Опциональное чтение квот")).font(.system(size: 10)).foregroundStyle(quiet) } }
                }
                Toggle(tr("Optional local Codex event projection", "Опциональный анализ локальных событий Codex"), isOn: $patterns)
                Text(tr("Off by default. Transient parsing of bounded recent event files; only counters and tool categories are retained.", "По умолчанию выключено. Ограниченное чтение недавних событий; сохраняются только счётчики и категории инструментов.")).font(.system(size: 11)).foregroundStyle(quiet)
                Button(tr("Apply client selection", "Применить выбор клиентов")) { store.configure((store.snapshot?.catalog ?? []).filter { selected.contains($0.id) }.map { $0.id }, patterns: patterns) }
                Divider().overlay(divider)
                Text(tr("Billing dates · manual", "Даты подписок · вручную")).font(.system(size: 16, weight: .semibold))
                ForEach(store.snapshot?.providers ?? []) { p in SubscriptionRow(provider: p, store: store) }
                if let m = store.settingsMessage { Text(m).foregroundStyle(mint) }
                Text(tr("Refresh every 5 minutes. Configure bridges/imports as documented in the provider guide. No screen, microphone or Accessibility permission required.", "Обновление каждые 5 минут. Мосты и импорт настраиваются по инструкции. Доступ к экрану, микрофону и Accessibility не требуется.")).font(.system(size: 11)).foregroundStyle(quiet)
            }.padding(26)
        }.frame(width: 560, height: 620).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .onAppear { selected = Set((store.snapshot?.providers ?? []).map { $0.id }); patterns = store.snapshot?.localPatterns ?? false }
    }
}

final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var store: PulseStore!
    var panel: FloatingPanel?
    var statusItem: NSStatusItem!
    var analysisWindow: NSWindow?
    var settingsWindow: NSWindow?
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        store = PulseStore()
        let main = NSMenu()
        let appMenu = NSMenu()
        let appRoot = NSMenuItem(); appRoot.submenu = appMenu; main.addItem(appRoot)
        let quitItem = NSMenuItem(title: tr("Quit Agent Pulse", "Завершить Agent Pulse"), action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self; appMenu.addItem(quitItem)
        let editRoot = NSMenuItem(title: tr("Edit", "Правка"), action: nil, keyEquivalent: "")
        let edit = NSMenu(title: tr("Edit", "Правка")); editRoot.submenu = edit; main.addItem(editRoot)
        for (title, action, key) in [(tr("Cut", "Вырезать"), "cut:", "x"), (tr("Copy", "Копировать"), "copy:", "c"), (tr("Paste", "Вставить"), "paste:", "v"), (tr("Select All", "Выделить всё"), "selectAll:", "a")] {
            edit.addItem(NSMenuItem(title: title, action: NSSelectorFromString(action), keyEquivalent: key))
        }
        NSApp.mainMenu = main
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "waveform.path.ecg", accessibilityDescription: "Agent Pulse")
        statusItem.button?.toolTip = "Agent Pulse — local agent counters"
        let menu = NSMenu()
        for (title, selector, key) in [(tr("Show / hide widget", "Показать / скрыть виджет"), #selector(togglePanel), ""), (tr("Analytics", "Аналитика"), #selector(openAnalysis), ""), (tr("Settings", "Настройки"), #selector(openSettings), ""), (tr("Refresh", "Обновить"), #selector(refresh), "r"), (tr("Quit Agent Pulse", "Завершить Agent Pulse"), #selector(quit), "q")] {
            let item = NSMenuItem(title: title, action: selector, keyEquivalent: key); item.target = self; menu.addItem(item)
        }
        statusItem.menu = menu
        let panel = FloatingPanel(contentRect: NSRect(x: 0, y: 0, width: 360, height: 270), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.title = "Agent Pulse"; panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isFloatingPanel = true; panel.hidesOnDeactivate = false; panel.isMovableByWindowBackground = true
        panel.isOpaque = false; panel.backgroundColor = .clear; panel.hasShadow = true
        panel.contentView = NSHostingView(rootView: WidgetView(store: store, actions: self))
        panel.contentView?.wantsLayer = true; panel.contentView?.layer?.cornerRadius = 14
        panel.contentView?.layer?.masksToBounds = true
        panel.setFrameAutosaveName("AgentPulsePanel")
        if !panel.setFrameUsingName("AgentPulsePanel"), let screen = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x: screen.maxX - 380, y: screen.maxY - 290))
        }
        self.panel = panel; panel.orderFrontRegardless()
        handleSnapshotArguments()
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        panel?.orderFrontRegardless(); return true
    }
    @objc func refresh() { store.refresh() }
    @objc func quit() { NSApp.terminate(nil) }
    @objc func togglePanel() { if panel?.isVisible == true { hidePanel() } else { panel?.orderFrontRegardless() } }
    func hidePanel() { panel?.orderOut(nil) }
    func toggleExpanded() {
        guard let panel else { return }
        let top = panel.frame.maxY
        store.expanded.toggle()
        panel.setFrame(NSRect(x: panel.frame.minX, y: top - (store.expanded ? 430 : 270), width: 360, height: store.expanded ? 430 : 270), display: true, animate: false)
    }
    @objc func openAnalysis() { showAnalysis() }
    func showAnalysis() {
        if analysisWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 620), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
            w.title = tr("Agent Pulse · analytics", "Agent Pulse · аналитика"); w.isReleasedWhenClosed = false; w.minSize = NSSize(width: 620, height: 520)
            w.contentView = NSHostingView(rootView: AnalysisView(store: store)); w.center(); analysisWindow = w
        }
        NSApp.activate(ignoringOtherApps: true); analysisWindow?.makeKeyAndOrderFront(nil)
    }
    @objc func openSettings() { showSettings() }
    func showSettings() {
        if settingsWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 620), styleMask: [.titled, .closable], backing: .buffered, defer: false)
            w.title = tr("Agent Pulse · settings", "Agent Pulse · настройки"); w.isReleasedWhenClosed = false
            w.contentView = NSHostingView(rootView: SettingsView(store: store, actions: self)); w.center(); settingsWindow = w
        }
        NSApp.activate(ignoringOtherApps: true); settingsWindow?.makeKeyAndOrderFront(nil)
    }
    func handleSnapshotArguments() {
        let args = CommandLine.arguments
        guard let index = args.firstIndex(of: "--snapshot"), index + 1 < args.count else { return }
        let path = args[index + 1]
        let mode = args.firstIndex(of: "--view").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } ?? "compact"
        if mode == "expanded" { toggleExpanded() }
        if mode.hasPrefix("analysis") { showAnalysis() }
        if mode == "analysis-small" { analysisWindow?.setContentSize(NSSize(width: 620, height: 520)) }
        if mode == "settings" { showSettings() }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self else { return }
            let w = mode.hasPrefix("analysis") ? self.analysisWindow : mode == "settings" ? self.settingsWindow : self.panel
            if let view = w?.contentView, let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: rep)
                if let data = rep.representation(using: .png, properties: [:]) { try? data.write(to: URL(fileURLWithPath: path)) }
            }
            if let panel = self.panel {
                let before = panel.isVisible
                self.hidePanel(); let hidden = !panel.isVisible
                self.togglePanel(); let restored = panel.isVisible
                let report: [String: Any] = ["view": mode, "panelWidth": panel.frame.width, "panelHeight": panel.frame.height, "floatingLevel": panel.level == .floating, "joinsAllSpaces": panel.collectionBehavior.contains(.canJoinAllSpaces), "fullScreenAuxiliary": panel.collectionBehavior.contains(.fullScreenAuxiliary), "movable": panel.isMovableByWindowBackground, "visibleBefore": before, "hidePassed": hidden, "restorePassed": restored, "statusItem": self.statusItem.button != nil, "fixtureMode": self.store.isFixture, "capturedSize": [w?.contentView?.bounds.width ?? 0, w?.contentView?.bounds.height ?? 0]]
                if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                    try? data.write(to: URL(fileURLWithPath: path + ".json"))
                }
            }
            NSApp.terminate(nil)
        }
    }
}
@main enum AgentPulseMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
        withExtendedLifetime(delegate) {}
    }
}
