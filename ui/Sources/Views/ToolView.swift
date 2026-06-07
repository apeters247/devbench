import SwiftUI
import Combine

/// Individual tool view component with input field, run button, output panel, and error display.
struct ToolView: View {
    let toolName: String
    let toolIcon: String

    @EnvironmentObject var pythonBridge: PythonBridge

    @State private var inputText: String = ""
    @State private var outputText: String = ""
    @State private var errorMessage: String?
    @State private var isLoading: Bool = false
    @State private var showCopiedFeedback: Bool = false

    private let pasteboard = NSPasteboard.general

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // ── Tool Header ──
            toolHeader

            // ── Input Text Field (multi-line, monospace) ──
            inputSection

            // ── Run Button ──
            HStack {
                Spacer()
                runButton
            }

            // ── Output Panel ──
            if !outputText.isEmpty || errorMessage != nil {
                outputSection
            }

            Spacer(minLength: 4)
        }
        .padding(12)
    }

    // MARK: - Tool Header

    private var toolHeader: some View {
        HStack(spacing: 8) {
            Image(systemName: toolIcon)
                .font(.title3)
                .foregroundColor(.accentColor)
            Text(toolName)
                .font(.headline)
                .fontWeight(.semibold)
            Spacer()
        }
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
                    Button(action: {
                        inputText = ""
                    }) {
                        Text("Clear")
                            .font(.caption2)
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.secondary)

                    Button(action: {
                        if let str = pasteboard.string(forType: .string) {
                            inputText = str
                        }
                    }) {
                        Text("Paste")
                            .font(.caption2)
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.accentColor)
                }
            }

            TextEditor(text: $inputText)
                .font(.system(.body, design: .monospaced))
                .frame(minHeight: 80, maxHeight: 150)
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Color.secondary.opacity(0.3), lineWidth: 1)
                )
                .cornerRadius(6)
                .disableAutocorrection(true)

            // Character count hint
            if !inputText.isEmpty {
                Text("\(inputText.count) characters")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }

    // MARK: - Run Button

    private var runButton: some View {
        Button(action: runTool) {
            HStack(spacing: 6) {
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.7)
                        .frame(width: 14, height: 14)
                } else {
                    Image(systemName: "play.fill")
                        .font(.caption)
                }
                Text(isLoading ? "Running..." : "Run")
                    .font(.subheadline).fontWeight(.medium)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 8)
        }
        .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
        .buttonStyle(.borderedProminent)
        .keyboardShortcut(.return, modifiers: .command)
    }

    // MARK: - Output Section

    private var outputSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Output")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                if !outputText.isEmpty {
                    Button(action: copyToClipboard) {
                        HStack(spacing: 4) {
                            Image(systemName: showCopiedFeedback ? "checkmark" : "doc.on.doc")
                                .font(.caption2)
                            Text(showCopiedFeedback ? "Copied!" : "Copy")
                                .font(.caption2)
                        }
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.accentColor)
                    .animation(.easeInOut(duration: 0.2), value: showCopiedFeedback)
                }
            }

            // Error display
            if let error = errorMessage {
                HStack(alignment: .top, spacing: 6) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                        .font(.caption)
                    ScrollView(.vertical) {
                        Text(error)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundColor(.red)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 80)
                }
                .padding(10)
                .background(Color.red.opacity(0.08))
                .cornerRadius(6)
            }

            // Output text panel
            ScrollView(.vertical) {
                Text(outputText.isEmpty ? " " : outputText)
                    .font(.system(.callout, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(8)
            }
            .frame(minHeight: 100, maxHeight: 250)
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
            )
            .cornerRadius(6)
        }
    }

    // MARK: - Actions

    private func runTool() {
        guard !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        isLoading = true
        outputText = ""
        errorMessage = nil

        let toolArg = toolName.lowercased().replacingOccurrences(of: " ", with: "_")

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

    private func copyToClipboard() {
        pasteboard.clearContents()
        pasteboard.setString(outputText, forType: .string)

        showCopiedFeedback = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            showCopiedFeedback = false
        }
    }
}

// MARK: - Preview

#if DEBUG
struct ToolView_Previews: PreviewProvider {
    static var previews: some View {
        ToolView(
            toolName: "Format",
            toolIcon: "doc.text.magnifyingglass"
        )
        .environmentObject(PythonBridge.shared)
        .frame(width: 400, height: 500)
    }
}
#endif