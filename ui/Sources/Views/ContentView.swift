import SwiftUI
import Combine

// MARK: - Detection Result Model

struct DetectionResult: Identifiable {
    var id: String { UUID().uuidString }
    let type: String
    let content: String
    let preview: String
    let confidence: Double
    let suggestedTools: [String]
    let metadata: [String: String]?

    enum CodingKeys: String, CodingKey {
        case type, content, preview, confidence, metadata
        case suggestedTools = "suggested_tools"
    }

    var typeIcon: String {
        switch type.lowercased() {
        case "code", "swift", "python", "javascript", "typescript", "rust", "go", "java":
            return "chevron.left.forwardslash.chevron.right"
        case "error", "error_log", "crash":
            return "exclamationmark.triangle.fill"
        case "text", "plain_text":
            return "doc.text"
        case "json", "yaml", "toml", "config":
            return "curlybraces"
        case "url", "link":
            return "link"
        case "diff", "patch":
            return "doc.text.below.ecg"
        default:
            return "doc.questionmark"
        }
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

    private let tools = ["Auto-Detect", "Format", "Lint", "Explain", "Refactor", "Document"]

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
                inputText = result.content
                selectedTool = result.suggestedTools.first ?? "Auto-Detect"
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
                Text(result.type.replacingOccurrences(of: "_", with: " ").capitalized)
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

        let toolArg = selectedTool.lowercased().replacingOccurrences(of: "-", with: "_")

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