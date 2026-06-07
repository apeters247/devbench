import SwiftUI
import ServiceManagement

/// Preferences / Settings window for Devbench.
struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings

    @State private var isRecordingShortcut: Bool = false
    @State private var recordedKeyCode: UInt16 = 0
    @State private var recordedModifiers: UInt = 0

    private var shortcutDisplay: String {
        if isRecordingShortcut {
            return "Press a key combination..."
        }
        let mods = NSEvent.ModifierFlags(rawValue: settings.globalShortcutModifiers)
        var parts: [String] = []
        if mods.contains(.command)  { parts.append("⌘") }
        if mods.contains(.shift)    { parts.append("⇧") }
        if mods.contains(.option)   { parts.append("⌥") }
        if mods.contains(.control)  { parts.append("⌃") }
        if let chars = keyCodeToString(settings.globalShortcutKeyCode) {
            parts.append(chars)
        }
        return parts.isEmpty ? "Not set" : parts.joined()
    }

    var body: some View {
        Form {
            // ── Clipboard Section ──
            Section {
                Toggle(isOn: $settings.autoDetectClipboard) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Auto-detect clipboard")
                            .font(.body)
                        Text("Automatically detect content when copied")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            } header: {
                Label("Clipboard", systemImage: "doc.on.clipboard")
                    .font(.headline)
            }

            Divider()

            // ── Shortcut Section ──
            Section {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Global shortcut")
                            .font(.body)
                        Text("Show/hide the menubar popover")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()

                    Button(action: {
                        if isRecordingShortcut {
                            // Cancel recording
                            isRecordingShortcut = false
                        } else {
                            startRecording()
                        }
                    }) {
                        Text(shortcutDisplay)
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(isRecordingShortcut ? .red : .primary)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(isRecordingShortcut ? Color.red : Color.secondary.opacity(0.4), lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)

                    if !isRecordingShortcut && settings.globalShortcutKeyCode != 0 {
                        Button(action: {
                            settings.globalShortcutKeyCode = 0
                            settings.globalShortcutModifiers = 0
                        }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                        .help("Clear shortcut")
                    }
                }
            } header: {
                Label("Shortcut", systemImage: "keyboard")
                    .font(.headline)
            }

            Divider()

            // ── General Section ──
            Section {
                Toggle(isOn: $settings.launchAtLogin) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Launch at login")
                            .font(.body)
                        Text("Automatically start Devbench when you log in")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Picker(selection: $settings.colorScheme) {
                    ForEach(ColorSchemePreference.allCases) { scheme in
                        Text(scheme.displayName).tag(scheme)
                    }
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Theme")
                            .font(.body)
                        Text("Choose light, dark, or system appearance")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .pickerStyle(.radioGroup)

            } header: {
                Label("General", systemImage: "gearshape")
                    .font(.headline)
            }

            Spacer()

            // Footer
            HStack {
                Spacer()
                VStack(spacing: 2) {
                    Text("Devbench v1.0")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("Built with SwiftUI • macOS 14+")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }
            .padding(.top, 8)
        }
        .padding(20)
        .frame(minWidth: 420, minHeight: 320)
    }

    // MARK: - Shortcut Recording

    private func startRecording() {
        isRecordingShortcut = true
        recordedKeyCode = 0
        recordedModifiers = 0

        // Create a local event monitor to capture the next key press
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            guard self.isRecordingShortcut else { return event }

            let keyCode = event.keyCode
            let mods = event.modifierFlags.intersection([.command, .shift, .option, .control])

            // Ignore modifier-only presses
            guard keyCode != 0x38, // Shift
                  keyCode != 0x3B, // Control
                  keyCode != 0x3A, // Option
                  keyCode != 0x37  else { // Command
                return nil
            }

            self.recordedKeyCode = keyCode
            self.recordedModifiers = mods.rawValue

            // Apply to settings
            self.settings.globalShortcutKeyCode = keyCode
            self.settings.globalShortcutModifiers = mods.rawValue

            self.isRecordingShortcut = false
            return nil // swallow the event
        }
    }

    /// Convert key code to a human-readable string
    private func keyCodeToString(_ code: UInt16) -> String? {
        // Common key codes
        switch code {
        case 0x31: return "Space"
        case 0x24: return "Return"
        case 0x30: return "Tab"
        case 0x35: return "Escape"
        case 0x33: return "Delete"
        case 0x7E: return "↑"
        case 0x7D: return "↓"
        case 0x7B: return "←"
        case 0x7C: return "→"
        case 0x74: return "F1"
        case 0x75: return "F2"
        case 0x76: return "F3"
        case 0x77: return "F4"
        case 0x78: return "F5"
        case 0x79: return "F6"
        case 0x7A: return "F7"
        case 0x7F: return "F8"
        case 0x80: return "F9"
        case 0x81: return "F10"
        case 0x82: return "F11"
        case 0x83: return "F12"
        default:
            // Try to get characters from a keyboard event
            if let event = NSEvent(keyEvent: .keyDown,
                                   location: .zero,
                                   modifierFlags: [],
                                   timestamp: 0,
                                   windowNumber: 0,
                                   context: nil,
                                   characters: "",
                                   charactersIgnoringModifiers: "",
                                   isARepeat: false,
                                   keyCode: code) {
                return event.charactersIgnoringModifiers?.uppercased()
            }
            return nil
        }
    }
}

// MARK: - Preview

#if DEBUG
struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView()
            .environmentObject(AppSettings.shared)
            .frame(width: 450, height: 350)
    }
}
#endif