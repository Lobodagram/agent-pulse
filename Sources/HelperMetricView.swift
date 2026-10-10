import SwiftUI

struct HelperMetricView: View {
    let row: HelperMetric
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(row.provider.uppercased() + " · " + row.operation + " · " + row.version)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
            Text(tr("Success / failed: ", "Успех / ошибки: ") + "\(row.successes) / \(row.failures) · " +
                 tr("known ", "известно ") + "\(row.knownResults)/\(row.runs)")
                .font(.system(size: 10)).foregroundStyle(quiet)
            Text(tr("Pending / stale / conflicts / missing start: ", "Без завершения / давние / конфликты / нет начала: ") +
                 "\(row.pendingRuns) / \(row.staleRuns) / \(row.conflicts) / \(row.finishWithoutStart)")
                .font(.system(size: 10)).foregroundStyle(quiet)
            Text(tr("Median paired time: ", "Медиана времени парных запусков: ") +
                 (row.medianElapsedMs.map { String(format: "%.1f", $0 / 1000) + tr(" s", " с") } ?? "—") + " (\(row.timedRuns))")
                .font(.system(size: 10)).foregroundStyle(quiet)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 6)
    }
}
