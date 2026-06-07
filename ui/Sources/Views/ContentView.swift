import SwiftUI
import Combine

// MARK: - Detection Result Model

/// Decodes the `devbench detect --swift` envelope:
/// `{tool_name, output, error, detection_type, metadata}`.
struct DetectionResult: Identifiable, Decodable {
    var id = UUID().uuidString
    let toolName: String
    let output: String
    let error: String?
    let detectionType: String?
    let metadata: [String: String]?

    /// The original input that was detected. Not part of the wire envelope —
    /// the bridge fills it in after decoding so the UI can echo it back.
    var sourceInput: String = ""

    enum CodingKeys: String, CodingKey {
        case toolName = "tool_name"
        case output
        case error
        case detectionType = "detection_type"
        case metadata
    }

    /// Human-readable label for the detected type.
    var displayType: String {
        detectionType ?? toolName
    }

    /// First-line preview of the tool output.
    var preview: String {
        output.split(separator: "\n").first.map(String.init) ?? output
    }

    /// The UI tool label that best matches this detection.
    var suggestedTool: String {
        let key = displayType.lowercased()
        if key.contains("json") { return "JSON" }
        if key.contains("jwt") { return "JWT" }
        if key.contains("base64") { return "Base64" }
        if key.contains("url") || key.contains("domain") || key.contains("link") { return "URL" }
        if key.contains("timestamp") { return "Timestamp" }
        if key.contains("uuid") { return "UUID" }
        if key.contains("diff") || key.contains("patch") { return "Diff" }
        if key.contains("yaml") || key.contains("toml") || key.contains("ini")
            || key.contains("xml") || key.contains("csv") || key.contains("env")
            || key.contains("config") { return "Convert" }
        return "Auto-Detect"
    }

    var typeIcon: String {
        let key = displayType.lowercased()
        if key.contains("json") || key.contains("yaml") || key.contains("toml")
            || key.contains("config") || key.contains("ini") || key.contains("env") {
            return "curlybraces"
        }
        if key.contains("jwt") || key.contains("base64") {
            return "key.fill"
        }
        if key.contains("url") || key.contains("domain") || key.contains("link") {
            return "link"
        }
        if key.contains("timestamp") {
            return "clock"
        }
        if key.contains("diff") || key.contains("patch") {
            return "doc.text.below.ecg"
        }
        if key.contains("error") || key.contains("crash") {
            return "exclamationmark.triangle.fill"
        }
        return "doc.questionmark"
    }
}

// MARK: - ContentView

struct ContentView: View {
    @Binding var selectedTool: String
    @Binding var detectionResult: DetectionResult?
    @Binding var isLoading: Bool

    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var clipboardMonitor: ClipboardMonitor
    @EnvironmentObject var pythonBridge: PythonBridge

    @State private var inputText: String = ""
    @State private var outputText: String = ""
    @State private var errorMessage: String?
    @State private var runError: String?

    private let tools = ["Auto-Detect", "Convert", "JSON", "Base64", "JWT", "Hash", "URL", "Timestamp", "UUID", "Diff"]

    /// Map a UI tool label to the real `devbench` subcommand it runs.
    private func subcommand(for uiTool: String) -> String {
        switch uiTool {
        case "Auto-Detect": return "detect"
        case "Convert":     return "cf"
        default:            return uiTool.lowercased()
        }
    }

    var body: some View {
        VStack(spacing: 12) {
            // ── Header ──
            headerView

            Divider()

            // ── Auto-Detect Result ──
            if let result = detectionResult {
                detectionBanner(result: result)
            }

            // ── Input Area ──
            inputSection

            // ── Tool Picker ──
            toolPickerSection

            // ── Run Button ──
            runButtonSection

            // ── Results Panel ──
            if !outputText.isEmpty || errorMessage != nil {
                resultsPanel
            }

            Spacer(minLength: 4)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .onAppear {
            // If clipboard monitor has a recent detection, show it
            if clipboardMonitor.lastDetectedContent != nil {
                detectionResult = clipboardMonitor.lastDetectedContent
            }
        }
        .onReceive(clipboardMonitor.$lastDetectedContent) { result in
            if settings.autoDetectClipboard, let result = result {
                detectionResult = result
                inputText = result.sourceInput
                selectedTool = result.suggestedTool
            }
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            Image(systemName: "wrench.adjustable.fill")
                .font(.title3)
                .foregroundColor(.accentColor)
            Text("Devbench")
                .font(.headline)
                .fontWeight(.semibold)
            Spacer()
            Button(action: { NSApplication.shared.activate(ignoringOtherApps: true)
                NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil) }) {
                Image(systemName: "gearshape")
                    .font(.body)
            }
            .buttonStyle(.borderless)
            .help("Settings")

            Button(action: {
                NSApplication.shared.terminate(nil)
            }) {
                Image(systemName: "power")
                    .font(.body)
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.borderless)
            .help("Quit Devbench")
        }
        .padding(.bottom, 2)
    }

    // MARK: - Detection Banner

    private func detectionBanner(result: DetectionResult) -> some View {
        HStack(spacing: 8) {
            Image(systemName: result.typeIcon)
                .font(.title3)
                .foregroundColor(.accentColor)
            VStack(alignment: .leading, spacing: 2) {
                Text(result.displayType.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.caption).fontWeight(.semibold)
                Text(result.preview)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            }
            Spacer()
            Button("Clear") {
                detectionResult = nil
                inputText = ""
                outputText = ""
                errorMessage = nil
            }
            .font(.caption2)
            .buttonStyle(.plain)
            .foregroundColor(.secondary)
        }
        .padding(8)
        .background(Color.accentColor.opacity(0.08))
        .cornerRadius(6)
    }

    // MARK: - Input Section

    private var inputSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Input")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                if !inputText.isEmpty {
                    Button("Paste") {
                        if let str = NSPasteboard.general.string(forType: .string) {
                            inputText = str
                        }
                    }
                    .font(.caption2)
                    .buttonStyle(.plain)
                    .foregroundColor(.accentColor)
                }
            }

            TextEditor(text: $inputText)
                .font(.system(.caption, design: .monospaced))
                .frame(height: 80)
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(Color.secondary.opacity(0.3), lineWidth: 1)
                )
                .cornerRadius(4)
        }
    }

    // MARK: - Tool Picker

    private var toolPickerSection: some View {
        HStack {
            Text("Tool:")
                .font(.caption)
                .foregroundColor(.secondary)
            Picker("", selection: $selectedTool) {
                ForEach(tools, id: \.self) { tool in
                    Text(tool).tag(tool)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(maxWidth: .infinity)
        }
    }

    // MARK: - Run Button

    private var runButtonSection: some View {
        HStack {
            Spacer()
            Button(action: runTool) {
                HStack(spacing: 6) {
                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.6)
                            .frame(width: 12, height: 12)
                    } else {
                        Image(systemName: "play.fill")
                            .font(.caption)
                    }
                    Text(isLoading ? "Running..." : "Run")
                        .font(.caption).fontWeight(.medium)
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 6)
            }
            .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
    }

    // MARK: - Results Panel

    private var resultsPanel: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Results")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                if !outputText.isEmpty {
                    Button(action: {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(outputText, forType: .string)
                    }) {
                        Label("Copy", systemImage: "doc.on.doc")
                            .font(.caption2)
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.accentColor)
                }
            }

            if let error = errorMessage {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                        .font(.caption)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }
                .padding(8)
                .background(Color.red.opacity(0.08))
                .cornerRadius(4)
            }

            ScrollView(.vertical) {
                Text(outputText.isEmpty ? " " : outputText)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(6)
            }
            .frame(maxHeight: 180)
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
            )
            .cornerRadius(4)
        }
    }

    // MARK: - Run Tool

    private func runTool() {
        guard !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        isLoading = true
        outputText = ""
        errorMessage = nil
        runError = nil

        let toolArg = subcommand(for: selectedTool)

        Task {
            do {
                let result = try await pythonBridge.runTool(tool: toolArg, input: inputText)
                await MainActor.run {
                    outputText = result
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

#if DEBUG
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView(
            selectedTool: .constant("Auto-Detect"),
            detectionResult: .constant(nil),
            isLoading: .constant(false)
        )
        .environmentObject(AppSettings.shared)
        .environmentObject(ClipboardMonitor.shared)
        .environmentObject(PythonBridge.shared)
    }
}
#endif