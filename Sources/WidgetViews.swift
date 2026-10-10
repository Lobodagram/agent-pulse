import AppKit
import SwiftUI
import Combine
import ServiceManagement

struct DragHandle: NSViewRepresentable {
    final class Grip: NSView { override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) } }
    func makeNSView(context: Context) -> Grip { Grip() }; func updateNSView(_ nsView: Grip, context: Context) {}
}
struct ActionButton: View {
    var symbol: String; var help: String; var action: () -> Void
    var body: some View { Button(action: action) { Image(systemName: symbol).frame(width: 30, height: 30).contentShape(Rectangle()) }.buttonStyle(.plain).foregroundStyle(quiet).help(help).accessibilityLabel(help) }
}
func todayText(_ p: Provider) -> String {
    if let value = p.todayTokens { return shortNumber(value) + (p.todayTokenCoverage == "partial-local" ? tr(" · partial", " · частично") : "") }
    return p.todayTokenStatus == "account-day-pending" ? tr("awaiting report", "жду отчёт") : p.todayTokenStatus == "local-day-pending" ? tr("no local data yet", "ещё нет данных") : tr("not reported", "не передано")
}
struct ResizeGrip: NSViewRepresentable {
    var actions: AppDelegate; var scale: Double
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
    func updateNSView(_ view: Grip, context: Context) { view.actions = actions; view.setAccessibilityValue(scale * 100) }
}
struct ProviderLine: View {
    let provider: Provider
    var metricMode: String = "limits"
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(provider.name.uppercased()).font(.system(size: 10, weight: .bold, design: .monospaced)).tracking(1).foregroundStyle(quiet)
                Spacer()
                Text(provider.status == "ready" ? tr("reported", "получено") : provider.status == "stale" ? tr("stale", "устарело") : tr("unavailable", "нет данных")).font(.system(size: 10)).foregroundStyle(provider.status == "ready" ? quiet : amber)
            }
            if metricMode == "limits" && !provider.quotas.isEmpty {
                HStack(spacing: 18) {
                    ForEach(provider.quotas.prefix(2)) { q in
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            Text(q.remainingPercent.map { "\(Int(floor($0)))%" } ?? "—").font(.system(size: 23, weight: .medium, design: .monospaced)).foregroundStyle((q.remainingPercent ?? 100) < 15 ? amber : mint)
                            VStack(alignment: .leading, spacing: 1) { Text(q.label).font(.system(size: 10)); Text(stamp(q.resetsAt, compact: true)).font(.system(size: 9)).foregroundStyle(quiet) }
                        }
                    }
                }
                Text(tr("Today · UTC: ", "Сегодня · UTC: ") + todayText(provider)).font(.system(size: 10)).foregroundStyle(quiet)
            } else {
                HStack(alignment: .firstTextBaseline) {
                    Text(metricMode == "today" ? shortNumber(provider.todayTokens) : "—").font(.system(size: 23, weight: .medium, design: .monospaced))
                    Text(metricMode == "today" ? tr("tokens today · UTC", "токены сегодня · UTC") : tr("limits not reported", "лимиты не переданы")).font(.system(size: 10)).foregroundStyle(quiet)
                }
                Text(metricMode == "today" ? (provider.todayTokenCoverage == "partial-local" ? tr("Partial local count", "Частичный локальный счётчик") : provider.id == "glm" ? tr("Local ZCode records", "Локальные записи ZCode") : tr("Reported day count", "Переданный счётчик дня")) : provider.id == "glm" ? tr("Connect GLM in Settings", "GLM: подключить в настройках") : tr("No reported account quota", "Квота аккаунта не передана")).font(.system(size: 10)).foregroundStyle(quiet)
                Text(subscriptionText(provider.subscription)).font(.system(size: 10)).foregroundStyle(quiet)
            }
        }.foregroundStyle(ink).lineLimit(1).minimumScaleFactor(0.8)
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
                HStack(spacing: 4) { PulseBrandMark(size: 20); Text("AGENT PULSE").font(.system(size: 11, weight: .semibold)).tracking(1); if store.isFixture { Text("DEMO").font(.system(size: 9)).foregroundStyle(amber) } }.frame(height: 26).overlay(DragHandle()).help(tr("Drag by this title", "Перетащить за заголовок"))
                Spacer()
                ActionButton(symbol: "arrow.clockwise", help: tr("Refresh", "Обновить"), action: store.refresh)
                ActionButton(symbol: "chart.bar.xaxis", help: tr("Analytics", "Аналитика"), action: actions.showAnalysis)
                ActionButton(symbol: "gearshape", help: tr("Settings", "Настройки"), action: actions.showSettings)
                ActionButton(symbol: "xmark", help: tr("Hide widget · Agent Pulse keeps running", "Скрыть виджет · Agent Pulse продолжит работать"), action: actions.hidePanel)
            }
            if let snapshot = store.snapshot {
                ForEach(store.visibleProviders) { p in ProviderLine(provider: p, metricMode: store.metricMode).frame(height: 78, alignment: .topLeading); Rectangle().fill(divider).frame(height: 1) }
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
                    Button(store.metricMode == "limits" ? tr("Limits ⇄", "Лимиты ⇄") : tr("Today ⇄", "Сегодня ⇄")) { store.metricMode = store.metricMode == "limits" ? "today" : "limits" }.buttonStyle(.plain).foregroundStyle(mint).help(tr("Switch remaining quotas / tokens today · menu bar keeps quotas", "Переключить остаток лимитов / токены сегодня · сверху остаются лимиты")).accessibilityLabel(tr("Switch widget metric", "Переключить показатель виджета"))
                    if store.pages > 1 { Button("‹") { store.page = (store.page + store.pages - 1) % store.pages }.buttonStyle(.plain); Text("\(store.page + 1)/\(store.pages)"); Button("›") { store.page = (store.page + 1) % store.pages }.buttonStyle(.plain) }
                    Text(store.error ?? (store.loading ? tr("Updating…", "Обновление…") : stamp(snapshot.generatedAt, compact: true))).lineLimit(1)
                    Spacer(); Button(store.expanded ? tr("Less ↑", "Меньше ↑") : tr("Details ↓", "Детали ↓")) { actions.toggleExpanded() }.buttonStyle(.plain).foregroundStyle(mint)
                }.padding(.trailing, 16).font(.system(size: 11)).foregroundStyle(store.error == nil ? quiet : amber)
            } else { Spacer(); Text(store.error ?? tr("Reading client counters…", "Читаю счётчики клиентов…")).font(.system(size: 12)).foregroundStyle(quiet); Spacer() }
        }.padding(.horizontal, 18).padding(.vertical, 10).frame(width: 360, height: store.expanded ? 430 : 270, alignment: .topLeading).background(bg).foregroundStyle(ink).colorScheme(.dark)
        .overlay(alignment: .bottomTrailing) {
            Image(systemName: "arrow.up.left.and.arrow.down.right").font(.system(size: 9)).foregroundStyle(quiet).padding(5)
                .frame(width: 30, height: 30).overlay(ResizeGrip(actions: actions, scale: store.widgetScale)).help(tr("Drag to resize · 80–100%", "Потяните для изменения размера · 80–100%"))
        }
    }
}
// Plain SwiftUI bars avoid Swift Charts' Metal device initialization on headless Intel.
