import AppKit
import SwiftUI
import Charts
import Combine

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
    var accountScope: String?; var quotaObservedAt: Double?; var observedAt: Double?; var lastSuccessfulAt: Double?; var tokenSource: String?; var tokenCoverage: String?; var todayTokenCoverage: String?; var todayTokenStatus: String?; var subscription: Subscription
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
    var analytics: AnalyticsReport?
    var patternCoverage: String; var privacy: String; var catalog: [ProviderSpec]?; var localTokens: Bool?; var localPatterns: Bool?
}
struct EventCoverage: Codable, Identifiable {
    var provider: String; var state: String; var calls: Int; var pairedCalls: Int; var rejected: Int
    var id: String { provider }
}
struct WorkflowFinding: Codable, Identifiable {
    var id: String; var provider: String; var kind: String; var title: String; var titleRu: String
    var suggestion: String; var suggestionRu: String; var occurrences: Int; var sessions: Int
    var sequence: [String]; var evidenceSessions: [String]?; var evidenceIds: [String]; var inventoryStatus: String; var confidence: String
}
struct JournalCall: Codable, Identifiable {
    var id: String; var provider: String; var session: String; var tool: String; var category: String
    var template: String; var outcome: String; var durationMs: Double?; var durationSource: String
    var startedAt: Double?; var endedAt: Double?; var paired: Bool; var source: String; var turn_source: String
}
struct JournalSession: Codable, Identifiable {
    var id: String; var provider: String; var calls: Int; var failed: Int; var pending: Int; var paired: Int
    var elapsedMs: Double?; var startedAt: Double?; var label: String?; var outcome: String; var variant: String?
}
struct AnalyticsReport: Codable {
    var calls: Int; var inventoryCount: Int; var eventLimitReached: Bool
    var coverage: [EventCoverage]; var findings: [WorkflowFinding]; var sessions: [JournalSession]; var recentCalls: [JournalCall]
}
func categoryText(_ code: String) -> String {
    let ru = ["read":"чтение", "search":"поиск", "edit":"изменение", "test":"проверка", "build":"сборка", "inspect":"осмотр", "remote":"внешний инструмент", "shell":"команда", "other":"прочее", "delegate":"делегирование", "environment":"среда"]
    return russian ? ru[code] ?? code : code
}
func outcomeText(_ code: String) -> String {
    let ru = ["success":"успешно", "failed":"ошибка", "unknown":"неизвестно", "pending":"без завершения", "accepted":"принято", "rework":"доработка"]
    return russian ? ru[code] ?? code : code
}
func coverageText(_ code: String) -> String {
    return code == "receiving" ? tr("receiving events", "получает события") : code == "stale" ? tr("no recent events", "нет свежих событий") : tr("not observed", "не наблюдается")
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
    @Published var widgetScale: Double = min(1, max(0.8, UserDefaults.standard.double(forKey: "widgetScale") == 0 ? 1 : UserDefaults.standard.double(forKey: "widgetScale"))) { didSet { if !isFixture { UserDefaults.standard.set(widgetScale, forKey: "widgetScale") } } }
    @Published var displayMode: String = UserDefaults.standard.string(forKey: "displayMode") ?? "floating" { didSet { if !isFixture { UserDefaults.standard.set(displayMode, forKey: "displayMode") } } }
    @Published var menuNumbers: Bool = UserDefaults.standard.object(forKey: "menuNumbers") as? Bool ?? true { didSet { if !isFixture { UserDefaults.standard.set(menuNumbers, forKey: "menuNumbers") } } }
    let fixture: String?; private var timer: Timer?; private var limitTimer: Timer?; private var readingLimits = false; private var authTimer: Timer?; private var authMarks: [String: String] = [:]; private var authRevision = 0
    init() {
        let args = CommandLine.arguments
        fixture = args.firstIndex(of: "--fixture").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        if let i = args.firstIndex(of: "--language"), i + 1 < args.count { language = args[i + 1]; UserDefaults.standard.set(language, forKey: "language") }
        if let i = args.firstIndex(of: "--scale"), i + 1 < args.count, let value = Double(args[i + 1]) { widgetScale = min(1, max(0.8, value)) }
        if args.contains("--menu-only") { displayMode = "menu" }
        if let fixture {
            do { snapshot = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: URL(fileURLWithPath: fixture))) }
            catch { self.error = tr("Could not load demo", "Не удалось прочитать демо") }
        } else {
            authMarks = authenticationMetadata()
            authTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in Task { @MainActor in self?.checkAuthenticationChange() } }
            limitTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in Task { @MainActor in self?.refreshLimits() } }
            refresh(); timer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } }
        }
    }
    var baseHeight: Double { expanded ? 430 : 270 }
    var isFixture: Bool { fixture != nil }
    var pages: Int { max(1, ((snapshot?.providers.count ?? 0) + 1) / 2) }
    var visibleProviders: [Provider] { Array((snapshot?.providers ?? []).dropFirst(min(page, pages - 1) * 2).prefix(2)) }
    func run(_ arguments: [String], completion: @escaping @MainActor (Result<Data, Error>) -> Void) {
        let resources = Bundle.main.resourceURL!
        DispatchQueue.global(qos: .utility).async {
            do {
                let process = Process(); let bundled = resources.appendingPathComponent("pulse-collector")
                if FileManager.default.isExecutableFile(atPath: bundled.path) { process.executableURL = bundled; process.arguments = arguments }
                else { process.executableURL = URL(fileURLWithPath: "/usr/bin/env"); process.arguments = [ProcessInfo.processInfo.environment["AGENT_PULSE_PYTHON"] ?? "python3", resources.appendingPathComponent("collector.py").path] + arguments }
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
        guard !loading, !isFixture else { return }; loading = true; error = nil; let revision = authRevision
        run(["snapshot"]) { [weak self] result in
            guard let self else { return }; self.loading = false
            guard revision == self.authRevision else { self.refresh(); return }
            switch result {
            case .success(let data):
                do { var next = try JSONDecoder().decode(Snapshot.self, from: data)
                    if let old = self.snapshot?.providers.first(where: { $0.id == "codex" }), let idx = next.providers.firstIndex(where: { $0.id == "codex" }), old.accountScope == next.providers[idx].accountScope, (old.quotaObservedAt ?? 0) > (next.providers[idx].quotaObservedAt ?? 0) {
                        next.providers[idx].quotas = old.quotas; next.providers[idx].quotaObservedAt = old.quotaObservedAt
                    }
                    self.snapshot = next; self.page = min(self.page, self.pages - 1) }
                catch { self.error = tr("Invalid metrics response", "Неполный ответ источника") }
            case .failure: self.error = tr("Refresh failed; last data retained", "Не удалось обновить; сохранены последние данные")
            }
        }
    }
    func authenticationMetadata() -> [String: String] {
        // File attributes only. Never open authentication files or extract credentials.
        let home = FileManager.default.homeDirectoryForCurrentUser
        let roots = ["codex": ProcessInfo.processInfo.environment["CODEX_HOME"].map { URL(fileURLWithPath: $0).appendingPathComponent("auth.json") } ?? home.appendingPathComponent(".codex/auth.json"),
                     "glm": home.appendingPathComponent(".zcode/v2/provider_config.json"),
                     "claude": home.appendingPathComponent(".claude/.credentials.json"),
                     "kimi": home.appendingPathComponent(".kimi/config.toml"),
                     "qwen": home.appendingPathComponent(".qwen/oauth_creds.json")]
        var result: [String: String] = [:]
        let selected = Set(snapshot?.providers.map { $0.id } ?? ["codex", "glm"])
        for (id, path) in roots where selected.contains(id) {
            if let attributes = try? FileManager.default.attributesOfItem(atPath: path.path) {
                result[id] = String(describing: attributes[.modificationDate]) + ":" + String(describing: attributes[.size]) + ":" + String(describing: attributes[.systemFileNumber])
            } else { result[id] = "missing" }
        }
        return result
    }
    func checkAuthenticationChange() {
        guard !isFixture else { return }
        let next = authenticationMetadata()
        guard next != authMarks else { return }
        let changed = Set(next.keys).union(authMarks.keys).filter { next[$0] != authMarks[$0] }
        authMarks = next; authRevision += 1
        if var value = snapshot {
            for idx in value.providers.indices where changed.contains(value.providers[idx].id) {
                value.providers[idx].quotas = []; value.providers[idx].quotaObservedAt = nil
                value.providers[idx].todayTokens = nil; value.providers[idx].lifetimeTokens = nil
                value.providers[idx].periodTokens = nil; value.providers[idx].contextTokens = nil
                value.providers[idx].accountScope = nil; value.providers[idx].status = "unavailable"
                value.providers[idx].subscription = Subscription(date: nil, kind: "renewal", source: "manual")
            }
            snapshot = value
        }
        refreshLimits(); refresh()
    }
    func refreshLimits() {
        guard !isFixture, !readingLimits, snapshot?.providers.contains(where: { $0.id == "codex" }) == true else { return }
        readingLimits = true; let revision = authRevision
        run(["limits"]) { [weak self] result in
            guard let self else { return }; self.readingLimits = false
            guard revision == self.authRevision else { self.refreshLimits(); return }
            struct LimitResult: Decodable { var status: String; var quotas: [Quota]; var quotaObservedAt: Double?; var accountScope: String? }
            if case .success(let data) = result, let value = try? JSONDecoder().decode(LimitResult.self, from: data), value.status == "ready", let idx = self.snapshot?.providers.firstIndex(where: { $0.id == "codex" }) {
                let switched = self.snapshot?.providers[idx].accountScope != nil && value.accountScope != nil && self.snapshot?.providers[idx].accountScope != value.accountScope
                if switched {
                    self.authRevision += 1
                    self.snapshot?.providers[idx].todayTokens = nil; self.snapshot?.providers[idx].lifetimeTokens = nil
                    self.snapshot?.providers[idx].subscription = Subscription(date: nil, kind: "renewal", source: "manual")
                    // General task/token history continues across account changes.
                }
                self.snapshot?.providers[idx].accountScope = value.accountScope
                self.snapshot?.providers[idx].quotas = value.quotas; self.snapshot?.providers[idx].quotaObservedAt = value.quotaObservedAt
                if switched { self.refresh() }
            }
        }
    }
    func observer(_ provider: String, enable: Bool) {
        guard !isFixture else { settingsMessage = tr("Demo: no configuration changes", "Демо: настройки не меняются"); return }
        run(["hooks", "--provider", provider, "--action", enable ? "install" : "remove"]) { [weak self] result in
            if case .success = result { self?.settingsMessage = tr("Observer configured. Start a new client session; Codex may request hook trust review.", "Наблюдатель настроен. Начните новую сессию клиента; Codex может запросить проверку доверия хуку.") }
            else { self?.settingsMessage = tr("Configuration failed; inspect the local CLI", "Настройка не удалась; проверьте локальную CLI") }
        }
    }
    func configure(_ ids: [String], patterns: Bool, tokens: Bool) {
        guard !isFixture else { settingsMessage = tr("Demo: settings are not saved", "Демо: настройки не сохраняются"); return }
        run(["configure", "--providers", ids.joined(separator: ","), "--local-patterns", patterns ? "on" : "off", "--local-tokens", tokens ? "on" : "off"]) { [weak self] result in
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
    var body: some View { Button(action: action) { Image(systemName: symbol).frame(width: 30, height: 30) }.buttonStyle(.plain).foregroundStyle(quiet).help(help).accessibilityLabel(help) }
}
func todayText(_ p: Provider) -> String {
    if let value = p.todayTokens { return shortNumber(value) + (p.todayTokenCoverage == "partial-local" ? tr(" · partial", " · частично") : "") }
    return p.todayTokenStatus == "account-day-pending" ? tr("awaiting report", "жду отчёт") : p.todayTokenStatus == "local-day-pending" ? tr("no local data yet", "ещё нет данных") : tr("not reported", "не передано")
}
struct ResizeGrip: NSViewRepresentable {
    var actions: AppDelegate
    final class Grip: NSView {
        var actions: AppDelegate?; var start: NSPoint = .zero; var width: Double = 360
        override var mouseDownCanMoveWindow: Bool { false }
        override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
        override func mouseDown(with event: NSEvent) { start = event.locationInWindow; width = Double(actions?.panel?.frame.width ?? 360) }
        override func mouseDragged(with event: NSEvent) { actions?.setScale((width + Double(event.locationInWindow.x - start.x)) / 360); syncValue() }
        override func resetCursorRects() { addCursorRect(bounds, cursor: .crosshair) }
        func syncValue() { if let actions { setAccessibilityValue(actions.store.widgetScale * 100) } }
        override func accessibilityPerformIncrement() -> Bool { guard let actions else { return false }; actions.setScale(actions.store.widgetScale + 0.05); syncValue(); return true }
        override func accessibilityPerformDecrement() -> Bool { guard let actions else { return false }; actions.setScale(actions.store.widgetScale - 0.05); syncValue(); return true }
    }
    func makeNSView(context: Context) -> Grip { let view = Grip(); view.actions = actions; view.setAccessibilityElement(true); view.setAccessibilityRole(.slider); view.setAccessibilityLabel(tr("Widget size", "Размер виджета")); return view }
    func updateNSView(_ view: Grip, context: Context) { view.actions = actions; view.setAccessibilityValue(actions.store.widgetScale * 100) }
}
struct ProviderLine: View {
    let provider: Provider
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(provider.name.uppercased()).font(.system(size: 10, weight: .bold, design: .monospaced)).tracking(1).foregroundStyle(quiet)
                Spacer()
                Text(provider.status == "ready" ? tr("reported", "получено") : provider.status == "stale" ? tr("stale", "устарело") : tr("unavailable", "нет данных")).font(.system(size: 10)).foregroundStyle(provider.status == "ready" ? quiet : amber)
            }
            if !provider.quotas.isEmpty {
                HStack(spacing: 18) {
                    ForEach(provider.quotas.prefix(2)) { q in
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            Text(q.remainingPercent.map { "\(Int(floor($0)))%" } ?? "—").font(.system(size: 23, weight: .medium, design: .monospaced)).foregroundStyle((q.remainingPercent ?? 100) < 15 ? amber : mint)
                            VStack(alignment: .leading, spacing: 1) { Text(q.label).font(.system(size: 10)); Text(stamp(q.resetsAt, compact: true)).font(.system(size: 9)).foregroundStyle(quiet) }
                        }
                    }
                }
                Text(tr("Limit read: ", "Лимит получен: ") + stamp(provider.quotaObservedAt ?? provider.observedAt, compact: true)).font(.system(size: 11)).foregroundStyle(quiet).help(tr("Independent quota snapshot; refresh to compare with the native client", "Независимый снимок лимита; обновите для сравнения с клиентом"))
                Text(tr("Today · UTC: ", "Сегодня · UTC: ") + todayText(provider)).font(.system(size: 10)).foregroundStyle(quiet)
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
        surface.scaleEffect(store.widgetScale, anchor: .topLeading).frame(width: 360 * store.widgetScale, height: store.baseHeight * store.widgetScale, alignment: .topLeading)
    }
    var surface: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                HStack(spacing: 4) { Circle().fill(store.loading ? amber : mint).frame(width: 6, height: 6); Text("AGENT PULSE").font(.system(size: 11, weight: .semibold)).tracking(1); if store.isFixture { Text("DEMO").font(.system(size: 9)).foregroundStyle(amber) } }.frame(height: 26).overlay(DragHandle()).help(tr("Drag by this title", "Перетащить за заголовок"))
                Spacer()
                ActionButton(symbol: "arrow.clockwise", help: tr("Refresh", "Обновить"), action: store.refresh)
                ActionButton(symbol: "chart.bar.xaxis", help: tr("Analytics", "Аналитика"), action: actions.showAnalysis)
                ActionButton(symbol: "gearshape", help: tr("Settings", "Настройки"), action: actions.showSettings)
                ActionButton(symbol: "minus", help: tr("Collapse to menu bar", "Свернуть в строку меню"), action: actions.collapseToMenu)
            }
            if let snapshot = store.snapshot {
                ForEach(store.visibleProviders) { p in ProviderLine(provider: p); Rectangle().fill(divider).frame(height: 1) }
                if store.visibleProviders.isEmpty { Text(tr("Choose clients in Settings", "Выберите клиентов в настройках")).foregroundStyle(quiet); Spacer() }
                if store.expanded {
                    ForEach(store.visibleProviders) { p in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(p.name).font(.system(size: 12, weight: .semibold))
                            Text(subscriptionText(p.subscription)).font(.system(size: 11)).foregroundStyle(quiet)
                            Text(tr("Today · UTC: ", "Сегодня · UTC: ") + todayText(p)).font(.system(size: 10)).foregroundStyle(quiet)
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
                }.padding(.trailing, 16).font(.system(size: 11)).foregroundStyle(store.error == nil ? quiet : amber)
            } else { Spacer(); Text(store.error ?? tr("Reading client counters…", "Читаю счётчики клиентов…")).font(.system(size: 12)).foregroundStyle(quiet); Spacer() }
        }.padding(.horizontal, 18).padding(.vertical, 10).frame(width: 360, height: store.expanded ? 430 : 270, alignment: .topLeading).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .overlay(alignment: .bottomTrailing) {
            Image(systemName: "arrow.up.left.and.arrow.down.right").font(.system(size: 9)).foregroundStyle(quiet).padding(5)
                .frame(width: 30, height: 30).overlay(ResizeGrip(actions: actions)).help(tr("Drag to resize · 80–100%", "Потяните для изменения размера · 80–100%"))
        }
    }
}
struct AnalysisView: View {
    @ObservedObject var store: PulseStore
    @State var tab = CommandLine.arguments.firstIndex(of: "--tab").flatMap { $0 + 1 < CommandLine.arguments.count ? CommandLine.arguments[$0 + 1] : nil } ?? "overview"
    @State var selectedSession: String?; @State var calls: [JournalCall] = []; @State var evidence: Set<String> = []
    @State var label = ""; @State var variant = "before"; @State var outcome = "unknown"
    @State var before = "before"; @State var after = "after"; @State var message = ""
    func select(_ session: JournalSession, evidenceIds: [String] = []) {
        selectedSession = session.id; label = session.label ?? ""; variant = session.variant ?? "before"; outcome = session.outcome
        evidence = Set(evidenceIds); tab = "sessions"; message = ""
        calls = (store.snapshot?.analytics?.recentCalls ?? []).filter { $0.session == session.id }
        if !store.isFixture {
            store.run(["journal", "--action", "session", "--session", session.id]) { r in
                struct Result: Decodable { var calls: [JournalCall]; var truncated: Bool }
                if case .success(let data) = r, let result = try? JSONDecoder().decode(Result.self, from: data) {
                    calls = result.calls
                    if result.truncated { message = tr("Showing first 500 calls; export for further review", "Первые 500 вызовов; используйте экспорт для продолжения") }
                }
            }
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { Text(tr("Agent activity", "Работа агентов")).font(.system(size: 26, weight: .medium)); Spacer(); Button(tr("Refresh", "Обновить"), action: store.refresh).disabled(store.loading || store.isFixture) }
            Picker("View", selection: $tab) {
                Text(tr("Overview", "Обзор")).tag("overview"); Text(tr("Workflows", "Сценарии")).tag("workflows")
                Text(tr("Sessions", "Сессии")).tag("sessions"); Text(tr("Compare", "Сравнение")).tag("compare")
            }.pickerStyle(.segmented).labelsHidden()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let snapshot = store.snapshot {
                        if tab == "overview" { overview(snapshot) }
                        else if let report = snapshot.analytics {
                            if tab == "workflows" { workflows(report) }
                            else if tab == "sessions" { sessions(report) }
                            else { comparison(report) }
                        } else { Text(tr("No event journal yet. Enable a local observer in Settings.", "Журнал ещё пуст. Включите локальный наблюдатель в настройках.")).foregroundStyle(quiet) }
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
            }
            Text(tr("Local evidence · partial coverage · no model calls or per-tool token estimates", "Локальные данные · частичный охват · без вызовов моделей и оценки токенов каждого инструмента")).font(.system(size: 10)).foregroundStyle(quiet)
        }.padding(24).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .onAppear {
            if CommandLine.arguments.contains("--session-demo"), let first = store.snapshot?.analytics?.sessions.first { select(first) }
        }
    }
    func overview(_ snapshot: Snapshot) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(tr("Quota windows, reported tokens and billing dates remain separate.", "Окна лимитов, переданные токены и даты оплаты учитываются отдельно.")).font(.system(size: 12)).foregroundStyle(quiet)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 16) {
                ForEach(snapshot.providers) { p in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(p.name).font(.system(size: 16, weight: .semibold))
                        Text(tr("Today · UTC: ", "Сегодня · UTC: ") + fullNumber(p.todayTokens)).font(.system(size: 12))
                        if let context = p.contextTokens { Text(tr("Context gauge: ", "Размер контекста: ") + fullNumber(context)).font(.system(size: 11)).foregroundStyle(amber) }
                        Text(subscriptionText(p.subscription)).font(.system(size: 11)).foregroundStyle(quiet)
                        Text(p.tokenSource ?? tr("Source unavailable", "Источник недоступен")).font(.system(size: 10)).foregroundStyle(quiet)
                        Text(p.tokenCoverage ?? "").font(.system(size: 10)).foregroundStyle(quiet)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            Divider()
            Text(tr("Reported tokens · UTC", "Переданные токены · UTC")).font(.system(size: 16, weight: .semibold))
            if snapshot.history.isEmpty { Text(tr("No history reported", "История не получена")).foregroundStyle(quiet) }
            else { Chart(snapshot.history) { item in BarMark(x: .value("Date", item.day, unit: .day), y: .value("Tokens", item.tokens)).foregroundStyle(by: .value("Client", item.provider)).position(by: .value("Client", item.provider)) }.frame(height: 140) }
            if let report = snapshot.analytics {
                Text(tr("Observed work", "Наблюдаемая работа")).font(.system(size: 16, weight: .semibold))
                Text("\(report.calls) " + tr("calls · ", "вызовов · ") + "\(report.findings.count) " + tr("workflow findings", "наблюдений по сценариям")).foregroundStyle(mint)
                coverage(report)
            }
            Text(tr("Missing days are unknown, not zero. Imported counters do not provide a command timeline.", "Пропущенные дни неизвестны, а не равны нулю. Импорт счётчиков не даёт хронологию команд.")).font(.system(size: 11)).foregroundStyle(quiet)
        }
    }
    func coverage(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(report.coverage) { c in
                HStack { Text(c.provider.uppercased()).font(.system(size: 11, weight: .semibold, design: .monospaced)); Spacer(); Text(coverageText(c.state)).foregroundStyle(c.state == "receiving" ? mint : amber) }
                Text("\(c.pairedCalls)/\(c.calls) " + tr("paired calls · ", "пар вызовов · ") + "\(c.rejected) " + tr("rejected events", "отклонённых событий")).font(.system(size: 10)).foregroundStyle(quiet)
            }
            if report.eventLimitReached { Text(tr("Analysis limited to the latest 20,000 events", "Анализ ограничен последними 20 000 событиями")).foregroundStyle(amber) }
        }.font(.system(size: 11))
    }
    func workflows(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            coverage(report)
            Text(tr("Suggestions require review. Repetition alone does not prove waste or a missing skill.", "Предложения требуют проверки. Повтор сам по себе не доказывает лишнюю работу или отсутствие скилла.")).font(.system(size: 12)).foregroundStyle(quiet)
            if report.findings.isEmpty { Text(tr("Not enough paired events yet. Enable an observer and run ordinary tasks.", "Пока недостаточно пар событий. Включите наблюдатель и выполняйте обычные задачи.")).foregroundStyle(quiet) }
            ForEach(report.findings) { finding in
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text(russian ? finding.titleRu : finding.title).font(.system(size: 15, weight: .semibold)); Spacer(); Text(finding.provider.uppercased()).font(.system(size: 10, design: .monospaced)).foregroundStyle(mint) }
                    if !finding.sequence.isEmpty { Text(finding.sequence.map(categoryText).joined(separator: " → ")).font(.system(size: 12, design: .monospaced)).foregroundStyle(mint) }
                    Text("\(finding.occurrences) " + tr("occurrences · ", "повторов · ") + "\(finding.sessions) " + tr("sessions", "сессий")).font(.system(size: 11)).foregroundStyle(quiet)
                    Text(russian ? finding.suggestionRu : finding.suggestion).font(.system(size: 12))
                    Text(finding.inventoryStatus == "inventory_unknown" ? tr("Inventory unknown: no claim that a tool is missing", "Каталог неизвестен: отсутствие инструмента не установлено") : finding.inventoryStatus == "configured_unverified" ? tr("Candidate configured; live availability unverified", "Кандидат настроен; доступность не проверена") : tr("Category match requires manual review", "Совпадение категорий требует ручной проверки")).font(.system(size: 10)).foregroundStyle(amber)
                    if let sid = finding.evidenceSessions?.first ?? report.recentCalls.first(where: { finding.evidenceIds.contains($0.id) })?.session {
                        Button(tr("Inspect evidence →", "Посмотреть примеры →")) {
                            let session = report.sessions.first(where: { $0.id == sid }) ?? JournalSession(id: sid, provider: finding.provider, calls: 0, failed: 0, pending: 0, paired: 0, elapsedMs: nil, startedAt: nil, label: nil, outcome: "unknown", variant: nil)
                            select(session, evidenceIds: finding.evidenceIds)
                        }
                    }

                }.padding(.vertical, 8)
                Divider()
            }
        }
    }
    @ViewBuilder func sessions(_ report: AnalyticsReport) -> some View {
        if selectedSession == nil { sessionList(report) } else { sessionDetail() }
    }
    func sessionList(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 12) {
                Text(tr("Choose a session to inspect observed calls", "Выберите сессию для просмотра вызовов")).font(.system(size: 14, weight: .semibold))
                ForEach(report.sessions) { session in
                    Button { select(session) } label: {
                        HStack { VStack(alignment: .leading, spacing: 4) { Text(session.provider.uppercased() + " · " + String(session.id.prefix(8))).font(.system(size: 13, weight: .semibold, design: .monospaced)); Text(stamp(session.startedAt, compact: true)).font(.system(size: 11)).foregroundStyle(quiet) }; Spacer(); Text("\(session.calls) " + tr("calls · ", "вызовов · ") + "\(session.failed) " + tr("failed", "ошибок")).font(.system(size: 11)) }.padding(.vertical, 5)
                    }.buttonStyle(.plain)
                    Divider()
                }
                if report.sessions.isEmpty { Text(tr("No observed sessions", "Наблюдаемых сессий пока нет")).foregroundStyle(quiet) }
        }
    }
    func sessionDetail() -> some View {
        VStack(alignment: .leading, spacing: 12) {

                Button(tr("← Sessions", "← Сессии")) { selectedSession = nil; evidence = [] }
                Text(String(selectedSession!.prefix(12))).font(.system(size: 17, weight: .medium, design: .monospaced))
                Text(tr("Arguments are intentionally hidden. Safe command shape, outcome and wall time only; overlapping durations are not summed.", "Аргументы скрыты. Только безопасная форма команды, исход и время; длительности параллельных вызовов не складываются.")).font(.system(size: 11)).foregroundStyle(quiet)
                HStack { TextField(tr("Task label (slug)", "Метка задачи (slug)"), text: $label); TextField(tr("Variant", "Вариант"), text: $variant); Picker(tr("Outcome", "Исход"), selection: $outcome) { ForEach(["unknown", "accepted", "failed", "rework"], id: \.self) { Text(outcomeText($0)).tag($0) } }.labelsHidden().frame(width: 160) }
                Button(tr("Save review", "Сохранить оценку")) {
                    guard let sid = selectedSession else { return }
                    if store.isFixture { message = tr("Demo: review not saved", "Демо: оценка не сохраняется"); return }
                    store.run(["journal", "--action", "annotate", "--session", sid, "--label", label, "--variant", variant, "--outcome", outcome]) { r in
                        if case .success = r { message = tr("Saved locally", "Сохранено локально"); store.refresh() }
                        else { message = tr("Use nonsensitive ASCII labels without spaces", "Используйте нечувствительные ASCII-метки без пробелов") }
                    }
                }
                if !message.isEmpty { Text(message).font(.system(size: 11)).foregroundStyle(amber) }
                ForEach(calls) { call in callRow(call); Divider() }
        }
    }
    func callRow(_ call: JournalCall) -> some View {
        let duration = call.durationMs.map { String(format: "%.2f s", $0 / 1000) } ?? "—"
        let incomplete = call.paired ? "" : tr(" · incomplete pair", " · неполная пара")
        let metadata = [stamp(call.startedAt, compact: true), duration, call.durationSource].joined(separator: " · ") + incomplete
        return
                    VStack(alignment: .leading, spacing: 4) {
                        HStack { Text(categoryText(call.category).uppercased()).font(.system(size: 10, weight: .bold)).foregroundStyle(evidence.contains(call.id) ? mint : quiet); Text(call.tool).font(.system(size: 11, design: .monospaced)); Spacer(); Text(outcomeText(call.outcome)).font(.system(size: 11)).foregroundStyle(call.outcome == "failed" ? amber : quiet) }
                        Text(call.template).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                        Text(metadata).font(.system(size: 10)).foregroundStyle(quiet)
                    }.padding(.vertical, 6)
    }
    func comparison(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(tr("Review the same task family before and after a change", "Сравните одну группу задач до и после изменения")).font(.system(size: 16, weight: .semibold))
            Text(tr("Label sessions, variant and acceptance in Sessions. At least 3 observations per variant are needed. Model settings and task difficulty still require your review.", "Укажите метки, вариант и результат в Сессиях. Нужно хотя бы 3 наблюдения на вариант. Настройки моделей и сложность задач проверяете вы.")).font(.system(size: 12)).foregroundStyle(quiet)
            HStack { TextField(tr("Task label", "Метка задачи"), text: $label); TextField(tr("Before", "До"), text: $before); TextField(tr("After", "После"), text: $after) }
            Button(tr("Compare observations", "Сравнить наблюдения")) {
                if store.isFixture { message = tr("Demo comparison: use real reviewed sessions to measure effects.", "Демо: для оценки эффекта используйте реальные проверенные сессии."); return }
                store.run(["journal", "--action", "compare", "--label", label, "--before", before, "--after", after]) { r in
                    if case .success(let data) = r, let obj = try? JSONSerialization.jsonObject(with: data), let formatted = try? JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys]), let text = String(data: formatted, encoding: .utf8) { message = text }
                    else { message = tr("Use valid task and variant labels", "Проверьте метки задачи и вариантов") }
                }
            }
            if !message.isEmpty { Text(message).font(.system(size: 11, design: .monospaced)).textSelection(.enabled) }
            Text(tr("No causal claim, exact per-tool cost or promised subscription saving. Failed and rework results remain visible.", "Без заявления о причинности, точной стоимости инструмента или обещаний экономии подписки. Ошибки и доработки учитываются.")).font(.system(size: 11)).foregroundStyle(amber)
        }
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
    @State var selected: Set<String> = []; @State var patterns = false; @State var tokens = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(tr("Agent Pulse settings", "Настройки Agent Pulse")).font(.system(size: 23, weight: .medium))
                Picker(tr("Language", "Язык"), selection: $store.language) { Text("English").tag("en"); Text("Русский").tag("ru") }.frame(width: 260)
                Toggle(tr("Keep widget above windows", "Держать поверх окон"), isOn: $store.topmost).onChange(of: store.topmost) { _, value in actions.panel?.level = value ? .floating : .normal }
                Text(tr("Widget size", "Размер виджета")).font(.system(size: 16, weight: .semibold))
                HStack { ForEach([0.8, 0.9, 1.0], id: \.self) { value in Button("\(Int(value * 100))%") { actions.setScale(value) } }; Text("\(Int(store.widgetScale * 100))%") }
                Slider(value: Binding(get: { store.widgetScale }, set: { actions.setScale($0) }), in: 0.8...1).frame(width: 300)
                Text(tr("Or drag the lower-right corner. Details and analytics stay available.", "Можно тянуть за нижний правый угол. Детали и аналитика остаются доступны.")).font(.system(size: 11)).foregroundStyle(quiet)
                Picker(tr("Placement", "Размещение"), selection: Binding(get: { store.displayMode }, set: { actions.setDisplayMode($0) })) {
                    Text(tr("Floating widget", "Плавающий виджет")).tag("floating"); Text(tr("Menu bar only", "Только строка меню")).tag("menu")
                }.frame(width: 350)
                Toggle(tr("Compact values in menu bar", "Короткие значения в строке меню"), isOn: $store.menuNumbers)
                Text(tr("Click the menu-bar icon for the widget; right-click for actions. Icon-only saves space beside the camera.", "Нажмите значок сверху для табло; правая кнопка — действия. Режим без цифр экономит место рядом с камерой.")).font(.system(size: 11)).foregroundStyle(quiet)
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
                ForEach(["codex", "glm", "claude"], id: \.self) { id in
                    HStack { Text(id.uppercased()).frame(width: 70, alignment: .leading); Button(tr("Enable", "Включить")) { store.observer(id, enable: true) }; Button(tr("Remove", "Удалить")) { store.observer(id, enable: false) } }
                }
                Divider().overlay(divider)
                Text(tr("Billing dates · manual", "Даты подписок · вручную")).font(.system(size: 16, weight: .semibold))
                ForEach(store.snapshot?.providers ?? []) { p in SubscriptionRow(provider: p, store: store) }
                if let m = store.settingsMessage { Text(m).foregroundStyle(mint) }
                Text(tr("Counters every 5 minutes; Codex limits every minute. Configure bridges/imports as documented in the provider guide. No screen, microphone or Accessibility permission required.", "Счётчики — каждые 5 минут; лимиты Codex — каждую минуту. Мосты и импорт настраиваются по инструкции. Доступ к экрану, микрофону и Accessibility не требуется.")).font(.system(size: 11)).foregroundStyle(quiet)
            }.padding(26)
        }.frame(width: 560, height: 620).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .onAppear { selected = Set((store.snapshot?.providers ?? []).map { $0.id }); patterns = store.snapshot?.localPatterns ?? false; tokens = store.snapshot?.localTokens ?? false }
    }
}

final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var observations = Set<AnyCancellable>(); var popover = NSPopover(); var statusMenu: NSMenu?
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
        statusMenu = menu
        statusItem.button?.target = self; statusItem.button?.action = #selector(statusClicked)
        statusItem.button?.sendAction(on: [.leftMouseUp, .rightMouseUp])
        store.$snapshot.combineLatest(store.$menuNumbers, store.$displayMode).sink { [weak self] _, _, _ in DispatchQueue.main.async { self?.updateStatus() } }.store(in: &observations)
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
        self.panel = panel; resizePanel()
        if store.displayMode != "menu" { panel.orderFrontRegardless() }
        updateStatus()
        handleSnapshotArguments()
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if store.displayMode == "menu" { if !popover.isShown { statusClicked() } }
        else { panel?.orderFrontRegardless() }
        return true
    }
    func updateStatus() {
        guard let button = statusItem?.button else { return }
        let title = store.menuNumbers && store.displayMode == "menu" ? (store.snapshot?.providers.prefix(2).map { p in
            let name = p.id == "codex" ? "C" : p.id == "glm" ? "G" : String(p.name.prefix(2))
            let value = p.quotas.first?.remainingPercent.map { "\(Int(floor($0)))%" } ?? (p.todayTokens.map { shortNumber($0) } ?? "—")
            return name + " " + value
        }.joined(separator: " · ") ?? "") : ""
        button.title = title; button.imagePosition = .imageLeading; button.font = .monospacedDigitSystemFont(ofSize: 11, weight: .medium)
        button.toolTip = tr("Agent Pulse · click for widget, right-click for actions", "Agent Pulse · нажмите для табло, правая кнопка — действия")
    }
    @objc func statusClicked() {
        guard let button = statusItem.button else { return }
        if NSApp.currentEvent?.type == .rightMouseUp { statusMenu?.popUp(positioning: nil, at: NSPoint(x: 0, y: button.bounds.minY), in: button); return }
        if store.displayMode == "menu" {
            if popover.isShown { popover.performClose(nil); return }
            popover.behavior = .transient
            popover.contentViewController = NSHostingController(rootView: WidgetView(store: store, actions: self))
            popover.contentSize = NSSize(width: 360 * store.widgetScale, height: store.baseHeight * store.widgetScale)
            NSApp.activate(ignoringOtherApps: true)
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        } else { togglePanel() }
    }
    func setScale(_ value: Double) { store.widgetScale = min(1, max(0.8, value)); resizePanel() }
    func resizePanel() {
        guard let panel else { return }
        let top = panel.frame.maxY
        panel.setFrame(NSRect(x: panel.frame.minX, y: top - store.baseHeight * store.widgetScale, width: 360 * store.widgetScale, height: store.baseHeight * store.widgetScale), display: true)
        panel.contentView?.layer?.cornerRadius = 14 * store.widgetScale
        if popover.isShown { popover.contentSize = panel.frame.size }
    }
    func setDisplayMode(_ mode: String) {
        store.displayMode = mode == "menu" ? "menu" : "floating"; popover.performClose(nil)
        if store.displayMode == "menu" { panel?.orderOut(nil) } else { panel?.orderFrontRegardless() }
        updateStatus()
    }
    @objc func refresh() { store.refresh() }
    @objc func quit() { NSApp.terminate(nil) }
    @objc func togglePanel() { if panel?.isVisible == true { hidePanel() } else { panel?.orderFrontRegardless() } }
    func hidePanel() { panel?.orderOut(nil); popover.performClose(nil) }
    func collapseToMenu() { setDisplayMode("menu") }
    func toggleExpanded() {
        guard panel != nil else { return }
        store.expanded.toggle(); resizePanel()
    }
    @objc func openAnalysis() { showAnalysis() }
    func showAnalysis() {
        popover.performClose(nil)
        if analysisWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 620), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
            w.title = tr("Agent Pulse · analytics", "Agent Pulse · аналитика"); w.isReleasedWhenClosed = false; w.minSize = NSSize(width: 620, height: 520)
            w.contentView = NSHostingView(rootView: AnalysisView(store: store)); w.center(); analysisWindow = w
        }
        NSApp.activate(ignoringOtherApps: true); analysisWindow?.makeKeyAndOrderFront(nil)
    }
    @objc func openSettings() { showSettings() }
    func showSettings() {
        popover.performClose(nil)
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
        if mode == "menu-popover" { setDisplayMode("menu"); DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.statusClicked() } }
        if mode == "resize-check", store.isFixture {
            let grip = ResizeGrip.Grip(); grip.actions = self
            let down = NSEvent.mouseEvent(with: .leftMouseDown, location: NSPoint(x: 280, y: 10), modifierFlags: [], timestamp: 0, windowNumber: panel?.windowNumber ?? 0, context: nil, eventNumber: 1, clickCount: 1, pressure: 1)!
            let drag = NSEvent.mouseEvent(with: .leftMouseDragged, location: NSPoint(x: 340, y: 10), modifierFlags: [], timestamp: 0.1, windowNumber: panel?.windowNumber ?? 0, context: nil, eventNumber: 2, clickCount: 1, pressure: 1)!
            grip.mouseDown(with: down); grip.mouseDragged(with: drag)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self else { return }
            let w = mode.hasPrefix("analysis") ? self.analysisWindow : mode == "settings" ? self.settingsWindow : self.panel
            let captureView = mode == "menu-popover" ? self.popover.contentViewController?.view : mode == "menu-bar" ? self.statusItem.button : w?.contentView
            if let view = captureView, let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: rep)
                if let data = rep.representation(using: .png, properties: [:]) { try? data.write(to: URL(fileURLWithPath: path)) }
            }
            if let panel = self.panel {
                let popoverBefore = self.popover.isShown
                let before = panel.isVisible
                self.hidePanel(); let hidden = !panel.isVisible
                self.togglePanel(); let restored = panel.isVisible
                let report: [String: Any] = ["view": mode, "panelWidth": panel.frame.width, "panelHeight": panel.frame.height, "floatingLevel": panel.level == .floating, "joinsAllSpaces": panel.collectionBehavior.contains(.canJoinAllSpaces), "fullScreenAuxiliary": panel.collectionBehavior.contains(.fullScreenAuxiliary), "movable": panel.isMovableByWindowBackground, "visibleBefore": before, "hidePassed": hidden, "restorePassed": restored, "statusItem": self.statusItem.button != nil, "fixtureMode": self.store.isFixture, "scale": self.store.widgetScale, "popoverShown": popoverBefore, "displayMode": self.store.displayMode, "menuTitle": self.statusItem.button?.title ?? "", "capturedSize": [w?.contentView?.bounds.width ?? 0, w?.contentView?.bounds.height ?? 0]]
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
