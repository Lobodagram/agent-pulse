import AppKit
import SwiftUI
import Combine
import ServiceManagement

@MainActor final class PulseStore: ObservableObject {
    @Published var snapshot: Snapshot?; @Published var loading = false; @Published var error: String?; @Published var settingsMessage: String?
    @Published var expanded = false; @Published var topmost = true { didSet { savePreference("topmost", topmost) } }; @Published var page = 0
    @Published var benefitExpanded: Set<String> = []
    @Published var language: String = UserDefaults.standard.string(forKey: "language") ?? "en" { didSet { pulseLanguageOverride = language; savePreference("language", language) } }
    @Published var widgetScale: Double = min(1, max(0.8, UserDefaults.standard.double(forKey: "widgetScale") == 0 ? 1 : UserDefaults.standard.double(forKey: "widgetScale"))) { didSet { savePreference("widgetScale", widgetScale) } }
    @Published var displayMode: String = UserDefaults.standard.string(forKey: "displayMode") ?? "floating" { didSet { savePreference("displayMode", displayMode) } }
    @Published var providerKeySaving = false
    @Published var metricMode: String = UserDefaults.standard.string(forKey: "metricMode") == "today" ? "today" : "limits" { didSet { savePreference("metricMode", metricMode) } }
    @Published var menuNumbers: Bool = UserDefaults.standard.object(forKey: "menuNumbers") as? Bool ?? true { didSet { savePreference("menuNumbers", menuNumbers) } }
    @Published var menuFollowActive: Bool = UserDefaults.standard.bool(forKey: "menuFollowActive") { didSet { savePreference("menuFollowActive", menuFollowActive) } }
    let observerHome: String?; let stateOverride: String?; private var applyingSettings = false; private var settingsBytes: Data?; private var pendingPreferences: [String:Any] = [:]; private var writingPreferences = false
    let fixture: String?; private var timer: Timer?; private var limitTimer: Timer?; private var readingLimits = false; private var authTimer: Timer?; private var authMarks: [String: String] = [:]; private var authRevision = 0
    let launchAtLogin: LaunchAtLoginController
    init() {
        let args = CommandLine.arguments
        observerHome = args.firstIndex(of: "--observer-home").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        stateOverride = args.firstIndex(of: "--state").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        fixture = args.firstIndex(of: "--fixture").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        let appPath = Bundle.main.bundleURL.path
        let installed = Bundle.main.bundleIdentifier == "app.agentpulse.desktop" && ["/Applications/Agent Pulse.app", NSHomeDirectory() + "/Applications/Agent Pulse.app"].contains(appPath)
        launchAtLogin = LaunchAtLoginController(service: MacLoginItemService(), preview: fixture != nil || stateOverride != nil, allowed: installed)
        if let i = args.firstIndex(of: "--language"), i + 1 < args.count { language = args[i + 1] }
        if let i = args.firstIndex(of: "--scale"), i + 1 < args.count, let value = Double(args[i + 1]) { widgetScale = min(1, max(0.8, value)) }
        if let i = args.firstIndex(of: "--metric-mode"), i + 1 < args.count { metricMode = args[i + 1] == "today" ? "today" : "limits" }
        if args.contains("--menu-only") { displayMode = "menu" }
        if let fixture {
            do { snapshot = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: URL(fileURLWithPath: fixture))) }
            catch { self.error = tr("Could not load demo", "Не удалось прочитать демо") }
            if args.contains("--benefit-expanded") { benefitExpanded = Set(snapshot?.providers.map(\.id) ?? []) }
        } else {
            loadPreferences()
            authMarks = authenticationMetadata()
            authTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in Task { @MainActor in self?.loadPreferences(); self?.checkAuthenticationChange() } }
            limitTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in Task { @MainActor in self?.refreshLimits() } }
            refresh(); timer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } }
        }
    }
    var stateURL: URL { stateOverride.map { URL(fileURLWithPath: $0) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/AgentPulse") }
    func savePreference(_ key: String, _ value: Any) {
        guard !isFixture, !applyingSettings else { return }
        if stateOverride == nil { UserDefaults.standard.set(value, forKey: key) }
        pendingPreferences[key] = value
        flushPreferences()
    }
    func flushPreferences() {
        guard !writingPreferences, !pendingPreferences.isEmpty, let data = try? JSONSerialization.data(withJSONObject: pendingPreferences) else { return }
        pendingPreferences = [:]; writingPreferences = true
        run(["settings", "--update"], input: data) { [weak self] result in
            guard let self else { return }; self.writingPreferences = false
            if case .failure = result { self.settingsMessage = tr("Could not save local settings", "Не удалось сохранить настройки") }
            self.flushPreferences()
        }
    }
    func loadPreferences() {
        guard !isFixture, !writingPreferences, pendingPreferences.isEmpty else { return }
        let url = stateURL.appendingPathComponent("config.json")
        guard let attributes = try? FileManager.default.attributesOfItem(atPath: url.path), attributes[.type] as? FileAttributeType != .typeSymbolicLink,
              let size = attributes[.size] as? Int, size <= 65536, let data = try? Data(contentsOf: url), data != settingsBytes,
              let values = try? JSONSerialization.jsonObject(with: data) as? [String:Any] else { return }
        settingsBytes = data; applyingSettings = true
        defer { applyingSettings = false }
        if let v = values["language"] as? String, ["en","ru"].contains(v) { language = v }
        if let v = values["widgetScale"] as? Double, v >= 0.8, v <= 1 { widgetScale = v }
        if let v = values["displayMode"] as? String, ["floating","menu","compact","tray"].contains(v) { displayMode = v == "floating" ? "floating" : "menu" }
        if let v = values["metricMode"] as? String, ["limits","today"].contains(v) { metricMode = v }
        if let v = values["topmost"] as? Bool { topmost = v }
        if let v = values["menuNumbers"] as? Bool { menuNumbers = v }
        if let v = values["menuFollowActive"] as? Bool { menuFollowActive = v }
    }
    var baseHeight: Double { (expanded ? 462 : 302) + Double(visibleProviders.filter { benefitExpanded.contains($0.id) }.count) * 62 }
    func toggleBenefit(_ provider: String) {
        if benefitExpanded.contains(provider) { benefitExpanded.remove(provider) } else { benefitExpanded.insert(provider) }
    }
    var isFixture: Bool { fixture != nil }
    var pages: Int { max(1, ((snapshot?.providers.count ?? 0) + 1) / 2) }
    var visibleProviders: [Provider] { Array((snapshot?.providers ?? []).dropFirst(min(page, pages - 1) * 2).prefix(2)) }
    func run(_ arguments: [String], input: Data? = nil, completion: @escaping @MainActor (Result<Data, Error>) -> Void) {
        let resources = Bundle.main.resourceURL!
        let arguments = (stateOverride.map { ["--state", $0] } ?? []) + arguments + (arguments.first == "hooks" ? (observerHome.map { ["--observer-home", $0] } ?? []) : [])
        DispatchQueue.global(qos: .utility).async {
            do {
                let process = Process(); let bundled = resources.appendingPathComponent("pulse-collector")
                if FileManager.default.isExecutableFile(atPath: bundled.path) { process.executableURL = bundled; process.arguments = arguments }
                else { process.executableURL = URL(fileURLWithPath: "/usr/bin/env"); process.arguments = [ProcessInfo.processInfo.environment["AGENT_PULSE_PYTHON"] ?? "python3", resources.appendingPathComponent("collector.py").path] + arguments }
                var env = ProcessInfo.processInfo.environment
                env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin")
                process.environment = env
                let output = Pipe(); process.standardOutput = output; process.standardError = FileHandle.nullDevice
                let stdin = input == nil ? nil : Pipe(); if let stdin { process.standardInput = stdin }
                try process.run(); if let input, let stdin { stdin.fileHandleForWriting.write(input); try? stdin.fileHandleForWriting.close() }; let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
                guard process.terminationStatus == 0 else { throw NSError(domain: "AgentPulse", code: Int(process.terminationStatus)) }
                Task { @MainActor in completion(.success(data)) }
            } catch { Task { @MainActor in completion(.failure(error)) } }
        }
    }
    func saveProviderKey(_ provider: String, _ key: String, region: String = "mainland-cn") {
        guard !isFixture, !providerKeySaving, let body = try? JSONSerialization.data(withJSONObject: ["key":key]) else { return }; providerKeySaving = true
        run(["provider-key", "--provider", provider, "--region", region], input: body) { [weak self] result in
            guard let self else { return }; self.providerKeySaving = false; if case .success(let data) = result, let value = try? JSONSerialization.jsonObject(with: data) as? [String:Any], value["saved"] is Bool { self.authRevision += 1; if let idx = self.snapshot?.providers.firstIndex(where: { $0.id == provider }) { self.snapshot?.providers[idx].quotas = []; self.snapshot?.providers[idx].quotaObservedAt = nil }; self.settingsMessage = tr("Provider connection saved. Refreshing…", "Подключение сохранено. Обновляю…"); self.refresh() } else { self.settingsMessage = tr("Could not save provider connection", "Не удалось сохранить подключение") }
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
                     "kimi": URL(fileURLWithPath: ProcessInfo.processInfo.environment["KIMI_CODE_HOME"] ?? home.appendingPathComponent(".kimi-code").path).appendingPathComponent("config.toml"),
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
