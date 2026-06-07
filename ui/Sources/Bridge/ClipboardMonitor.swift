import Foundation
import AppKit
import Combine

/// Monitors the system clipboard for changes using NSPasteboard polling.
///
/// Polls `NSPasteboard.general.changeCount` every 0.5 seconds.
/// When a change is detected, reads the content and routes it to
/// `PythonBridge.detect()` for auto-detection. Updates the UI via
/// a Combine `@Published` publisher.
@MainActor
class ClipboardMonitor: ObservableObject {
    static let shared = ClipboardMonitor()

    // MARK: - Published State

    /// The last detected content result (published to UI)
    @Published var lastDetectedContent: DetectionResult?

    /// Whether detection is currently in progress
    @Published var isDetecting: Bool = false

    /// Timestamp of the last clipboard change
    @Published var lastChangeDate: Date?

    /// Recent clipboard history (ring buffer, max 10)
    @Published var recentHistory: [ClipboardEntry] = []

    // MARK: - Private Properties

    private let pasteboard = NSPasteboard.general
    private var lastChangeCount: Int
    private var timer: Timer?
    private var cancellables = Set<AnyCancellable>()

    /// Maximum history entries
    private let maxHistory = 10

    /// Minimum interval between detections (debounce)
    private let detectionCooldown: TimeInterval = 0.8
    private var lastDetectionTime: Date = .distantPast

    /// Cooldown to avoid re-triggering on our own copies
    private var lastCopyTimestamp: Date = .distantPast
    private let copyCooldown: TimeInterval = 0.3

    // MARK: - Initialization

    private init() {
        self.lastChangeCount = pasteboard.changeCount
    }

    // MARK: - Public API

    /// Start polling the clipboard
    func startMonitoring() {
        guard timer == nil else { return } // already running

        // Check immediately
        checkClipboard()

        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.checkClipboard()
            }
        }

        // Also listen for NSWorkspace activation notifications
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(applicationDidBecomeActive),
            name: NSApplication.didBecomeActiveNotification,
            object: nil
        )

        print("Devbench ClipboardMonitor: Monitoring started")
    }

    /// Stop polling the clipboard
    func stopMonitoring() {
        timer?.invalidate()
        timer = nil
        NotificationCenter.default.removeObserver(self, name: NSApplication.didBecomeActiveNotification, object: nil)
        print("Devbench ClipboardMonitor: Monitoring stopped")
    }

    /// Force an immediate clipboard check (e.g. when user opens the popover)
    func checkNow() {
        checkClipboard()
    }

    /// Register that we just copied something ourselves (to avoid re-detection)
    func didCopyContent() {
        lastCopyTimestamp = Date()
    }

    // MARK: - Clipboard Detection

    @objc private func applicationDidBecomeActive() {
        checkClipboard()
    }

    private func checkClipboard() {
        let currentChangeCount = pasteboard.changeCount
        guard currentChangeCount != lastChangeCount else { return }

        lastChangeCount = currentChangeCount
        lastChangeDate = Date()

        // Skip if we just copied something ourselves
        if Date().timeIntervalSince(lastCopyTimestamp) < copyCooldown {
            return
        }

        // Read clipboard content
        guard let content = readClipboardContent() else { return }

        // Debounce: don't detect too frequently
        guard Date().timeIntervalSince(lastDetectionTime) >= detectionCooldown else { return }
        lastDetectionTime = Date()

        // Add to history
        addToHistory(content: content)

        // Run detection
        isDetecting = true

        Task {
            do {
                let result = try await PythonBridge.shared.detect(input: content)
                await MainActor.run {
                    self.lastDetectedContent = result
                    self.isDetecting = false
                }
            } catch {
                await MainActor.run {
                    print("Devbench ClipboardMonitor: Detection error — \(error.localizedDescription)")
                    self.isDetecting = false
                }
            }
        }
    }

    /// Read text content from the clipboard
    private func readClipboardContent() -> String? {
        // Try multiple pasteboard types
        let types: [NSPasteboard.PasteboardType] = [
            .string,
            .rtf,
            .rtfd,
            .html,
            .fileURL,
            .tabularText,
            .findPanelSearchOptions,
        ]

        for type in types {
            if let data = pasteboard.data(forType: type) {
                if type == .string || type == .tabularText || type == .findPanelSearchOptions {
                    return String(data: data, encoding: .utf8)
                } else if type == .fileURL {
                    if let url = URL(dataRepresentation: data, relativeTo: nil) {
                        return url.path
                    }
                } else if type == .html || type == .rtf || type == .rtfd {
                    // For rich text, try to extract plain text
                    if let str = String(data: data, encoding: .utf8) {
                        // Strip HTML tags for HTML content
                        if type == .html {
                            return stripHTML(str)
                        }
                        return str
                    }
                }
            }
        }

        // Fallback: just get the string
        return pasteboard.string(forType: .string)
    }

    /// Minimal HTML tag removal for preview purposes
    private func stripHTML(_ html: String) -> String {
        // Simple regex-based stripping for basic HTML
        guard let regex = try? NSRegularExpression(pattern: "<[^>]+>", options: .caseInsensitive) else {
            return html
        }
        let range = NSRange(location: 0, length: html.utf16.count)
        let plain = regex.stringByReplacingMatches(in: html, options: [], range: range, withTemplate: "")
        return plain
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&#39;", with: "'")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - History

    private struct HistoryEntry: Codable {
        let content: String
        let timestamp: Date
        let type: String?
    }

    private func addToHistory(content: String) {
        let entry = ClipboardEntry(
            content: content,
            timestamp: Date(),
            type: nil
        )
        recentHistory.insert(entry, at: 0)
        if recentHistory.count > maxHistory {
            recentHistory = Array(recentHistory.prefix(maxHistory))
        }
    }
}

// MARK: - Clipboard Entry Model

struct ClipboardEntry: Identifiable, Hashable {
    let id = UUID()
    let content: String
    let timestamp: Date
    let type: String?

    var preview: String {
        content.trimmingCharacters(in: .whitespacesAndNewlines)
            .prefix(100)
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\n", with: " ")
        + (content.count > 100 ? "..." : "")
    }

    var relativeTime: String {
        let interval = Date().timeIntervalSince(timestamp)
        if interval < 60 { return "just now" }
        if interval < 3600 { return "\(Int(interval / 60))m ago" }
        if interval < 86400 { return "\(Int(interval / 3600))h ago" }
        return "\(Int(interval / 86400))d ago"
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: ClipboardEntry, rhs: ClipboardEntry) -> Bool {
        lhs.id == rhs.id
    }
}