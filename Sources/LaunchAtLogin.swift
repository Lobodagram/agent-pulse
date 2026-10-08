import Foundation
import Combine
import ServiceManagement

enum LoginItemStatus: String { case disabled, enabled, requiresApproval, unavailable }

@MainActor protocol LoginItemService {
    var status: LoginItemStatus { get }
    func register() throws
    func unregister() throws
}

@MainActor struct MacLoginItemService: LoginItemService {
    var status: LoginItemStatus {
        switch SMAppService.mainApp.status {
        case .enabled: return .enabled
        case .requiresApproval: return .requiresApproval
        case .notRegistered: return .disabled
        case .notFound: return .unavailable
        @unknown default: return .unavailable
        }
    }
    func register() throws { try SMAppService.mainApp.register() }
    func unregister() throws { try SMAppService.mainApp.unregister() }
}

@MainActor final class LaunchAtLoginController: ObservableObject {
    @Published private(set) var status: LoginItemStatus = .disabled
    @Published private(set) var failed = false
    let preview: Bool
    let allowed: Bool
    private let service: any LoginItemService
    var checked: Bool { status == .enabled || status == .requiresApproval }

    init(service: any LoginItemService, preview: Bool, allowed: Bool) {
        self.service = service; self.preview = preview; self.allowed = allowed
        refresh()
    }
    func refresh() {
        guard !preview, allowed else { return }
        status = service.status
    }
    func setEnabled(_ enabled: Bool) {
        guard !preview, allowed else { return }
        failed = false; refresh()
        if enabled && checked || !enabled && status == .disabled { return }
        do {
            if enabled { try service.register() } else { try service.unregister() }
        } catch { failed = true }
        refresh()
        if enabled ? !checked : status != .disabled { failed = true }
    }
}
