import SwiftUI
import AppKit
import Combine
import ServiceManagement

// MARK: - App Settings

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    @Published var autoDetectClipboard: Bool {
        didSet { UserDefaults.standard.set(autoDetectClipboard, forKey: "autoDetectClipboard") }
    }
    @Published var launchAtLogin: Bool {
        didSet { UserDefaults.standard.set(launchAtLogin, forKey: "launchAtLogin") }
    }
    @Published var colorScheme: ColorSchemePreference {
        didSet { UserDefaults.standard.set(colorScheme.rawValue, forKey: "colorScheme") }
    }
    @Published var globalShortcutKeyCode: UInt16 {
        didSet {
            UserDefaults.standard.set(Int(globalShortcutKeyCode), forKey: "globalShortcutKeyCode")
            registerGlobalShortcut()
        }
    }
    @Published var globalShortcutModifiers: UInt {
        didSet {
            UserDefaults.standard.set(Int(globalShortcutModifiers), forKey: "globalShortcutModifiers")
            registerGlobalShortcut()
        }
    }

    /// Whether the popover/menu is currently visible
    @Published var isPopoverVisible: Bool = false

    private init() {
        self.autoDetectClipboard = UserDefaults.standard.bool(forKey: "autoDetectClipboard")
        self.launchAtLogin = UserDefaults.standard.bool(forKey: "launchAtLogin")
        self.colorScheme = ColorSchemePreference(
            rawValue: UserDefaults.standard.string(forKey: "colorScheme") ?? "system"
        ) ?? .system
        self.globalShortcutKeyCode = UInt16(UserDefaults.standard.integer(forKey: "globalShortcutKeyCode"))
        self.globalShortcutModifiers = UInt(UserDefaults.standard.integer(forKey: "globalShortcutModifiers"))

        // Default shortcut: Command+Shift+Space (keyCode 49 = space)
        if self.globalShortcutKeyCode == 0 {
            self.globalShortcutKeyCode = 49
            self.globalShortcutModifiers = NSEvent.ModifierFlags.command.rawValue |
                                           NSEvent.ModifierFlags.shift.rawValue
        }
    }

    // MARK: - Global Shortcut

    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?

    func registerGlobalShortcut() {
        // Remove existing tap
        if let tap = eventTap {
            CFMachPortInvalidate(tap)
            if let source = runLoopSource {
                CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes)
            }
            eventTap = nil
            runLoopSource = nil
        }

        let keyCode = globalShortcutKeyCode
        let modifiers = globalShortcutModifiers

        // Create an event tap for key events
        let eventMask = (1 << CGEventType.keyDown.rawValue)
        let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: CGEventMask(eventMask),
            callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
                guard type == .keyDown else {
                    return Unmanaged.passUnretained(event)
                }

                let eventKeyCode = event.getIntegerValueField(.keyboardEventKeycode)
                let eventFlags = event.flags

                // Mask only the modifier flags we care about
                let wantedMods: CGEventFlags = [.maskCommand, .maskShift, .maskAlternate, .maskControl]
                let maskedEventFlags = eventFlags.rawValue & wantedMods.rawValue
                let maskedWantedFlags = CGEventFlags(rawValue: modifiers) & wantedMods

                if UInt16(eventKeyCode) == keyCode && maskedEventFlags == maskedWantedFlags.rawValue {
                    DispatchQueue.main.async {
                        AppSettings.shared.isPopoverVisible.toggle()
                        if AppSettings.shared.isPopoverVisible {
                            ClipboardMonitor.shared.checkNow()
                        }
                    }
                    return nil // swallow the event
                }

                return Unmanaged.passUnretained(event)
            },
            userInfo: nil
        )

        guard let validTap = tap else {
            print("Devbench: Could not create event tap (needs accessibility permissions)")
            return
        }

        eventTap = validTap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, validTap, 0)
        if let source = runLoopSource {
            CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
        }
    }

    /// Set launch at login via ServiceManagement (macOS 13+)
    func applyLaunchAtLogin() {
        // On macOS 13+ we can use SMAppService
        if #available(macOS 13, *) {
            do {
                let service = SMAppService.mainApp
                if launchAtLogin {
                    try service.register()
                } else {
                    try service.unregister()
                }
            } catch {
                print("Devbench: Failed to update launch-at-login: \(error)")
            }
        }
    }
}

enum ColorSchemePreference: String, CaseIterable, Identifiable {
    case system
    case light
    case dark

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .system: return "System"
        case .light:  return "Light"
        case .dark:   return "Dark"
        }
    }
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Register default settings
        AppSettings.shared.registerGlobalShortcut()

        // Start clipboard monitoring if enabled
        if AppSettings.shared.autoDetectClipboard {
            ClipboardMonitor.shared.startMonitoring()
        }

        // Observe settings changes
        _ = AppSettings.shared.$autoDetectClipboard.sink { enabled in
            if enabled {
                ClipboardMonitor.shared.startMonitoring()
            } else {
                ClipboardMonitor.shared.stopMonitoring()
            }
        }

        _ = AppSettings.shared.$launchAtLogin.sink { _ in
            AppSettings.shared.applyLaunchAtLogin()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        ClipboardMonitor.shared.stopMonitoring()
    }
}

// MARK: - @main App

@main
struct DevbenchApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var settings = AppSettings.shared
    @StateObject private var clipboardMonitor = ClipboardMonitor.shared
    @StateObject private var pythonBridge = PythonBridge.shared

    @State private var selectedTool: String = "Auto-Detect"
    @State private var detectionResult: DetectionResult?
    @State private var isLoading: Bool = false

    var body: some Scene {
        MenuBarExtra {
            VStack(spacing: 0) {
                ContentView(
                    selectedTool: $selectedTool,
                    detectionResult: $detectionResult,
                    isLoading: $isLoading
                )
                .environmentObject(settings)
                .environmentObject(clipboardMonitor)
                .environmentObject(pythonBridge)
                .frame(width: 400, height: 480)
            }
        } label: {
            Image(systemName: "wrench.adjustable")
                .font(.system(size: 14, weight: .medium))
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environmentObject(settings)
                .environmentObject(pythonBridge)
                .frame(width: 450, height: 350)
        }
    }
}