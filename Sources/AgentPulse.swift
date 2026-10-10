import AppKit
import SwiftUI
import Combine
import ServiceManagement

@main enum AgentPulseMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        if !CommandLine.arguments.contains("--fixture"), let id = Bundle.main.bundleIdentifier,
           let existing = NSRunningApplication.runningApplications(withBundleIdentifier: id).first(where: { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier }) {
            existing.activate(options: []); return
        }
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
        withExtendedLifetime(delegate) {}
    }
}
