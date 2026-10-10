import AppKit
import SwiftUI
import Combine
import ServiceManagement

func tokenAxisTop(_ maximum: Double) -> Double {
    guard maximum.isFinite, maximum > 0 else { return 10 }
    let raw = max(1, maximum / 4)
    let magnitude = pow(10, floor(log10(raw)))
    let unit = raw / magnitude
    let step = (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * magnitude
    let top = ceil(maximum / step) * step
    return top.isFinite ? max(10, top) : maximum
}
struct DailyTokenPlot: View {
    var rows: [DayUsage]
    @Binding var selected: String?
    @Binding var hovered: String?
    private var days: [String] { Array(Set(rows.map(\.date))).sorted() }
    private var clients: [String] { Array(Set(rows.map(\.provider))).sorted() }
    private var top: Double { tokenAxisTop(rows.map(\.tokens).max() ?? 0) }
    private let palette: [Color] = [.blue, .green, .orange, .purple, .pink, .cyan]
    private func color(_ index: Int) -> Color { palette[index % palette.count] }
    private func value(_ day: String, _ client: String) -> Double? { rows.first { $0.date == day && $0.provider == client }?.tokens }
    private func day(_ point: CGPoint, width: CGFloat) -> String? {
        guard point.x >= 0, point.x < width, point.y >= 0, point.y < 150, !days.isEmpty else { return nil }
        return days[min(days.count-1, Int(point.x / width * Double(days.count)))]
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            GeometryReader { geometry in
                let width = max(1, geometry.size.width - 56)
                let slot = width / CGFloat(max(1, days.count))
                ZStack(alignment: .topLeading) {
                    ForEach(0..<5) { index in
                        let y = CGFloat(index) * 37.5
                        Text(shortNumber(top * Double(4-index) / 4)).font(.system(size: 10)).foregroundStyle(quiet)
                            .frame(width: 50, alignment: .trailing).position(x: 25, y: y)
                        Rectangle().fill(divider).frame(width: width, height: 1).offset(x: 56, y: y)
                    }
                    ForEach(Array(days.enumerated()), id: \.element) { index, date in
                        Rectangle().fill(mint.opacity((hovered ?? selected) == date ? 0.10 : 0))
                            .frame(width: slot, height: 150).offset(x: 56 + CGFloat(index) * slot)
                        HStack(alignment: .bottom, spacing: 2) {
                            ForEach(Array(clients.enumerated()), id: \.element) { clientIndex, client in
                                let tokens = value(date, client)
                                Rectangle().fill(tokens == nil ? Color.clear : color(clientIndex))
                                    .frame(width: max(1, min(14, slot / CGFloat(max(1, clients.count)) - 3)), height: CGFloat((tokens ?? 0) / top) * 150)
                                    .accessibilityLabel(date + " · " + client.uppercased())
                                    .accessibilityValue(fullNumber(tokens) + tr(" tokens", " токенов"))
                            }
                        }.frame(width: slot, height: 150, alignment: .bottom).offset(x: 56 + CGFloat(index) * slot)
                        if index % max(1, (days.count+4)/5) == 0 {
                            Text(date.suffix(5)).font(.system(size: 10)).foregroundStyle(quiet)
                                .position(x: 56 + (CGFloat(index)+0.5) * slot, y: 164)
                        }
                    }
                    Rectangle().fill(.clear).frame(width: width, height: 150).contentShape(Rectangle())
                        .onContinuousHover { phase in
                            switch phase {
                            case .active(let point): hovered = day(point, width: width)
                            case .ended: hovered = nil
                            }
                        }
                        .onTapGesture { point in if let date = day(point, width: width) { selected = date } }
                        .offset(x: 56)
                        .accessibilityHidden(true)
                }
            }.frame(height: 180)
            HStack(spacing: 10) {
                ForEach(Array(clients.enumerated()), id: \.element) { index, client in
                    HStack(spacing: 4) { Circle().fill(color(index)).frame(width: 7, height: 7); Text(client.uppercased()).font(.system(size: 10)).foregroundStyle(quiet) }
                }
            }
        }
    }
}

struct TokenHistoryView: View {
    var snapshot: Snapshot
    @State private var selectedDay: String?
    @State private var hoveredDay: String?
    private var history: [DayUsage] { snapshot.history.filter { $0.tokens.isFinite && $0.tokens >= 0 && isoDay.date(from: $0.date) != nil } }
    private var days: [String] { Array(Set(history.map(\.date))).sorted() }
    private var focusedDay: String? { hoveredDay ?? selectedDay }
    private func coverageLabel(_ row: DayUsage) -> String {
        switch row.coverage {
        case "known-account-sum": return tr("Reported sum of known accounts", "Переданная сумма известных аккаунтов")
        case "partial-local": return tr("Partial local events", "Частичные локальные события")
        default: return tr("Reported daily counter · source scope varies", "Переданный дневной счётчик · охват источников различается")
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(tr("Tokens by day · UTC", "Токены по дням · UTC")).font(.system(size: 16, weight: .semibold))
            if history.isEmpty {
                Text(tr("No daily counters reported", "Дневные счётчики не получены")).foregroundStyle(quiet)
            } else {
                DailyTokenPlot(rows: history, selected: $selectedDay, hovered: $hoveredDay)
                Text(tr("Hover to preview; click to select a day. Values below are exact reported counters.", "Наведите для просмотра; нажмите, чтобы выбрать день. Ниже — точные переданные значения.")).font(.system(size: 11)).foregroundStyle(quiet)
                Picker(tr("Day · UTC", "День · UTC"), selection: $selectedDay) {
                    Text(tr("Choose a day", "Выберите день")).tag(nil as String?)
                    ForEach(days, id: \.self) { day in Text(day).tag(Optional(day)) }
                }.accessibilityLabel(tr("Select token day", "Выбрать день расхода токенов"))
                if let focusedDay {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(focusedDay + " · UTC" + (hoveredDay == nil ? "" : tr(" · preview", " · просмотр"))).font(.system(size: 14, weight: .semibold))
                        ForEach(snapshot.providers) { provider in
                            let row = history.first { $0.date == focusedDay && $0.provider == provider.id }
                            HStack(alignment: .top) {
                                Text(provider.id.uppercased()).frame(width: 88, alignment: .leading)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(fullNumber(row?.tokens) + (row == nil ? "" : tr(" tokens", " токенов"))).monospacedDigit()
                                    Text(row.map(coverageLabel) ?? tr("No daily counter; this is not zero", "Дневной счётчик отсутствует; это не ноль")).font(.system(size: 10)).foregroundStyle(quiet)
                                }
                            }.font(.system(size: 12))
                        }
                        Text(tr("Hourly token counts are not reported by these daily sources. Quota percentages are a separate measurement.", "Почасовые токены эти дневные источники не передают. Проценты лимитов — отдельное измерение.")).font(.system(size: 11)).foregroundStyle(quiet)
                    }.padding(12).frame(maxWidth: .infinity, alignment: .leading).background(divider.opacity(0.35)).clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
        }
        .onAppear {
            if selectedDay == nil { selectedDay = days.last }
            if storeFixtureDay != nil { selectedDay = storeFixtureDay }
        }
    }
    private var storeFixtureDay: String? {
        let args = CommandLine.arguments
        guard args.contains("--fixture"), let index = args.firstIndex(of: "--history-day"), index+1 < args.count, days.contains(args[index+1]) else { return nil }
        return args[index+1]
    }
}

