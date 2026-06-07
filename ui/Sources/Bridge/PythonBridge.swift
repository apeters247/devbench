import Foundation
import Combine

/// Bridge to call the Python `devbench` CLI tool from Swift.
///
/// Uses `Process` to spawn either:
/// 1. A bundled Python framework inside the app bundle
/// 2. The system `python3` as fallback
///
/// Calls `devbench <tool> "<input>"` as a subprocess and parses JSON output.
@MainActor
class PythonBridge: ObservableObject {
    static let shared = PythonBridge()

    // MARK: - Published State

    @Published var isPythonAvailable: Bool = false
    @Published var pythonVersion: String = ""
    @Published var lastError: String?

    // MARK: - Configuration

    /// Path to the bundled Python executable, if any
    private var bundledPythonPath: String? {
        guard let bundlePath = Bundle.main.path(forResource: "python", ofType: nil,
                                                 inDirectory: "Frameworks/Python.framework/Versions/Current/bin") else {
            return nil
        }
        let pythonPath = (bundlePath as NSString).appendingPathComponent("python3")
        return FileManager.default.isExecutableFile(atPath: pythonPath) ? pythonPath : nil
    }

    /// Path to the bundled devbench CLI script
    private var bundledDevbenchPath: String? {
        Bundle.main.path(forResource: "devbench", ofType: nil,
                         inDirectory: "Resources/devbench/bin")
    }

    /// Path to the devbench executable — checks bundle first, then PATH
    private func resolveDevbenchPath() -> String? {
        if let bundled = bundledDevbenchPath {
            return bundled
        }
        // Search PATH
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        task.arguments = ["devbench"]
        let pipe = Pipe()
        task.standardOutput = pipe
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let path = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
            if let path = path, !path.isEmpty, FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        } catch {
            print("Devbench PythonBridge: which devbench failed — \(error)")
        }
        return nil
    }

    /// Resolve the Python interpreter path
    private func resolvePythonPath() -> String {
        if let bundled = bundledPythonPath {
            return bundled
        }
        // Check common locations
        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
        ]
        for path in candidates {
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        return "/usr/bin/python3" // fallback
    }

    // MARK: - Initialization

    private init() {
        checkPythonAvailability()
    }

    private func checkPythonAvailability() {
        let pythonPath = resolvePythonPath()
        let task = Process()
        task.executableURL = URL(fileURLWithPath: pythonPath)
        task.arguments = ["--version"]

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe

        do {
            try task.run()
            task.waitUntilExit()

            if task.terminationStatus == 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let version = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "unknown"
                pythonVersion = version
                isPythonAvailable = true
            } else {
                isPythonAvailable = false
                pythonVersion = ""
                lastError = "Python not found at \(pythonPath)"
            }
        } catch {
            isPythonAvailable = false
            pythonVersion = ""
            lastError = error.localizedDescription
        }
    }

    // MARK: - Run Devbench Tool

    /// Run a devbench tool with the given input and return the user-facing output.
    ///
    /// `detect` is run with `--swift` so the CLI emits the Swift-friendly
    /// envelope; every tool's inner `output` field is unwrapped so the UI never
    /// displays a double-wrapped JSON envelope.
    ///
    /// - Parameters:
    ///   - tool: The CLI subcommand (e.g. "detect", "json", "base64", "cf")
    ///   - input: The input text to process
    /// - Returns: The tool's `output` field as a string
    /// - Throws: `PythonBridgeError` if the process fails or the tool reports an error
    func runTool(tool: String, input: String) async throws -> String {
        guard isPythonAvailable else {
            throw PythonBridgeError.pythonNotAvailable(
                message: lastError ?? "Python interpreter is not available"
            )
        }

        let arguments: [String]
        if tool == DevbenchTool.detect.rawValue {
            arguments = ["detect", "--swift", input]
        } else {
            arguments = [tool, input]
        }

        let rawOutput = try await runDevbench(arguments: arguments)
        return try Self.extractOutput(from: rawOutput)
    }

    /// Run `devbench detect --swift` and decode the Swift-friendly envelope.
    func detect(input: String) async throws -> DetectionResult {
        let rawOutput = try await runDevbench(arguments: ["detect", "--swift", input])

        guard let data = rawOutput.data(using: .utf8) else {
            throw PythonBridgeError.invalidOutput("Could not encode output as UTF-8")
        }

        let decoder = JSONDecoder()
        do {
            var result = try decoder.decode(DetectionResult.self, from: data)
            result.sourceInput = input
            return result
        } catch {
            throw PythonBridgeError.decodingError(
                "Failed to parse detection result: \(error.localizedDescription)\nRaw: \(rawOutput.prefix(500))"
            )
        }
    }

    /// Extract the user-facing `output` field from a devbench JSON envelope.
    ///
    /// If the envelope reports an `error` and has no usable `output`, this
    /// throws so the UI surfaces the failure. Non-envelope text is returned
    /// verbatim as a fallback.
    static func extractOutput(from raw: String) throws -> String {
        guard let data = raw.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return raw
        }

        let output = obj["output"] as? String
        if let error = obj["error"] as? String, !error.isEmpty, (output ?? "").isEmpty {
            throw PythonBridgeError.processError(exitCode: 1, message: error)
        }
        return output ?? raw
    }

    // MARK: - Private

    /// Execute `devbench` as a subprocess and return stdout
    private func runDevbench(arguments: [String]) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            let task = Process()

            // Try devbench executable first, then python3 -m devbench
            if let devbenchPath = resolveDevbenchPath() {
                task.executableURL = URL(fileURLWithPath: devbenchPath)
                task.arguments = arguments
            } else {
                // Fallback: python3 -m devbench
                task.executableURL = URL(fileURLWithPath: resolvePythonPath())
                task.arguments = ["-m", "devbench"] + arguments
            }

            let outputPipe = Pipe()
            let errorPipe = Pipe()
            task.standardOutput = outputPipe
            task.standardError = errorPipe

            // Environment
            var env = ProcessInfo.processInfo.environment
            env["PYTHONUNBUFFERED"] = "1"
            task.environment = env

            task.terminationHandler = { process in
                let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
                let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: outputData, encoding: .utf8) ?? ""
                let errorOutput = String(data: errorData, encoding: .utf8) ?? ""

                if process.terminationStatus == 0 {
                    continuation.resume(returning: output.trimmingCharacters(in: .whitespacesAndNewlines))
                } else {
                    let message = errorOutput.trimmingCharacters(in: .whitespacesAndNewlines)
                        .isEmpty ? output.trimmingCharacters(in: .whitespacesAndNewlines) : errorOutput
                    continuation.resume(throwing: PythonBridgeError.processError(
                        exitCode: process.terminationStatus,
                        message: message
                    ))
                }
            }

            do {
                try task.run()
            } catch {
                continuation.resume(throwing: PythonBridgeError.processError(
                    exitCode: -1,
                    message: "Failed to launch process: \(error.localizedDescription)"
                ))
            }
        }
    }
}

// MARK: - Devbench Tools

/// The real `devbench` CLI subcommands the app can invoke.
enum DevbenchTool: String, CaseIterable {
    case detect
    case json
    case base64
    case jwt
    case hash
    case url
    case timestamp
    case uuid
    case diff
    case cf
    case list
}

// MARK: - Errors

enum PythonBridgeError: LocalizedError {
    case pythonNotAvailable(message: String)
    case processError(exitCode: Int32, message: String)
    case invalidOutput(String)
    case decodingError(String)

    var errorDescription: String? {
        switch self {
        case .pythonNotAvailable(let msg):
            return "Python not available: \(msg)"
        case .processError(let code, let msg):
            return "Process exited with code \(code): \(msg)"
        case .invalidOutput(let msg):
            return "Invalid output: \(msg)"
        case .decodingError(let msg):
            return "Decoding error: \(msg)"
        }
    }
}