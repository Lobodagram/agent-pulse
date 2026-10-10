import AppKit
import SwiftUI
import Combine
import ServiceManagement

func resultSourceText(_ source: String) -> String {
    let names = ["exit-not-reported": tr("Exit code not reported", "Код завершения не передан"), "running-process": tr("Process still running", "Процесс ещё работает"), "structured-exit": tr("Explicit exit code", "Явный код завершения"), "native-failure": tr("Native failure event", "Штатное событие ошибки"), "error-flag": tr("Explicit error flag", "Явный признак ошибки"), "completed-non-shell": tr("Completed non-shell tool", "Завершённый инструмент"), "conflicting-exit": tr("Conflicting exit codes", "Противоречивые коды завершения")]
    return names[source] ?? source
}
func taskComparisonText(_ obj: [String: Any]) -> String {
    let reasons = obj["reasons"] as? [String] ?? []
    let names = ["insufficient-tasks": tr("At least 3 tasks per variant", "Нужно хотя бы 3 задачи на вариант"), "different-cohorts": tr("Different model, project or acceptance criterion", "Разные модели, проекты или критерии приёмки"), "unknown-model-or-selection": tr("Unknown model or incomplete selection", "Неизвестная модель или неполная выборка"), "unreviewed-tasks": tr("Some tasks await review", "Не все задачи проверены"), "quality-not-established": tr("Quality is unverified or decreased", "Качество не подтверждено или снизилось"), "incomplete-usage": tr("Incomplete reported token usage", "Неполные переданные счётчики токенов"), "incomplete-selection": tr("Incomplete task selection", "Неполная выборка задач"), "incomplete-time": tr("Incomplete elapsed intervals", "Неполные интервалы времени"), "incomplete-requests": tr("Model request counters unavailable", "Счётчики запросов модели недоступны"), "zero-baseline": tr("Zero baseline; percentage unavailable", "Нулевая база; процент недоступен")]
    var lines = [tr("Token reduction per accepted result: ", "Снижение токенов на принятый результат: ") + ((obj["tokenReduction"] as? Double).map { String(format: "%.1f%%", $0 * 100) } ?? "—")]
    if let metrics = obj["metrics"] as? [String: [String: Any]] {
        let labels = [("observedCallsPerAccepted", tr("Observed call reduction / accepted result", "Снижение вызовов / принятый результат")), ("elapsedMsPerAccepted", tr("Task interval sum reduction / accepted result", "Снижение суммы интервалов / принятый результат")), ("modelRequestsPerAccepted", tr("Model request reduction / accepted result", "Снижение запросов модели / принятый результат"))]
        for (key, label) in labels { if let metric = metrics[key] {
            lines.append(label + ": " + ((metric["reduction"] as? Double).map { String(format: "%.1f%%", $0 * 100) } ?? "—"))
            if let blocked = metric["reasons"] as? [String], !blocked.isEmpty { lines.append(blocked.map { names[$0] ?? $0 }.joined(separator: " · ")) }
        } }
    }
    for reason in reasons { lines.append("• " + (names[reason] ?? reason)) }
    if let groups = obj["groups"] as? [String: [String: Any]] {
        for variant in groups.keys.sorted() { let g = groups[variant]!
            lines.append(variant + ": \(g["accepted"] ?? 0)/\(g["reviewed"] ?? 0) " + tr("accepted · ", "принято · ") + "\(g["usageCompleteTasks"] ?? 0)/\(g["tasks"] ?? 0) " + tr("with reported usage", "с переданным расходом"))
        }
    }
    lines.append(tr("Observed difference; review task difficulty. Subscription savings are unknown.", "Разница наблюдений; проверьте сложность задач. Экономия подписки неизвестна."))
    return lines.joined(separator: "\n")
}
struct AnalysisView: View {
    @ObservedObject var store: PulseStore
    @State var tab = CommandLine.arguments.firstIndex(of: "--tab").flatMap { $0 + 1 < CommandLine.arguments.count ? CommandLine.arguments[$0 + 1] : nil } ?? "overview"
    @State var selectedSession: String?; @State var calls: [JournalCall] = []; @State var evidence: Set<String> = []
    @State var modelHistory: ModelHistory?
    @State var label = ""; @State var variant = "before"; @State var outcome = "unknown"
    @State var before = "before"; @State var after = "after"; @State var message = ""
    @State var comparisonMessage = ""; @State var comparisonLabel = ""
    @State var widgetPinBusy = false
    @State var sessionCursors: [String?] = [nil]; @State var sessionPage = 0; @State var nextCursor: String?
    @State var sessionTotal = 0; @State var pageOffset = 0; @State var pageLoading = false; @State var pageRequest = UUID()
    @State var showUnobservedCapabilities = false
    @State var reviewBusy = false; @State var reviewMessage = ""
    @State var assetName = ""; @State var assetVersion = "v1"; @State var assetKind = "skill"; @State var assetProvider = "codex"; @State var assetFinding = ""
    @State var chosenAsset = ""; @State var taskCriterion = "quality-v1"; @State var taskApplied = false
    @State var taskEligibility = "unknown"; @State var taskNonUseReason = ""; @State var showDismissedFindings = false
    @State var taskFirst = 0; @State var taskLast = 0; @State var compareTasks = true
    @State var compareProvider = "codex"
    @State var registerExpanded = CommandLine.arguments.contains("--fixture") && CommandLine.arguments.contains("--efficiency-demo")
    @State var taskExpanded = CommandLine.arguments.contains("--fixture") && CommandLine.arguments.contains("--efficiency-demo")
    @State var helperMetricsExpanded = CommandLine.arguments.contains("--fixture") && CommandLine.arguments.contains("--helper-metrics-demo")
    var assetMetrics: [AssetMetric] { store.snapshot?.analytics?.efficiency?.assets ?? [] }
    func saveMetadata(_ action: String, _ metadata: [String: Any]) {
        guard !reviewBusy, !store.isFixture, let data = try? JSONSerialization.data(withJSONObject: metadata), let text = String(data: data, encoding: .utf8) else { return }
        reviewBusy = true; reviewMessage = ""; message = ""
        store.run(["journal", "--action", action, "--metadata", text]) { result in
            reviewBusy = false
            if case .success = result { message = tr("Saved locally", "Сохранено локально"); reviewMessage = message; store.refresh() }
            else { message = tr("Not saved: check public labels, version and non-overlapping task boundaries.", "Не сохранено: проверьте метки, версию и границы задачи без пересечений."); reviewMessage = message }
        }
    }
    func saveTask() {
        guard taskFirst >= 0, taskLast >= taskFirst, taskLast < calls.count else { return }
        let selected = Array(calls[taskFirst...taskLast]); guard let first = selected.first else { return }
        var spec: [String: Any] = ["provider": first.provider, "taskId": first.id + ":" + selected.last!.id, "label": label, "variant": variant, "criterion": taskCriterion, "outcome": outcome, "callIds": selected.map(\.id)]
        if let asset = assetMetrics.first(where: { $0.id == chosenAsset }) { spec["assetId"] = asset.assetId; spec["version"] = asset.version; spec["applied"] = taskApplied; spec["eligibility"] = taskEligibility; spec["nonUseReason"] = taskApplied ? "" : taskNonUseReason }
        saveMetadata("task", spec)
    }
    func select(_ session: JournalSession, evidenceIds: [String] = []) {
        selectedSession = session.id; label = session.label ?? ""; variant = session.variant ?? "before"; outcome = session.outcome
        taskFirst = 0; taskLast = max(0, session.calls - 1); chosenAsset = ""; taskApplied = false
        taskEligibility = "unknown"; taskNonUseReason = ""
        evidence = Set(evidenceIds); tab = "sessions"; message = ""
        calls = (store.snapshot?.analytics?.recentCalls ?? []).filter { $0.session == session.id }
        taskLast = max(0, calls.count - 1)
        modelHistory = session.modelHistory
        sessionCursors = [nil]; sessionPage = 0; nextCursor = nil; pageOffset = 0; sessionTotal = session.calls
        if !store.isFixture {
            loadSessionPage(session.id, cursor: nil)
        }
    }
    func loadSessionPage(_ sid: String, cursor: String?, index: Int = 0) {
        let request = UUID(); pageRequest = request; pageLoading = true; message = ""
        var arguments = ["journal", "--action", "session", "--session", sid, "--limit", "100"]
        if let cursor { arguments += ["--cursor", cursor] }
        store.run(arguments) { result in
            guard selectedSession == sid, pageRequest == request else { return }
            pageLoading = false
            struct Page: Decodable { var calls: [JournalCall]; var cursor: String; var nextCursor: String?; var pageOffset: Int; var callCount: Int; var modelHistory: ModelHistory?; var eventLimitReached: Bool }
            if case .success(let data) = result, let value = try? JSONDecoder().decode(Page.self, from: data) {
                calls = value.calls; nextCursor = value.nextCursor; pageOffset = value.pageOffset; sessionTotal = value.callCount; modelHistory = value.modelHistory
                taskFirst = 0; taskLast = max(0, calls.count - 1)
                sessionPage = index; sessionCursors[index] = value.cursor
                if value.eventLimitReached { message = tr("Journal event limit reached; this snapshot is partial.", "Достигнут лимит событий журнала; снимок частичный.") }
            } else { message = tr("Page unavailable. Reopen the session for a fresh snapshot.", "Страница недоступна. Откройте сессию заново для свежего снимка.") }
        }
    }
    func markFinding(_ id: String, status: String, reason: String = "unspecified") {
        guard !store.isFixture, !reviewBusy else { return }
        reviewBusy = true; reviewMessage = ""
        store.run(["journal", "--action", "review", "--finding", id, "--status", status, "--reason", reason]) { result in
            guard case .success = result else { reviewBusy = false; reviewMessage = tr("Decision was not saved", "Решение не сохранено"); return }
            store.run(["journal"]) { result in
                reviewBusy = false
                if case .success(let data) = result, let report = try? JSONDecoder().decode(AnalyticsReport.self, from: data) {
                    store.snapshot?.analytics = report
                    reviewMessage = tr("Saved locally. Recheck uses a 24-hour observation window.", "Сохранено локально. Перепроверка использует окно 24 часа.")
                } else { reviewMessage = tr("Saved; refresh the report", "Сохранено; обновите отчёт") }
            }
        }
    }
    func exportReview() {
        guard !store.isFixture else { return }
        let panel = NSSavePanel(); panel.nameFieldStringValue = "agent-pulse-review.md"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        store.run(["journal", "--action", "export", "--format", "markdown", "--language", russian ? "ru" : "en", "--file", url.path]) { result in
            reviewMessage = (try? result.get()) == nil ? tr("Export failed", "Экспорт не выполнен") : tr("Local Markdown report saved", "Локальный Markdown-отчёт сохранён")
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { PulseBrandMark(size: 32); Text(tr("Agent activity", "Работа агентов")).font(.system(size: 26, weight: .medium)); if store.isFixture { Text("DEMO").font(.system(size: 10)).foregroundStyle(amber) }; Spacer(); Button(tr("Refresh", "Обновить"), action: store.refresh).disabled(store.loading || store.isFixture) }
            HStack { Button(tr("Export Markdown", "Экспорт Markdown"), action: exportReview).disabled(store.isFixture); Text(reviewMessage).font(.system(size: 11)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true) }
            Picker("View", selection: $tab) {
                Text(tr("Overview", "Обзор")).tag("overview"); Text(tr("Workflows", "Сценарии")).tag("workflows")
                Text(tr("Sessions", "Сессии")).tag("sessions"); Text(tr("Compare", "Сравнение")).tag("compare")
                Text(tr("Capabilities", "Навыки")).tag("capabilities")
                Text(tr("Tokens", "Токены")).tag("tokens")
            }.pickerStyle(.segmented).labelsHidden()
            ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let snapshot = store.snapshot {
                        if tab == "overview" { overview(snapshot) }
                        else if tab == "tokens" { TokenHistoryView(snapshot: snapshot) }
                        else if let report = snapshot.analytics {
                            if tab == "workflows" { workflows(report) }
                            else if tab == "sessions" { sessions(report) }
                            else if tab == "capabilities" { capabilities(report) }
                            else { comparison(report) }
                        } else { Text(tr("No event journal yet. Enable a local observer in Settings.", "Журнал ещё пуст. Включите локальный наблюдатель в настройках.")).foregroundStyle(quiet) }
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
            }
            .onAppear {
                if store.isFixture && CommandLine.arguments.contains("--collection-demo") {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                        if tab == "overview" { proxy.scrollTo("collection-health", anchor: .top) }
                        if tab == "compare" {
                            comparisonMessage = taskComparisonText(["reasons": ["incomplete-usage"], "metrics": ["observedCallsPerAccepted": ["reduction": 0.5, "reasons": []], "elapsedMsPerAccepted": ["reduction": 0.2, "reasons": []], "modelRequestsPerAccepted": ["reasons": ["incomplete-requests"]]], "groups": ["before": ["accepted": 3, "reviewed": 3, "tasks": 3, "usageCompleteTasks": 0], "after": ["accepted": 3, "reviewed": 3, "tasks": 3, "usageCompleteTasks": 0]]])
                        }
                    }
                }
                if store.isFixture && CommandLine.arguments.contains("--efficiency-demo") {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                        if tab == "sessions" { proxy.scrollTo("task-review", anchor: .top) }
                        if tab == "capabilities" { proxy.scrollTo("register-version", anchor: .top) }
                        if tab == "workflows" { proxy.scrollTo("finding-reviews", anchor: .top) }
                    }
                }
                if store.isFixture && CommandLine.arguments.contains("--helper-metrics-demo") {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { proxy.scrollTo("helper-metrics", anchor: .top) }
                }
            }
            }
            Text(tr("Local evidence · partial coverage · no model calls or per-tool token estimates", "Локальные данные · частичный охват · без вызовов моделей и оценки токенов каждого инструмента")).font(.system(size: 10)).foregroundStyle(quiet)
        }.padding(24).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .onChange(of: tab) { _, _ in message = ""; reviewMessage = "" }
        .onAppear {
            let args = CommandLine.arguments
            if store.isFixture, let i = args.firstIndex(of: "--analysis-tab"), i+1 < args.count, ["overview", "workflows", "sessions", "compare", "capabilities", "tokens"].contains(args[i+1]) { tab = args[i+1] }
            if CommandLine.arguments.contains("--session-demo"), let first = store.snapshot?.analytics?.sessions.first { select(first) }
            if store.isFixture, CommandLine.arguments.contains("--task-assessment-demo"), let first = assetMetrics.first, let session = store.snapshot?.analytics?.sessions.first(where: { $0.provider == first.provider }) {
                select(session)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { chosenAsset = first.id }
            }
            if store.isFixture, CommandLine.arguments.contains("--model-demo"), let first = store.snapshot?.analytics?.sessions.first(where: { ($0.modelHistory?.reportedChanges ?? 0) > 0 }) { select(first) }
        }
    }
    func overview(_ snapshot: Snapshot) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(tr("Quota windows, reported tokens and billing dates remain separate.", "Окна лимитов, переданные токены и даты оплаты учитываются отдельно.")).font(.system(size: 12)).foregroundStyle(quiet)
            LazyVGrid(columns: [GridItem(.flexible(), alignment: .topLeading), GridItem(.flexible(), alignment: .topLeading)], alignment: .leading, spacing: 16) {
                ForEach(snapshot.providers) { p in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(p.name).font(.system(size: 16, weight: .semibold))
                        Text(tr("Today · UTC: ", "Сегодня · UTC: ") + fullNumber(p.todayTokens)).font(.system(size: 12))
                        if let context = p.contextTokens { Text(tr("Context gauge: ", "Размер контекста: ") + fullNumber(context)).font(.system(size: 11)).foregroundStyle(amber) }
                        Text(subscriptionText(p.subscription)).font(.system(size: 11)).foregroundStyle(quiet)
                        Text(p.tokenSource ?? tr("Source unavailable", "Источник недоступен")).font(.system(size: 10)).foregroundStyle(quiet)
                        Text((p.todayTokenCoverage == "partial-local" ? tr("Today: partial local counters", "Сегодня: частичные локальные счётчики") : nil) ?? p.tokenCoverage ?? "").font(.system(size: 10)).foregroundStyle(quiet)
                        if let profile = p.localTokenProfile {
                            Text(tr("Local device · UTC ", "На этом устройстве · UTC ") + profile.date).font(.system(size: 10)).foregroundStyle(quiet)
                            Text(tr("Input / output: ", "Вход / выход: ") + fullNumber(profile.inputTokens) + " / " + fullNumber(profile.outputTokens)).font(.system(size: 11))
                            Text(tr("Cached input: ", "Вход из кэша: ") + fullNumber(profile.cachedInputTokens) + " · " + percentText(profile.cacheHitRate)).font(.system(size: 11)).foregroundStyle(mint)
                            Text(tr("Breakdown coverage: ", "Охват детализации: ") + percentText(profile.counterCoverageRate) + tr(" of observed tokens · partial", " наблюдаемых токенов · частично")).font(.system(size: 10)).foregroundStyle(quiet)
                            Text(tr("Cache share does not measure subscription or skill savings.", "Доля кэша не измеряет экономию подписки или пользу навыка.")).font(.system(size: 10)).foregroundStyle(quiet)
                        }
                        if p.sourceStatus.contains("local_tokens_backlog_skipped") {
                            Text(tr("Local backlog skipped: recent counters only; missing history is not reconstructed.", "Локальное отставание пропущено: учтены свежие счётчики; пропущенная история не восстановлена.")).font(.system(size: 10)).foregroundStyle(amber)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            Divider()
            TokenHistoryView(snapshot: snapshot)
            if let report = snapshot.analytics {
                Text(tr("Observed work", "Наблюдаемая работа")).font(.system(size: 16, weight: .semibold))
                Text("\(report.calls) " + tr("calls · ", "вызовов · ") + "\(report.findings.count) " + tr("workflow findings", "наблюдений по сценариям")).foregroundStyle(mint)
                coverage(report).id("collection-health")
            }
            Text(tr("Missing days are unknown, not zero. Imported counters do not provide a command timeline.", "Пропущенные дни неизвестны, а не равны нулю. Импорт счётчиков не даёт хронологию команд.")).font(.system(size: 11)).foregroundStyle(quiet)
        }
    }
    func coverage(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(report.coverage) { c in
                HStack { Text(c.provider.uppercased()).font(.system(size: 11, weight: .semibold, design: .monospaced)); Spacer(); Text(coverageText(c.state)).foregroundStyle(c.state == "receiving" ? mint : amber) }
                Text("\(c.pairedCalls)/\(c.calls) " + tr("paired calls · ", "пар вызовов · ") + "\(c.rejected) " + tr("rejected events", "отклонённых событий")).font(.system(size: 10)).foregroundStyle(quiet)
                if let known = c.knownOutcomes {
                    Text("\(known) " + tr("known results · ", "известных результатов · ") + "\(c.unknownOutcomes ?? 0) " + tr("unknown · ", "неизвестных · ") + "\(c.collectionGaps ?? 0) " + tr("collection gaps", "пропусков сбора")).font(.system(size: 10)).foregroundStyle(quiet)
                }
                if let at = c.lastToolEventAt { Text(tr("Last received call: ", "Последний полученный вызов: ") + stamp(at, compact: true)).font(.system(size: 10)).foregroundStyle(quiet) }
            }
            if let checks = report.checkRuns {
                Text(tr("Helper results: ", "Результаты помощников: ") + "\(checks.knownResults)/\(checks.runs) · " + percentText(checks.knownResultRate)).font(.system(size: 11))
                Text("\(checks.pendingRuns) " + tr("pending · ", "без завершения · ") + "\(checks.conflicts) " + tr("conflicts · ", "противоречий · ") + "\(checks.finishWithoutStart) " + tr("missing starts", "пропусков начала")).font(.system(size: 10)).foregroundStyle(quiet)
                if let operations = checks.byOperationVersion, !operations.isEmpty {
                    DisclosureGroup(tr("Direct helper runs by version", "Прямые запуски помощников по версиям"), isExpanded: $helperMetricsExpanded) {
                        ForEach(operations) { row in HelperMetricView(row: row) }
                        if checks.operationVersionsTruncated == true { Text(tr("Latest 50 groups shown; totals include all retained runs", "Показаны последние 50 групп; итоги включают все сохранённые запуски")).font(.system(size: 10)).foregroundStyle(amber) }
                    }.id("helper-metrics")
                }
            }
            if report.checkRuns != nil { Text(tr("Helper evidence is separate from native outcomes and human acceptance", "Квитанции отдельно от штатных исходов и приёмки человеком")).font(.system(size: 10)).foregroundStyle(quiet) }
            if let health = report.storageHealth {
                Text(tr("Journal integrity: ", "Целостность журнала: ") + (health.integrity == "ok" ? tr("quick check passed", "быстрая проверка пройдена") : tr("check failed", "проверка не пройдена")) + " · \(health.retentionDays) " + tr("days retained", "дней хранения")).font(.system(size: 10)).foregroundStyle(quiet)
                if health.analysisLimitReached { Text(tr("Analysis selection is truncated", "Выборка анализа усечена")).font(.system(size: 10)).foregroundStyle(amber) }
            }
            Text(tr("Silence may mean an idle client. Paired calls count only received events; total coverage is unknown.", "Тишина может означать простой клиента. Пары считаются среди полученных событий; полный охват неизвестен.")).font(.system(size: 10)).foregroundStyle(quiet)
            if let sources = report.quality?.outcomeSources {
                DisclosureGroup(tr("Result evidence", "Основания результатов")) {
                    ForEach(sources.keys.sorted(), id: \.self) { source in
                        Text("\(sources[source] ?? 0) · " + resultSourceText(source)).font(.system(size: 10)).foregroundStyle(quiet)
                    }
                }
            }
            if report.eventLimitReached { Text(tr("Analysis limited to the latest 20,000 events", "Анализ ограничен последними 20 000 событиями")).foregroundStyle(amber) }
        }.font(.system(size: 11))
    }
    func capabilities(_ report: AnalyticsReport) -> some View {
        let all = report.capabilities ?? []
        let observed = all.filter { $0.loaded + $0.invoked + $0.declared > 0 }
        let visible = showUnobservedCapabilities ? all.sorted { a, b in
            let x = a.loaded + a.invoked + a.declared; let y = b.loaded + b.invoked + b.declared
            return x == y ? a.identity < b.identity : x > y
        } : observed
        return VStack(alignment: .leading, spacing: 12) {
            efficiencyCards(report)
            DisclosureGroup(tr("Register a version", "Добавить версию"), isExpanded: $registerExpanded) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Picker(tr("Client", "Клиент"), selection: $assetProvider) { ForEach(Array(Set(report.coverage.map(\.provider) + ["codex", "glm"])).sorted(), id: \.self) { Text($0.uppercased()).tag($0) } }
                        Picker(tr("Type", "Тип"), selection: $assetKind) { ForEach(["skill", "mcp", "tool"], id: \.self) { Text($0).tag($0) } }
                    }
                    HStack { TextField(tr("Public name", "Публичная метка"), text: $assetName); TextField(tr("Version", "Версия"), text: $assetVersion) }
                    Picker(tr("Finding", "Находка"), selection: $assetFinding) {
                        Text(tr("Without a finding", "Без находки")).tag("")
                        ForEach(report.findings.filter { $0.provider == assetProvider }) { Text((russian ? $0.titleRu : $0.title) + " · \($0.occurrences)").tag($0.id) }
                    }
                    Text(tr("Use nonsensitive ASCII labels. A registered version is not proof of use.", "Используйте нечувствительные ASCII-метки. Регистрация версии не подтверждает применение.")).font(.system(size: 11)).foregroundStyle(quiet)
                    Button(tr("Save version", "Сохранить версию")) {
                        var spec: [String: Any] = ["provider": assetProvider, "assetId": assetName, "version": assetVersion, "kind": assetKind]
                        if !assetFinding.isEmpty { spec["findingId"] = assetFinding }
                        saveMetadata("asset", spec)
                    }.disabled(store.isFixture || reviewBusy || assetName.isEmpty || assetVersion.isEmpty)
                }.padding(.top, 8)
            }.id("register-version").onChange(of: assetProvider) { _, _ in assetFinding = "" }
            VStack(alignment: .leading, spacing: 8) {
            Text(tr("Read ≠ invoked ≠ manually declared. No observed use does not prove non-use.", "Чтение ≠ вызов ≠ ручная отметка. Отсутствие наблюдения не доказывает неиспользование.")).font(.system(size: 12)).foregroundStyle(quiet)
            Text("\(all.count) " + tr("catalog entries · ", "записей каталога · ") + "\(observed.count) " + tr("with evidence · ", "с подтверждением · ") + "\((report.toolUsage ?? []).count) " + tr("observed tools", "наблюдаемых инструментов")).font(.system(size: 12)).foregroundStyle(mint)
            Text(tr("Literal cat/sed/head/tail reads match registered paths only. Reading does not establish application. MCP namespaces are not proof of a plugin or live server.", "Буквальные cat/sed/head/tail учитываются только по зарегистрированным путям. Чтение не доказывает применение. Пространство MCP не подтверждает плагин или доступность сервера.")).font(.system(size: 11)).foregroundStyle(quiet)
            }
            Text(tr("Observed tools", "Наблюдаемые инструменты")).font(.system(size: 16, weight: .semibold))
            if (report.toolUsage ?? []).isEmpty { Text(tr("No tool calls received in this view.", "В этом разделе пока нет полученных вызовов инструментов.")).foregroundStyle(quiet) }
            ForEach(report.toolUsage ?? [], id: \.identity) { row in
                VStack(alignment: .leading, spacing: 4) {
                    Text(row.provider.uppercased() + " · " + row.tool).font(.system(size: 12, design: .monospaced)).fixedSize(horizontal: false, vertical: true)
                    Text("\(row.calls) " + tr("calls · ", "вызовов · ") + "\(row.failed) " + tr("failed · ", "ошибок · ") + "\(row.unknown) " + tr("unknown · ", "неизвестных · ") + "\(row.pending) " + tr("pending", "незавершённых")).font(.system(size: 11)).foregroundStyle(quiet)
                }
            }
            ForEach(report.mcpNamespaces ?? [], id: \.identity) { row in namespaceCard(row) }
            Text(tr("Reviewed skills and MCP", "Учтённые скиллы и MCP")).font(.system(size: 16, weight: .semibold))
            if all.isEmpty { Text(tr("Scan or import a reviewed inventory first.", "Сначала отсканируйте или импортируйте проверенный каталог.")).foregroundStyle(quiet) }
            else { Toggle(tr("Show catalog entries without observed use", "Показать записи каталога без подтверждённого применения"), isOn: $showUnobservedCapabilities).font(.system(size: 12)) }
            if !all.isEmpty && visible.isEmpty { Text(tr("No registered use confirmed. This does not mean no skills were used.", "Применение из каталога не подтверждено. Это не означает, что скиллы не использовались.")).foregroundStyle(quiet) }
            ForEach(visible, id: \.identity) { row in capabilityCard(row); Divider() }

        }
    }
    func namespaceCard(_ row: McpNamespace) -> some View {
        let suffix = row.registered ? "" : tr(" · not registered", " · вне каталога")
        let label = "\(row.provider.uppercased()) · MCP \(row.namespace) · \(row.calls) " + tr("calls", "вызовов") + suffix
        return Text(label).font(.system(size: 11)).foregroundStyle(quiet)
    }
    func efficiencyCards(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(tr("Useful results", "Польза инструментов")).font(.system(size: 17, weight: .semibold))
            Text(tr("Per client and version · reviewed tasks · tokens include selected failed attempts. Quotas stay separate.", "По клиентам и версиям · проверенные задачи · токены включают выбранные неудачные попытки. Лимиты отдельно.")).font(.system(size: 11)).foregroundStyle(quiet)
            if (report.efficiency?.assets ?? []).isEmpty { Text(tr("Register a version, then review a task in Sessions. Token metrics require sufficient reported data.", "Добавьте версию и оцените задачу в Сессиях. Для показателей токенов нужны достаточные переданные данные.")).font(.system(size: 12)).foregroundStyle(quiet) }
            ForEach(report.efficiency?.assets ?? []) { row in
                efficiencyCard(row)
                Divider()
            }
        }
    }
    func efficiencyCard(_ row: AssetMetric) -> some View {
        let eligible = row.eligibleTasks.map { String($0) } ?? "—"
        let adoption = tr("Applied / eligible: ", "Применено / подходит: ") + "\(row.usedEligibleTasks ?? 0)/" + eligible + " · " + percentText(row.adoptionRate) + tr(" · selected tasks only", " · только выбранные задачи")
        let coverage = tr("Eligibility reviewed: ", "Применимость оценена: ") + "\(row.eligibilityKnownTasks ?? 0)/\(row.tasks) · " + tr("application known: ", "применение известно: ") + "\(row.adoptionKnownTasks ?? 0)/" + eligible
        return
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text(row.assetId + " · " + row.version).font(.system(size: 14, weight: .semibold)); Spacer(); Text(row.provider.uppercased()).font(.system(size: 10, design: .monospaced)).foregroundStyle(mint) }
                    Text(decisionText(row.lifecycle ?? "unknown")).font(.system(size: 11)).foregroundStyle(mint)
                    Text(adoption).font(.system(size: 11))
                    Text(coverage).font(.system(size: 10)).foregroundStyle(quiet)
                    if let reasons = row.nonUseReasons, !reasons.isEmpty { Text(reasons.keys.sorted().map { decisionText($0) + ": \(reasons[$0]!)" }.joined(separator: " · ")).font(.system(size: 10)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true) }
                    Text("\(row.accepted)/\(row.reviewed) " + tr("accepted · ", "принято · ") + "\(row.tasks) " + tr("tasks · ", "задач · ") + "\(row.usageCompleteTasks)/\(row.tasks) " + tr("with complete reported usage", "с полным переданным расходом")).font(.system(size: 11)).foregroundStyle(quiet)
                    HStack(alignment: .top, spacing: 24) {
                        metric(tr("Tokens / accepted", "Токены / результат"), row.tokensPerAccepted.map { String(format: "%.0f", $0) } ?? "—")
                        metric(tr("Input from cache", "Вход из кэша"), row.cacheHitRate.map { String(format: "%.1f%%", $0 * 100) } ?? "—")
                        metric(tr("Median wall time", "Медиана времени"), row.medianElapsedMs.map { String(format: "%.1f", $0 / 1000) + tr(" s", " с") } ?? "—")
                    }
                    Text("\(row.nativeIdentityUses ?? 0) " + tr("name invocations · ", "вызовов имени · ") + "\(row.declaredUses) " + tr("version attestations · ", "отметок версии · ") + "\(row.knownResults)/\(row.observedCalls) " + tr("known tool results", "известных исходов")).font(.system(size: 10)).foregroundStyle(quiet)
                    Text(tr("Reported model requests: ", "Передано вызовов модели: ") + (row.modelRequests.map { String(format: "%.0f", $0) } ?? "—") + " · \(row.elapsedTasks ?? 0)/\(row.tasks) " + tr("with wall time", "со временем")).font(.system(size: 10)).foregroundStyle(quiet)
                    Text(tr("Calls / accepted: ", "Вызовы / результат: ") + (row.observedCallsPerAccepted.map { String(format: "%.1f", $0) } ?? "—") + tr(" · model requests / accepted: ", " · вызовы модели / результат: ") + (row.modelRequestsPerAccepted.map { String(format: "%.1f", $0) } ?? "—")).font(.system(size: 10)).foregroundStyle(quiet)
                    Text(tr("— means insufficient data; observed use does not establish savings.", "— означает недостаток данных; применение не доказывает экономию.")).font(.system(size: 10)).foregroundStyle(amber)
                }.padding(.vertical, 8)
    }
    func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) { Text(value).font(.system(size: 20, weight: .medium, design: .monospaced)); Text(title).font(.system(size: 10)).foregroundStyle(quiet) }.frame(maxWidth: .infinity, alignment: .leading)
    }
    func capabilityCard(_ row: CapabilityStat) -> some View {
                VStack(alignment: .leading, spacing: 4) {
                    Text(row.provider.uppercased() + " · " + row.kind + " · " + row.id).font(.system(size: 12, design: .monospaced)).fixedSize(horizontal: false, vertical: true)
                    if row.loaded + row.invoked + row.declared == 0 { Text(tr("No confirmed events", "Нет подтверждённых событий")).font(.system(size: 11)).foregroundStyle(quiet) }
                    else { Text("\(row.loaded) " + tr("loaded · ", "чтений · ") + "\(row.invoked) " + tr("invoked · ", "вызовов · ") + "\(row.declared) " + tr("declared", "отметок")).font(.system(size: 11)).foregroundStyle(mint) }
                    if let sources = row.evidenceSources, let count = sources["shell-literal"] { Text("\(count) " + tr("literal shell reads", "буквальных чтений shell")).font(.system(size: 10)).foregroundStyle(quiet) }
                    Text(row.status + (row.inventoryFresh ? "" : tr(" · inventory needs refresh", " · обновите каталог"))).font(.system(size: 10)).foregroundStyle(quiet)
                }.padding(.vertical, 4)
    }
    func workflows(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            coverage(report)
            Text(tr("Suggestions require review. Repetition alone does not prove waste or a missing skill.", "Предложения требуют проверки. Повтор сам по себе не доказывает лишнюю работу или отсутствие скилла.")).font(.system(size: 12)).foregroundStyle(quiet)
            if report.findings.isEmpty {
                Text(report.calls == 0 ? tr("No calls received. Configure an observer in Settings and check native trust.", "Вызовы не получены. Настройте наблюдатель в Настройках и проверьте доверие клиента.") : tr("Calls are recorded; no repeat candidate meets the thresholds yet. Workflows need matching sequences in at least 3 turns. Other findings have separate thresholds.", "Вызовы записываются; ни один кандидат пока не достиг порогов. Для сценария нужны совпадающие цепочки минимум в 3 ходах. У других находок свои пороги.")).foregroundStyle(quiet)
            }
            if report.findings.contains(where: { $0.reviewStatus == "dismissed" }) { Toggle(tr("Show dismissed findings", "Показать отклонённые находки"), isOn: $showDismissedFindings).font(.system(size: 11)) }
            ForEach(report.findings.filter { showDismissedFindings || $0.reviewStatus != "dismissed" }) { finding in
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text(russian ? finding.titleRu : finding.title).font(.system(size: 15, weight: .semibold)); Spacer(); Text(finding.provider.uppercased()).font(.system(size: 10, design: .monospaced)).foregroundStyle(mint) }
                    if !finding.sequence.isEmpty { Text(finding.sequence.map(categoryText).joined(separator: " → ")).font(.system(size: 12, design: .monospaced)).foregroundStyle(mint) }
                    if let operations = finding.operations { Text(operations.joined(separator: " → ")).font(.system(size: 10, design: .monospaced)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true) }
                    Text("\(finding.occurrences) " + tr("occurrences · ", "повторов · ") + "\(finding.sessions) " + tr("sessions", "сессий")).font(.system(size: 11)).foregroundStyle(quiet)
                    if let models = finding.models { Text(tr("Models: ", "Модели: ") + (models.isEmpty ? modelText(nil) : models.joined(separator: ", ")) + " · \(finding.unknownModelCalls ?? 0) " + tr("unknown", "неизвестных")).font(.system(size: 10)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true) }
                    Text(russian ? finding.suggestionRu : finding.suggestion).font(.system(size: 12))
                    if let reason = finding.reviewReason, !reason.isEmpty { Text(decisionText(finding.reviewStatus ?? "open") + " · " + decisionText(reason)).font(.system(size: 11)).foregroundStyle(quiet) }
                    Text(finding.inventoryStatus == "inventory_unknown" ? tr("Inventory unknown: no claim that a tool is missing", "Каталог неизвестен: отсутствие инструмента не установлено") : finding.inventoryStatus == "configured_unverified" ? tr("Candidate configured; live availability unverified", "Кандидат настроен; доступность не проверена") : tr("Category match requires manual review", "Совпадение категорий требует ручной проверки")).font(.system(size: 10)).foregroundStyle(amber)
                    Menu(tr("Record decision", "Отметить решение")) {
                        Button(tr("Confirmed pattern", "Повтор подтверждён")) { markFinding(finding.id, status: "open", reason: "confirmed-pattern") }
                        Button(tr("Implemented script", "Внедрён скрипт")) { markFinding(finding.id, status: "actioned", reason: "script") }
                        Button(tr("Implemented skill", "Внедрён скилл")) { markFinding(finding.id, status: "actioned", reason: "skill") }
                        Button(tr("Implemented MCP", "Внедрён MCP")) { markFinding(finding.id, status: "actioned", reason: "mcp") }
                        Button(tr("Dismiss", "Отклонить")) { markFinding(finding.id, status: "dismissed", reason: "not-applicable") }
                        ForEach(["waiting-process", "required-check", "different-task", "false-positive", "duplicate"], id: \.self) { reason in Button(decisionText(reason)) { markFinding(finding.id, status: "dismissed", reason: reason) } }
                        Button(tr("Reopen", "Вернуть в работу")) { markFinding(finding.id, status: "open") }
                    }.disabled(store.isFixture || reviewBusy)
                    if let sid = finding.evidenceSessions?.first ?? report.recentCalls.first(where: { finding.evidenceIds.contains($0.id) })?.session {
                        Button(tr("Inspect evidence →", "Посмотреть примеры →")) {
                            let session = report.sessions.first(where: { $0.id == sid }) ?? JournalSession(id: sid, provider: finding.provider, calls: 0, failed: 0, pending: 0, paired: 0, elapsedMs: nil, startedAt: nil, label: nil, outcome: "unknown", variant: nil)
                            select(session, evidenceIds: finding.evidenceIds)
                        }
                    }

                }.padding(.vertical, 8)
                Divider()
            }
            if !(report.findingReviews ?? []).isEmpty {
                Text(tr("Reviewed decisions", "Решения по находкам")).font(.system(size: 16, weight: .semibold)).id("finding-reviews")
                Text(tr("Equal time windows; partial coverage. A lower count or absence does not prove savings or resolution.", "Равные окна времени; частичный охват. Снижение или отсутствие не доказывает экономию или устранение проблемы.")).font(.system(size: 11)).foregroundStyle(quiet)
                ForEach(report.findingReviews ?? []) { row in
                    VStack(alignment: .leading, spacing: 4) {
                        Text((russian ? row.titleRu : row.title) + " · " + row.provider.uppercased()).font(.system(size: 12))
                        Text(decisionText(row.status) + " · " + decisionText(row.reason) + " · " + reviewStateText(row.recheckState)).font(.system(size: 11)).foregroundStyle(mint).fixedSize(horizontal: false, vertical: true)
                        Text(decisionText(row.lifecycle ?? "unknown")).font(.system(size: 11)).foregroundStyle(quiet)
                        ForEach(row.linkedVersions ?? []) { version in Text(version.assetId + " · " + version.version + " · \(version.declaredUses) " + tr("uses · ", "применений · ") + "\(version.accepted)/\(version.tasks) " + tr("accepted", "принято")).font(.system(size: 10)).foregroundStyle(quiet) }
                        Text("\(row.windowHours) h · " + stamp(row.afterWindowEndsAt, compact: true)).font(.system(size: 10)).foregroundStyle(quiet)
                        Button(tr("Reopen", "Вернуть в работу")) { markFinding(row.findingId, status: "open") }.disabled(store.isFixture || reviewBusy)
                    }
                }
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
                    Text(tr("Models: ", "Модели: ") + ((session.models ?? []).isEmpty ? modelText(nil) : session.models!.joined(separator: ", ")) + " · \(session.modelHistory?.unknownModelCalls ?? session.calls) " + tr("unknown calls", "вызовов без модели")).font(.system(size: 10)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true)
                    Divider()
                }
                if report.sessions.isEmpty { Text(tr("No observed sessions", "Наблюдаемых сессий пока нет")).foregroundStyle(quiet) }
        }
    }
    func sessionDetail() -> some View {
        VStack(alignment: .leading, spacing: 12) {

                Button(tr("← Sessions", "← Сессии")) { selectedSession = nil; evidence = []; pageRequest = UUID(); pageLoading = false }
                Text(String(selectedSession!.prefix(12))).font(.system(size: 17, weight: .medium, design: .monospaced))
                Text(tr("Arguments are intentionally hidden. Safe command shape, outcome and wall time only; overlapping durations are not summed.", "Аргументы скрыты. Только безопасная форма команды, исход и время; длительности параллельных вызовов не складываются.")).font(.system(size: 11)).foregroundStyle(quiet)
                if let history = modelHistory { modelTimeline(history) }
                HStack { TextField(tr("Task label (slug)", "Метка задачи (slug)"), text: $label); TextField(tr("Variant", "Вариант"), text: $variant); Picker(tr("Outcome", "Исход"), selection: $outcome) { ForEach(["unknown", "accepted", "failed", "rework"], id: \.self) { Text(outcomeText($0)).tag($0) } }.labelsHidden().frame(width: 160) }
                Button(tr("Save session review", "Оценить всю сессию")) {
                    guard let sid = selectedSession else { return }
                    if store.isFixture { message = tr("Demo: review not saved", "Демо: оценка не сохраняется"); return }
                    store.run(["journal", "--action", "annotate", "--session", sid, "--label", label, "--variant", variant, "--outcome", outcome]) { r in
                        if case .success = r { message = tr("Saved locally", "Сохранено локально"); store.refresh() }
                        else { message = tr("Use nonsensitive ASCII labels without spaces", "Используйте нечувствительные ASCII-метки без пробелов") }
                    }
                }
                if !message.isEmpty { Text(message).font(.system(size: 11)).foregroundStyle(amber) }
                DisclosureGroup(tr("Review a task within this page", "Оценить задачу на этой странице"), isExpanded: $taskExpanded) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(tr("Choose the first and last call of one actual task. Selection is limited to this page; shared or incomplete turns cannot receive a token total.", "Выберите первый и последний вызов одной реальной задачи. Выбор ограничен страницей; общие или неполные ходы не получают сумму токенов.")).font(.system(size: 11)).foregroundStyle(quiet)
                        Picker(tr("First call", "Первый вызов"), selection: $taskFirst) { ForEach(calls.indices, id: \.self) { i in Text("\(pageOffset + i + 1) · " + calls[i].tool).tag(i) } }
                        Picker(tr("Last call", "Последний вызов"), selection: $taskLast) { ForEach(calls.indices, id: \.self) { i in Text("\(pageOffset + i + 1) · " + calls[i].tool).tag(i) } }
                        HStack { Text(tr("Acceptance criterion", "Критерий приёмки")); TextField(tr("Criterion version", "Версия критерия"), text: $taskCriterion) }
                        Picker(tr("Asset version", "Версия инструмента"), selection: $chosenAsset) {
                            Text(tr("Baseline / no asset", "Исходный вариант / без инструмента")).tag("")
                            ForEach(assetMetrics.filter { $0.provider == calls.first?.provider }) { row in Text(row.assetId + " · " + row.version).tag(row.id) }
                        }.onChange(of: chosenAsset) { _, _ in
                            taskApplied = false
                            let demo = store.isFixture && CommandLine.arguments.contains("--task-assessment-demo")
                            taskEligibility = demo ? "yes" : "unknown"; taskNonUseReason = demo ? "unavailable" : ""
                        }
                        Picker(tr("Suitable for this task", "Подходит для этой задачи"), selection: $taskEligibility) { ForEach(["unknown", "yes", "no"], id: \.self) { Text(decisionText($0)).tag($0) } }.disabled(chosenAsset.isEmpty)
                        Toggle(tr("I confirm this version was applied", "Подтверждаю применение этой версии"), isOn: $taskApplied).disabled(chosenAsset.isEmpty || taskEligibility == "no").onChange(of: taskEligibility) { _, value in if value == "no" { taskApplied = false } }.onChange(of: taskApplied) { _, value in if value { taskNonUseReason = "" } }
                        Picker(tr("Reason for non-use", "Причина неприменения"), selection: $taskNonUseReason) { ForEach(["", "unknown", "unavailable", "not-selected", "workflow-mismatch", "preferred-alternative"], id: \.self) { Text(decisionText($0)).tag($0) } }.disabled(chosenAsset.isEmpty || taskApplied)
                        Button(tr("Save task review", "Сохранить оценку задачи"), action: saveTask).disabled(store.isFixture || reviewBusy || pageLoading || calls.isEmpty || label.isEmpty || taskLast < taskFirst)
                    }.padding(.top, 8).id("task-review")
                }
                Text(tr("Fixed journal snapshot · observed calls only · 30-day retention", "Фиксированный снимок журнала · только полученные вызовы · хранение 30 дней")).font(.system(size: 10)).foregroundStyle(quiet)
                HStack {
                    Text(pageLoading ? tr("Loading page…", "Загрузка страницы…") : "\(calls.isEmpty ? 0 : pageOffset + 1)–\(pageOffset + calls.count) / \(sessionTotal)").font(.system(size: 11)).foregroundStyle(quiet)
                    Spacer()
                    Button(tr("Previous", "Назад")) { loadSessionPage(selectedSession!, cursor: sessionCursors[sessionPage - 1], index: sessionPage - 1) }.disabled(store.isFixture || pageLoading || sessionPage == 0)
                    Button(tr("Next", "Далее")) { if let nextCursor { sessionCursors = Array(sessionCursors.prefix(sessionPage + 1)); sessionCursors.append(nextCursor); loadSessionPage(selectedSession!, cursor: nextCursor, index: sessionPage + 1) } }.disabled(store.isFixture || pageLoading || nextCursor == nil)
                }
                ForEach(calls) { call in callRow(call); Divider() }
        }
    }
    func callRow(_ call: JournalCall) -> some View {
        let duration = call.durationMs.map { String(format: "%.2f s", $0 / 1000) } ?? "—"
        let incomplete = call.paired ? "" : tr(" · incomplete pair", " · неполная пара")
        let metadata = [modelStamp(call.startedAt), duration, call.durationSource].joined(separator: " · ") + incomplete
        return
                    VStack(alignment: .leading, spacing: 4) {
                        HStack { Text(categoryText(call.category).uppercased()).font(.system(size: 10, weight: .bold)).foregroundStyle(evidence.contains(call.id) ? mint : quiet); Text(call.tool).font(.system(size: 11, design: .monospaced)); Spacer(); Text(outcomeText(call.outcome)).font(.system(size: 11)).foregroundStyle(call.outcome == "failed" ? amber : quiet) }
                        if let source = call.outcomeSource { Text(tr("Result source: ", "Источник результата: ") + source + (call.collectionIssue.map { " · " + $0 } ?? "")).font(.system(size: 10)).foregroundStyle(quiet) }
                        Text(modelText(call.model) + " · " + (call.modelSource ?? "not-reported")).font(.system(size: 11, design: .monospaced)).foregroundStyle(call.model == nil || call.model == "other" ? quiet : mint).fixedSize(horizontal: false, vertical: true)
                        Text(call.template).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                        Text(metadata).font(.system(size: 10)).foregroundStyle(quiet)
                    }.padding(.vertical, 6)
    }
    func modelTimeline(_ history: ModelHistory) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(tr("Observed model history", "История наблюдаемых моделей")).font(.system(size: 14, weight: .semibold))
            Text("\(history.knownModelCalls) " + tr("identified · ", "с моделью · ") + "\(history.unknownModelCalls) " + tr("unknown · ", "без модели · ") + "\(history.reportedChanges) " + tr("observed changes", "наблюдаемых изменений")).font(.system(size: 11)).foregroundStyle(quiet)
            Text(tr("Times mark observed calls, not the exact UI switch. Gaps and parallel lanes stay separate.", "Время относится к вызовам, а не к точному переключению в интерфейсе. Пропуски и параллельные ветки разделены.")).font(.system(size: 10)).foregroundStyle(quiet)
            ForEach(history.segments) { segment in
                VStack(alignment: .leading, spacing: 3) {
                    Text(modelText(segment.model) + " · \(segment.calls) " + tr("calls", "вызовов")).font(.system(size: 12, weight: .medium, design: .monospaced)).fixedSize(horizontal: false, vertical: true)
                    Text(modelStamp(segment.firstObservedAt) + " → " + modelStamp(segment.lastObservedAt) + " · " + modelTransitionText(segment.transition)).font(.system(size: 10)).foregroundStyle(quiet).fixedSize(horizontal: false, vertical: true)
                }
            }
            if history.truncated { Text(tr("Last 100 segments; export for full review", "Последние 100 участков; для полного просмотра — экспорт")).font(.system(size: 10)).foregroundStyle(amber) }
            Divider()
        }
    }
    func comparison(_ report: AnalyticsReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(tr("Review the same task family before and after a change", "Сравните одну группу задач до и после изменения")).font(.system(size: 16, weight: .semibold))
            Toggle(tr("Compare reviewed tasks", "Сравнивать отдельные задачи"), isOn: $compareTasks)
            if compareTasks { Picker(tr("Client", "Клиент"), selection: $compareProvider) { ForEach(Array(Set(report.coverage.map(\.provider) + ["codex", "glm"])).sorted(), id: \.self) { Text($0.uppercased()).tag($0) } } }
            Text("\(report.efficiency?.totalTasks ?? 0) " + tr("reviewed task selections. Tokens require complete native receipts; model requests are not tool calls.", "выбранных задач. Токены требуют полных штатных счётчиков; вызовы модели не равны вызовам инструментов.")).font(.system(size: 11)).foregroundStyle(quiet)
            Text(compareTasks ? tr("Review task boundaries, variant and acceptance in Sessions. At least 3 tasks per variant are needed. Review task difficulty and model settings.", "Выберите границы задач, вариант и приёмку в Сессиях. Нужно хотя бы 3 задачи на вариант. Проверьте сложность и настройки модели.") : tr("Label sessions, variant and acceptance in Sessions. At least 3 observations per variant are needed. Model settings and task difficulty still require your review.", "Укажите метки, вариант и результат в Сессиях. Нужно хотя бы 3 наблюдения на вариант. Настройки моделей и сложность задач проверяете вы.")).font(.system(size: 12)).foregroundStyle(quiet)
            if !compareTasks { Text("\(report.sessions.filter { !($0.label ?? "").isEmpty }.count) " + tr("labelled sessions in this view. Empty groups mean insufficient reviewed evidence, not zero improvement.", "размеченных сессий в этом разделе. Пустые группы означают недостаток проверенных данных, а не нулевое улучшение.")).font(.system(size: 11)).foregroundStyle(quiet) }
            HStack { TextField(tr("Task label", "Метка задачи"), text: $comparisonLabel); TextField(tr("Before", "До"), text: $before); TextField(tr("After", "После"), text: $after) }
            Button(tr("Compare observations", "Сравнить наблюдения")) {
                if store.isFixture { comparisonMessage = tr("Demo comparison: use real reviewed sessions to measure effects.", "Демо: для оценки эффекта используйте реальные проверенные сессии."); return }
                let queryLabel = comparisonLabel; let queryBefore = before; let queryAfter = after; let queryMode = compareTasks; let queryProvider = compareProvider
                let arguments = ["journal", "--action", compareTasks ? "compare-tasks" : "compare", "--label", queryLabel, "--before", queryBefore, "--after", queryAfter] + (compareTasks ? ["--provider", compareProvider] : [])
                store.run(arguments) { r in
                    guard comparisonLabel == queryLabel, before == queryBefore, after == queryAfter, compareTasks == queryMode, compareProvider == queryProvider else { return }
                    if case .success(let data) = r, let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        if queryMode { comparisonMessage = taskComparisonText(obj) }
                        else if let formatted = try? JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys]), let text = String(data: formatted, encoding: .utf8) { comparisonMessage = text }
                    }
                    else { comparisonMessage = tr("Use valid task and variant labels", "Проверьте метки задачи и вариантов") }
                }
            }
            if !comparisonMessage.isEmpty { Text(comparisonMessage).font(.system(size: 11, design: .monospaced)).textSelection(.enabled) }
            if compareTasks {
                HStack {
                    Button(tr("Pin pair in widget", "Закрепить пару в виджете")) { saveWidgetPair(clear: false) }
                        .disabled(widgetPinBusy || comparisonLabel.isEmpty || before.isEmpty || after.isEmpty || before == after || store.isFixture)
                    Button(tr("Clear widget pair", "Сбросить пару виджета")) { saveWidgetPair(clear: true) }.disabled(widgetPinBusy || store.isFixture)
                }
                if let c = store.snapshot?.providers.first(where: { $0.id == compareProvider })?.benefit?.comparison {
                    Text(tr("Pinned: ", "Закреплено: ") + c.label + " · " + c.before + " → " + c.after).font(.system(size: 11)).foregroundStyle(quiet)
                }
                Text(tr("The selected pair is recalculated on refresh over retained 30-day tasks. Metrics stay unavailable until evidence passes the comparison gates.", "Выбранная пара пересчитывается при обновлении по сохранённым задачам за 30 дней. Показатели появятся, когда сравнение пройдёт проверки.")).font(.system(size: 11)).foregroundStyle(quiet)
            }
            Text(tr("No causal claim, exact per-tool cost or promised subscription saving. Failed and rework results remain visible.", "Без заявления о причинности, точной стоимости инструмента или обещаний экономии подписки. Ошибки и доработки учитываются.")).font(.system(size: 11)).foregroundStyle(amber)
        }.onChange(of: comparisonLabel) { _, _ in comparisonMessage = "" }
        .onChange(of: before) { _, _ in comparisonMessage = "" }
        .onChange(of: after) { _, _ in comparisonMessage = "" }
        .onChange(of: compareTasks) { _, _ in comparisonMessage = "" }
        .onChange(of: compareProvider) { _, _ in comparisonMessage = "" }
    }
    func saveWidgetPair(clear: Bool) {
        guard !widgetPinBusy, !store.isFixture else { return }
        widgetPinBusy = true
        let args = ["journal", "--action", "widget-comparison", "--provider", compareProvider] + (clear ? [] : ["--label", comparisonLabel, "--before", before, "--after", after])
        store.run(args) { result in
            widgetPinBusy = false
            if case .success = result { comparisonMessage = tr("Widget selection saved", "Выбор для виджета сохранён"); store.refresh() }
            else { comparisonMessage = tr("Could not save widget selection", "Не удалось сохранить выбор для виджета") }
        }
    }
}
