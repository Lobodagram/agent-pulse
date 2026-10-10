import AppKit
import SwiftUI
import Combine
import ServiceManagement

var pulseLanguageOverride: String?
var pulseApplicationVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "development" }
var russian: Bool { (pulseLanguageOverride ?? UserDefaults.standard.string(forKey: "language")) == "ru" }
func tr(_ en: String, _ ru: String) -> String { russian ? ru : en }
struct Quota: Codable, Identifiable {
    var bucket: String; var kind: String; var durationMinutes: Double?; var remainingPercent: Double?; var resetsAt: Double?
    var id: String { bucket + kind + String(durationMinutes ?? 0) }
    var label: String {
        if let m = durationMinutes, m.isFinite, m > 0, m <= 525600 {
            if m == 10080 { return tr("Week", "Неделя") }
            if m == 300 { return tr("5 hours", "5 часов") }
            if m.truncatingRemainder(dividingBy: 1440) == 0 { return "\(Int(m / 1440)) " + tr("days", "дней") }
            if m.truncatingRemainder(dividingBy: 60) == 0 { return "\(Int(m / 60)) " + tr("hours", "часов") }
            return "\(Int(m)) " + tr("minutes", "минут")
        }
        return tr("Window", "Окно")
    }
}
func activeProvider(bundleID: String?) -> String? {
    guard let bundleID else { return nil }
    return ["com.openai.codex": "codex", "com.openai.Codex": "codex", "dev.zcode.app": "glm", "ai.z.ZCode": "glm", "com.zai.zcode": "glm", "com.anthropic.claudefordesktop": "claude"][bundleID]
}
func compactQuotaLine(_ p: Provider) -> String {
    let values = p.quotas.prefix(2).map { q -> String in
        var label = tr("win", "окно")
        if let m = q.durationMinutes, m.isFinite, m > 0, m <= 525600 {
            if m.truncatingRemainder(dividingBy: 1440) == 0 { label = "\(Int(m / 1440))" + tr("d", "д") }
            else if m.truncatingRemainder(dividingBy: 60) == 0 { label = "\(Int(m / 60))" + tr("h", "ч") }
            else { label = "\(Int(m))" + tr("m", "м") }
        }
        let value = q.remainingPercent.flatMap { $0.isFinite && $0 >= 0 && $0 <= 100 ? "\(Int(floor($0)))%" : nil } ?? "—"
        return label + " " + value
    }
    return (p.status == "stale" ? "~" : "") + p.id.uppercased() + " " + (values.isEmpty ? "—" : values.joined(separator: " · "))
}
struct Subscription: Codable { var date: String?; var kind: String; var source: String }
struct LocalTokenProfile: Codable {
    var date: String; var inputTokens: Double?; var outputTokens: Double?; var cachedInputTokens: Double?
    var cacheHitRate: Double?; var counterCoverageRate: Double?
}
func percentText(_ value: Double?) -> String { value.map { String(format: "%.1f%%", $0 * 100) } ?? "—" }
struct Provider: Codable, Identifiable {
    var id: String; var name: String; var status: String; var quotas: [Quota]
    var todayTokens: Double?; var lifetimeTokens: Double?; var periodTokens: Double?; var contextTokens: Double?
    var sessions: Double?; var resetCredits: Double?; var sourceStatus: [String]; var quotaError: String?
    var accountScope: String?; var quotaObservedAt: Double?; var observedAt: Double?; var lastSuccessfulAt: Double?; var tokenSource: String?; var tokenCoverage: String?; var todayTokenCoverage: String?; var todayTokenStatus: String?; var subscription: Subscription
    var localTokenProfile: LocalTokenProfile?
    var benefit: WidgetBenefit? = nil
}
struct WidgetBenefit: Codable {
    var windowDays: Int; var linkedAssets: [String:Int]; var observedInvocations: Int; var declaredAppliedTasks: Int
    var reviewedLinkedTasks: Int; var hasObservations: Bool; var comparison: WidgetComparison?
}
struct WidgetComparison: Codable {
    var label: String; var before: String; var after: String; var metrics: [String: WidgetReduction]
    var groups: [String: WidgetComparisonGroup]
}
struct WidgetReduction: Codable { var reduction: Double?; var reasons: [String] }
struct WidgetComparisonGroup: Codable { var tasks: Int; var accepted: Int }
struct ProviderSpec: Codable, Identifiable { var id: String; var name: String; var mode: String; var support: String }
struct DayUsage: Codable, Identifiable {
    var provider: String; var date: String; var tokens: Double; var coverage: String?
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
    var knownOutcomes: Int?; var unknownOutcomes: Int?; var collectionGaps: Int?
    var lastToolEventAt: Double?
    var id: String { provider }
}
struct WorkflowFinding: Codable, Identifiable {
    var id: String; var provider: String; var kind: String; var title: String; var titleRu: String
    var suggestion: String; var suggestionRu: String; var occurrences: Int; var sessions: Int
    var sequence: [String]; var evidenceSessions: [String]?; var evidenceIds: [String]; var inventoryStatus: String; var confidence: String
    var operations: [String]?; var sequenceBasis: String?
    var models: [String]?; var unknownModelCalls: Int?
    var reviewStatus: String?; var reviewReason: String?
}
struct JournalCall: Codable, Identifiable {
    var id: String; var provider: String; var session: String; var tool: String; var category: String
    var template: String; var outcome: String; var durationMs: Double?; var durationSource: String
    var startedAt: Double?; var endedAt: Double?; var paired: Bool; var source: String; var turn_source: String
    var outcomeSource: String?; var collectionIssue: String?
    var model: String?; var modelSource: String?
}
struct JournalSession: Codable, Identifiable {
    var id: String; var provider: String; var calls: Int; var failed: Int; var pending: Int; var paired: Int
    var elapsedMs: Double?; var startedAt: Double?; var label: String?; var outcome: String; var variant: String?
    var models: [String]? = nil; var modelHistory: ModelHistory? = nil
}
struct ModelHistory: Codable {
    var segments: [ModelSegment]; var truncated: Bool; var knownModelCalls: Int; var unknownModelCalls: Int; var reportedChanges: Int
}
struct ModelSegment: Codable, Identifiable {
    var model: String; var firstObservedAt: Double?; var lastObservedAt: Double?; var calls: Int; var transition: String; var evidenceIds: [String]
    var id: String { evidenceIds.first ?? "unknown" }
}
func modelText(_ model: String?) -> String { model == nil || model == "other" ? tr("Unknown model", "Модель неизвестна") : model! }
func modelTransitionText(_ value: String) -> String {
    let ru = ["first-observed":"первое наблюдение", "unknown-gap":"модель не передана", "after-unknown":"после пропуска", "timing-unverified":"порядок не подтверждён", "overlapping-observations":"параллельные наблюдения", "reported-change":"изменение в наблюдаемых вызовах", "same-reported-model":"та же модель"]
    return russian ? ru[value] ?? value : value.replacingOccurrences(of: "-", with: " ")
}
struct AnalyticsReport: Codable {
    var calls: Int; var inventoryCount: Int; var eventLimitReached: Bool
    var coverage: [EventCoverage]; var findings: [WorkflowFinding]; var sessions: [JournalSession]; var recentCalls: [JournalCall]
    var capabilities: [CapabilityStat]?; var toolUsage: [ToolStat]?
    var findingReviews: [FindingReview]?; var mcpNamespaces: [McpNamespace]?
    var efficiency: EfficiencyReport?
    var checkRuns: CheckRunSummary?; var storageHealth: StorageSummary?
    var quality: OutcomeQuality?
}
struct CheckRunSummary: Codable {
    var runs: Int; var knownResults: Int; var knownResultRate: Double?; var pendingRuns: Int; var conflicts: Int; var finishWithoutStart: Int
    var byOperationVersion: [HelperMetric]?; var operationVersionsTruncated: Bool?
}
struct HelperMetric: Codable, Identifiable {
    var provider: String; var operation: String; var version: String; var runs: Int; var knownResults: Int
    var successes: Int; var failures: Int; var successRate: Double?; var pendingRuns: Int; var staleRuns: Int
    var conflicts: Int; var finishWithoutStart: Int; var timedRuns: Int; var medianElapsedMs: Double?
    var id: String { provider + "." + operation + "." + version }
}
struct StorageSummary: Codable { var integrity: String; var retentionDays: Int; var analysisLimitReached: Bool; var storedEvents: Int }
struct OutcomeQuality: Codable { var outcomeSources: [String: Int]? }
struct EfficiencyReport: Codable { var assets: [AssetMetric]; var totalTasks: Int; var tasksTruncated: Bool }
struct AssetMetric: Codable, Identifiable {
    var provider: String; var assetId: String; var version: String; var kind: String; var findingId: String
    var tasks: Int; var accepted: Int; var reviewed: Int; var usageCompleteTasks: Int; var elapsedTasks: Int?
    var nativeUses: Int; var nativeIdentityUses: Int?; var declaredUses: Int; var observedCalls: Int; var knownResults: Int
    var tokensPerAccepted: Double?; var cacheHitRate: Double?; var medianElapsedMs: Double?; var modelRequests: Double?
    var eligibleTasks: Int?; var eligibilityKnownTasks: Int?; var eligibilityUnknownTasks: Int?; var usedEligibleTasks: Int?; var adoptionKnownTasks: Int?
    var adoptionRate: Double?; var nonUseReasons: [String: Int]?; var lifecycle: String?
    var observedCallsPerAccepted: Double?; var modelRequestsPerAccepted: Double?; var elapsedMsPerAccepted: Double?
    var id: String { provider + "." + assetId + "." + version }
}
struct CapabilityStat: Codable {
    var provider: String; var id: String; var kind: String; var status: String; var evidenceStatus: String
    var loaded: Int; var invoked: Int; var declared: Int; var inventoryFresh: Bool
    var evidenceSources: [String: Int]?
    var identity: String { provider + "." + kind + "." + id }
}
struct FindingReview: Codable, Identifiable {
    var findingId: String; var provider: String; var title: String; var titleRu: String
    var status: String; var reason: String; var recheckState: String; var windowHours: Int; var afterWindowEndsAt: Double
    var lifecycle: String?; var linkedVersions: [LinkedVersion]?
    var id: String { findingId }
}
struct LinkedVersion: Codable, Identifiable { var assetId: String; var version: String; var tasks: Int; var accepted: Int; var declaredUses: Int; var id: String { assetId + "." + version } }
func decisionText(_ value: String) -> String {
    let ru = ["unknown":"неизвестно", "yes":"подходит", "no":"не подходит", "":"применение не оценено", "unavailable":"недоступен", "not-selected":"не выбран", "workflow-mismatch":"сценарий не подходит", "preferred-alternative":"выбран другой способ", "waiting-process":"ожидание процесса", "required-check":"обязательная проверка", "different-task":"другая задача", "false-positive":"ложная находка", "confirmed-pattern":"повтор подтверждён", "not-applicable":"не применимо", "duplicate":"дубликат", "open":"в работе", "actioned":"внедрено", "dismissed":"отклонено", "unspecified":"причина не указана", "reviewed":"проверено", "implemented-unlinked":"внедрено — свяжите версию", "registered-awaiting-use":"версия учтена — ждём применения", "awaiting-acceptance":"применено — ждём приёмки", "accepted-awaiting-comparison":"принято — ждём сравнения"]
    return russian ? ru[value] ?? value : value.isEmpty ? "Application unassessed" : value.replacingOccurrences(of: "-", with: " ")
}
struct McpNamespace: Codable {
    var provider: String; var namespace: String; var calls: Int; var registered: Bool
    var identity: String { provider + "." + namespace }
}
func reviewStateText(_ value: String) -> String {
    let ru = ["awaiting-window":"ожидается окно наблюдения", "not-requested":"перепроверка не запрошена", "insufficient-evidence":"мало подтверждений", "baseline-not-qualifying":"исходное окно не достигло порога", "not-qualifying-in-observed-window":"в новом окне порог не достигнут", "observational-lower":"наблюдаемых повторов меньше", "observational-higher":"наблюдаемых повторов больше", "observational-same":"наблюдаемое число совпадает"]
    return russian ? ru[value] ?? value : value.replacingOccurrences(of: "-", with: " ")
}
struct ToolStat: Codable {
    var provider: String; var tool: String; var calls: Int; var failed: Int; var unknown: Int; var pending: Int
    var identity: String { provider + "." + tool }
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
    return code == "receiving" ? tr("receiving tool events", "получает вызовы") : code == "lifecycle-only" ? tr("lifecycle only", "только события сессии") : code == "stale" ? tr("no recent events", "нет свежих событий") : tr("not observed", "не наблюдается")
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
func modelStamp(_ value: Double?) -> String {
    guard let value else { return "—" }
    let f = DateFormatter(); f.locale = Locale(identifier: russian ? "ru_RU" : "en_US"); f.dateFormat = "d MMM, HH:mm:ss"
    return f.string(from: Date(timeIntervalSince1970: value))
}
func subscriptionText(_ s: Subscription) -> String {
    if s.kind == "none" { return tr("No subscription", "Без подписки") }
    guard let d = s.date else { return tr("Billing date not set", "Дата подписки не указана") }
    return (s.kind == "expiry" ? tr("Expiry: ", "Окончание: ") : tr("Renewal: ", "Продление: ")) + d + tr(" · manual", " · вручную")
}
