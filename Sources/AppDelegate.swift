import AppKit
import SwiftUI
import Combine
import ServiceManagement

final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusPage = 0; var statusTimer: Timer?; var fixtureWindowTimer: Timer?; var observations = Set<AnyCancellable>(); var statusMenu: NSMenu?
    var store: PulseStore!
    var panel: FloatingPanel?
    var statusItem: NSStatusItem!
    var analysisWindow: NSWindow?
    var settingsWindow: NSWindow?
    var fixtureTogglePassed = false
    var fixtureFocusChecks: [String: Bool] = [:]
    var fixtureControlChecks: [String: Bool] = [:]
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        store = PulseStore()
        let main = NSMenu()
        let appMenu = NSMenu()
        let appRoot = NSMenuItem(); appRoot.submenu = appMenu; main.addItem(appRoot)
        for (title, action, key) in [(tr("Analytics", "Аналитика"), #selector(openAnalysis), "1"), (tr("Settings", "Настройки"), #selector(openSettings), ",")] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: key); item.target = self; appMenu.addItem(item)
        }
        appMenu.addItem(.separator())
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
        store.$menuFollowActive.sink { [weak self] _ in DispatchQueue.main.async { self?.updateStatus() } }.store(in: &observations)
        NSWorkspace.shared.notificationCenter.publisher(for: NSWorkspace.didActivateApplicationNotification).sink { [weak self] _ in DispatchQueue.main.async { self?.updateStatus() } }.store(in: &observations)
        statusTimer = Timer.scheduledTimer(withTimeInterval: 8, repeats: true) { [weak self] _ in Task { @MainActor in self?.statusPage += 1; self?.updateStatus() } }
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
        store.$widgetScale.sink { [weak self] _ in DispatchQueue.main.async { self?.resizePanel() } }.store(in: &observations)
        store.$benefitExpanded.dropFirst().sink { [weak self] _ in DispatchQueue.main.async { self?.resizePanel() } }.store(in: &observations)
        store.$page.dropFirst().sink { [weak self] _ in DispatchQueue.main.async { self?.resizePanel() } }.store(in: &observations)
        store.$snapshot.dropFirst().sink { [weak self] _ in DispatchQueue.main.async { self?.resizePanel() } }.store(in: &observations)
        store.$topmost.sink { [weak self] value in DispatchQueue.main.async { self?.panel?.level = value ? .floating : .normal } }.store(in: &observations)
        store.$displayMode.dropFirst().sink { [weak self] value in DispatchQueue.main.async { if value == "floating" { self?.panel?.orderFrontRegardless() } else { self?.panel?.orderOut(nil) }; self?.updateStatus() } }.store(in: &observations)
        if store.displayMode != "menu" { panel.orderFrontRegardless() }
        updateStatus()
        handleSnapshotArguments()
        if store.isFixture, let i = CommandLine.arguments.firstIndex(of: "--ready-file"), i+1 < CommandLine.arguments.count {
            try? Data("ready".utf8).write(to: URL(fileURLWithPath: CommandLine.arguments[i+1]), options: .atomic)
        }
        if store.isFixture, let i = CommandLine.arguments.firstIndex(of: "--window-state-file"), i+1 < CommandLine.arguments.count {
            let path = CommandLine.arguments[i+1]
            fixtureWindowTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    guard let self else { return }
                    let windows = [("widget", self.panel as NSWindow?), ("analytics", self.analysisWindow), ("settings", self.settingsWindow)].compactMap { kind, window -> [String: Any]? in
                        guard let window else { return nil }
                        return ["kind": kind, "number": window.windowNumber, "visible": window.isVisible, "miniaturized": window.isMiniaturized, "key": window.isKeyWindow, "main": window.isMainWindow, "level": window.level.rawValue]
                    }
                    if let data = try? JSONSerialization.data(withJSONObject: ["active": NSApp.isActive, "windows": windows], options: [.sortedKeys]) {
                        try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
                    }
                }
            }
        }
    }
    @objc func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if settingsWindow?.isVisible == true { presentUtilityWindow(settingsWindow) }
        else if analysisWindow?.isVisible == true { presentUtilityWindow(analysisWindow) }
        else { panel?.orderFrontRegardless(); sender.activate(ignoringOtherApps: true) }
        return false
    }
    func applicationDidBecomeActive(_ notification: Notification) {
        // A second executable launch activates the existing instance without a reopen event.
        if panel?.isVisible == false && settingsWindow?.isVisible != true && analysisWindow?.isVisible != true {
            panel?.orderFrontRegardless()
        }
    }
    func updateStatus() {
        guard let button = statusItem?.button else { return }
        let providers = store.snapshot?.providers ?? []
        let lines = providers.map(compactQuotaLine)
        let font = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .medium)
        var index = statusPage % max(1, lines.count)
        let args = CommandLine.arguments
        let fixtureID = store.isFixture ? args.firstIndex(of: "--active-app").flatMap { $0 + 1 < args.count ? args[$0+1] : nil } : nil
        if store.menuFollowActive, let provider = activeProvider(bundleID: fixtureID ?? NSWorkspace.shared.frontmostApplication?.bundleIdentifier), let match = providers.firstIndex(where: { $0.id == provider }) { index = match }
        let values = lines.isEmpty ? "—" : lines[index]
        button.title = store.menuNumbers && store.displayMode == "menu" ? values : ""
        button.imagePosition = .imageLeading; button.font = font
        let caption = tr("Remaining limits · — not reported · click to show/hide movable widget", "Осталось лимитов · — не передано · нажмите: показать/скрыть подвижное табло")
        button.toolTip = ([caption] + lines).joined(separator: "\n")
        button.setAccessibilityLabel("Agent Pulse · " + caption + " · " + lines.joined(separator: " · "))
    }
    @objc func statusClicked() {
        guard let button = statusItem.button else { return }
        if NSApp.currentEvent?.type == .rightMouseUp { statusMenu?.popUp(positioning: nil, at: NSPoint(x: 0, y: button.bounds.minY), in: button); return }
        togglePanel()
        if panel?.isVisible == true { NSApp.activate(ignoringOtherApps: true) }
    }
    func setScale(_ value: Double) { store.widgetScale = min(1, max(0.8, value)); resizePanel() }
    func resizePanel() {
        guard let panel else { return }
        let top = panel.frame.maxY
        panel.setFrame(NSRect(x: panel.frame.minX, y: top - store.baseHeight * store.widgetScale, width: 360 * store.widgetScale, height: store.baseHeight * store.widgetScale), display: true)
        panel.contentView?.layer?.cornerRadius = 14 * store.widgetScale
    }
    func setDisplayMode(_ mode: String) {
        store.displayMode = mode == "menu" ? "menu" : "floating"
        if store.displayMode == "menu" { panel?.orderOut(nil) } else { panel?.orderFrontRegardless() }
        updateStatus()
    }
    @objc func refresh() { store.refresh() }
    @objc func quit() { NSApp.terminate(nil) }
    @objc func togglePanel() { if panel?.isVisible == true { hidePanel() } else { panel?.orderFrontRegardless() } }
    func hidePanel() { panel?.orderOut(nil) }
    func toggleExpanded() {
        guard panel != nil else { return }
        store.expanded.toggle(); resizePanel()
    }
    @objc func openAnalysis() { toggleUtilityWindow(analysisWindow, show: showAnalysis) }
    func toggleUtilityWindow(_ window: NSWindow?, show: () -> Void) {
        // The nonactivating widget can become key while the utility remains main.
        if let window, window.isVisible, !window.isMiniaturized, NSApp.isActive,
           window.isKeyWindow || window.isMainWindow {
            window.orderOut(nil)
        } else { show() }
    }
    func presentUtilityWindow(_ window: NSWindow?) {
        guard let window else { return }
        // A click in the nonactivating widget must restore and focus its utility.
        window.level = .normal
        window.collectionBehavior = [.moveToActiveSpace, .fullScreenAuxiliary]
        if window.isMiniaturized { window.deminiaturize(nil) }
        window.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.async { window.makeKeyAndOrderFront(nil) }
    }
    func showAnalysis() {
        if analysisWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 620), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
            w.title = tr("Agent Pulse · analytics", "Agent Pulse · аналитика"); w.isReleasedWhenClosed = false; w.minSize = NSSize(width: 620, height: 520)
            w.contentView = NSHostingView(rootView: AnalysisView(store: store)); w.center(); analysisWindow = w
        }
        presentUtilityWindow(analysisWindow)
    }
    @objc func openSettings() { toggleUtilityWindow(settingsWindow, show: showSettings) }
    func closeSettings() { settingsWindow?.close() }
    func minimizeSettings() { settingsWindow?.miniaturize(nil) }
    func showSettings() {
        if settingsWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 620), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
            w.title = "Agent Pulse " + pulseApplicationVersion + tr(" · settings", " · настройки"); w.isReleasedWhenClosed = false
            w.contentView = NSHostingView(rootView: SettingsView(store: store, actions: self)); w.center(); settingsWindow = w
        }
        presentUtilityWindow(settingsWindow)
    }
    func checkFixtureFocus(stage: Int, deadline: Date) {
        guard store.isFixture else { return }
        let ready = NSApp.isActive && settingsWindow?.isVisible == true && settingsWindow?.isKeyWindow == true
        if !ready {
            guard Date() < deadline else { fixtureFocusChecks[stage == 0 ? "readyBefore" : "readyAfter"] = false; return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.02) { self.checkFixtureFocus(stage: stage, deadline: deadline) }
            return
        }
        fixtureFocusChecks[stage == 0 ? "readyBefore" : "readyAfter"] = true
        if stage == 0 {
            panel?.makeKey()
            fixtureFocusChecks["widgetKey"] = panel?.isKeyWindow == true
            fixtureFocusChecks["utilityMain"] = settingsWindow?.isMainWindow == true
            openSettings()
            fixtureFocusChecks["hidden"] = settingsWindow?.isVisible == false
            openSettings()
            checkFixtureFocus(stage: 1, deadline: Date().addingTimeInterval(0.8))
        } else {
            fixtureTogglePassed = fixtureFocusChecks["hidden"] == true && fixtureFocusChecks["widgetKey"] == true && fixtureFocusChecks["utilityMain"] == true
        }
    }
    func checkFixtureWindowControls(stage: Int, deadline: Date) {
        guard store.isFixture, let panel else { return }
        if stage == 0 {
            let displayMode = store.displayMode
            hidePanel()
            fixtureControlChecks["widgetCloseHides"] = !panel.isVisible
            fixtureControlChecks["hidePreservesPlacement"] = store.displayMode == displayMode
            _ = applicationShouldHandleReopen(NSApp, hasVisibleWindows: false)
            fixtureControlChecks["explicitReopenShowsWidget"] = panel.isVisible
            fixtureControlChecks["reopenPreservesPlacement"] = store.displayMode == displayMode
            hidePanel()
            applicationDidBecomeActive(Notification(name: NSApplication.didBecomeActiveNotification))
            fixtureControlChecks["activationRestoresWidget"] = panel.isVisible
            fixtureControlChecks["activationPreservesPlacement"] = store.displayMode == displayMode
            hidePanel()
            togglePanel()
            fixtureControlChecks["statusRestoresWidget"] = panel.isVisible
            showSettings()
            fixtureControlChecks["settingsCanMinimize"] = settingsWindow?.styleMask.contains(.miniaturizable) == true
            // Let presentation and AppKit's minimize animation run on the main loop.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in
                self?.minimizeSettings()
                self?.checkFixtureWindowControls(stage: 1, deadline: Date().addingTimeInterval(2))
            }
        } else if stage == 1 {
            if settingsWindow?.isMiniaturized == true || Date() >= deadline {
                fixtureControlChecks["settingsMinimized"] = settingsWindow?.isMiniaturized == true
                showSettings()
                checkFixtureWindowControls(stage: 2, deadline: Date().addingTimeInterval(2))
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { [weak self] in self?.checkFixtureWindowControls(stage: 1, deadline: deadline) }
            }
        } else {
            if settingsWindow?.isVisible == true && settingsWindow?.isMiniaturized == false || Date() >= deadline {
                let settings = settingsWindow
                fixtureControlChecks["settingsRestored"] = settings?.isVisible == true && settings?.isMiniaturized == false
                closeSettings()
                fixtureControlChecks["settingsClosed"] = settings?.isVisible == false
                showSettings()
                fixtureControlChecks["settingsReopened"] = settingsWindow === settings && settings?.isVisible == true
                closeSettings()
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { [weak self] in self?.checkFixtureWindowControls(stage: 2, deadline: deadline) }
            }
        }
    }
    func handleSnapshotArguments() {
        let args = CommandLine.arguments
        guard let index = args.firstIndex(of: "--snapshot"), index + 1 < args.count else { return }
        let path = args[index + 1]
        let mode = args.firstIndex(of: "--view").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } ?? "compact"
        if store.isFixture {
            if let i = args.firstIndex(of: "--status-page"), i+1 < args.count { statusPage = max(0, Int(args[i+1]) ?? 0) }
            if args.contains("--active-app") { store.menuFollowActive = true }
            updateStatus()
        }
        if mode == "expanded" { toggleExpanded() }
        if args.contains("--benefit-control-check"), let id = store.visibleProviders.first?.id {
            let initial = store.baseHeight
            fixtureControlChecks["benefitStartsCollapsed"] = store.benefitExpanded.isEmpty
            store.toggleBenefit(id); resizePanel()
            fixtureControlChecks["benefitOpensAndResizes"] = store.benefitExpanded.contains(id) && abs((panel?.frame.height ?? 0) - ceil((initial + 62) * store.widgetScale)) < 0.01
            if store.pages > 1 {
                store.page = 1; resizePanel()
                fixtureControlChecks["benefitPageShrinks"] = store.baseHeight == initial
                store.page = 0; resizePanel()
                fixtureControlChecks["benefitPageRestores"] = store.baseHeight == initial + 62
            }
            store.toggleBenefit(id); resizePanel()
            fixtureControlChecks["benefitClosesAndResizes"] = store.benefitExpanded.isEmpty && abs((panel?.frame.height ?? 0) - ceil(initial * store.widgetScale)) < 0.01
        }
        if mode.hasPrefix("analysis") { showAnalysis() }
        if mode == "analysis-small" { analysisWindow?.setContentSize(NSSize(width: 620, height: 520)) }
        if mode == "analysis-large" { analysisWindow?.setContentSize(NSSize(width: 900, height: 700)) }
        if mode == "settings" { showSettings() }
        if mode == "window-controls", store.isFixture { checkFixtureWindowControls(stage: 0, deadline: Date().addingTimeInterval(2)) }
        if mode == "window-focus", store.isFixture {
            showAnalysis(); analysisWindow?.miniaturize(nil); showAnalysis()
            showSettings(); settingsWindow?.orderOut(nil); showSettings()
            checkFixtureFocus(stage: 0, deadline: Date().addingTimeInterval(0.8))
        }
        if mode == "menu-widget" { setDisplayMode("menu"); DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.statusClicked() } }
        if mode == "resize-check", store.isFixture {
            let grip = ResizeGrip.Grip(); grip.actions = self
            let down = NSEvent.mouseEvent(with: .leftMouseDown, location: NSPoint(x: 280, y: 10), modifierFlags: [], timestamp: 0, windowNumber: panel?.windowNumber ?? 0, context: nil, eventNumber: 1, clickCount: 1, pressure: 1)!
            let drag = NSEvent.mouseEvent(with: .leftMouseDragged, location: NSPoint(x: 340, y: 10), modifierFlags: [], timestamp: 0.1, windowNumber: panel?.windowNumber ?? 0, context: nil, eventNumber: 2, clickCount: 1, pressure: 1)!
            grip.mouseDown(with: down); grip.mouseDragged(with: drag)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + (store.isFixture && args.contains("--rotation-check") ? 9 : mode == "window-controls" ? 6 : 2)) { [weak self] in
            guard let self else { return }
            let w = mode.hasPrefix("analysis") ? self.analysisWindow : mode == "settings" ? self.settingsWindow : self.panel
            let captureView = mode == "menu-bar" ? self.statusItem.button : w?.contentView
            if let view = captureView, let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: rep)
                if let data = rep.representation(using: .png, properties: [:]) { try? data.write(to: URL(fileURLWithPath: path)) }
            }
            if let panel = self.panel {
                let before = panel.isVisible
                self.hidePanel(); let hidden = !panel.isVisible
                self.togglePanel(); let restored = panel.isVisible
                let report: [String: Any] = ["view": mode, "utilityFocusChecks": self.fixtureFocusChecks, "utilityTogglePassed": mode != "window-focus" || self.fixtureTogglePassed, "utilityRestorePassed": mode != "window-focus" || (self.analysisWindow?.isVisible == true && self.analysisWindow?.isMiniaturized == false && self.settingsWindow?.isVisible == true), "utilityFocusPassed": mode != "window-focus" || (self.settingsWindow?.isKeyWindow == true && NSApp.isActive), "utilityPlacementPassed": mode != "window-focus" || (self.settingsWindow?.level == .normal && self.settingsWindow?.collectionBehavior.contains(.moveToActiveSpace) == true), "panelWidth": panel.frame.width, "panelHeight": panel.frame.height, "floatingLevel": panel.level == .floating, "joinsAllSpaces": panel.collectionBehavior.contains(.canJoinAllSpaces), "fullScreenAuxiliary": panel.collectionBehavior.contains(.fullScreenAuxiliary), "movable": panel.isMovableByWindowBackground, "visibleBefore": before, "hidePassed": hidden, "restorePassed": restored, "statusItem": self.statusItem.button != nil, "fixtureMode": self.store.isFixture, "metricMode": self.store.metricMode, "scale": self.store.widgetScale, "menuClickShowsPanel": mode == "menu-widget" && before, "menuTooltip": self.statusItem.button?.toolTip ?? "", "displayMode": self.store.displayMode, "menuTitle": self.statusItem.button?.title ?? "", "capturedSize": [w?.contentView?.bounds.width ?? 0, w?.contentView?.bounds.height ?? 0]]
                var result = report; result["windowControlChecks"] = self.fixtureControlChecks
                if let data = try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]) {
                    try? data.write(to: URL(fileURLWithPath: path + ".json"))
                }
            }
            NSApp.terminate(nil)
        }
    }
}
