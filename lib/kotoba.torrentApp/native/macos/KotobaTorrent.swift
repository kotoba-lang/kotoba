import AppKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate {
  let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 720, height: 460),
                        styleMask: [.titled, .closable, .miniaturizable, .resizable],
                        backing: .buffered, defer: false)
  let titleLabel = NSTextField(labelWithString: "Kotoba Torrent")
  let fileLabel = NSTextField(wrappingLabelWithString: "Open a legal .torrent file to begin.")
  let progress = NSProgressIndicator()
  let status = NSTextField(wrappingLabelWithString: "Idle")
  let openButton = NSButton(title: "Open .torrent…", target: nil, action: nil)
  let stopButton = NSButton(title: "Stop", target: nil, action: nil)
  var task: Process?

  func applicationDidFinishLaunching(_ notification: Notification) {
    titleLabel.font = .systemFont(ofSize: 28, weight: .bold)
    progress.minValue = 0; progress.maxValue = 1; progress.doubleValue = 0
    openButton.target = self; openButton.action = #selector(pickFile)
    stopButton.target = self; stopButton.action = #selector(stopDownload); stopButton.isEnabled = false
    let buttons = NSStackView(views: [openButton, stopButton]); buttons.orientation = .horizontal; buttons.spacing = 10
    let stack = NSStackView(views: [titleLabel, fileLabel, progress, status, buttons])
    stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 18
    stack.translatesAutoresizingMaskIntoConstraints = false
    window.contentView?.addSubview(stack)
    NSLayoutConstraint.activate([
      stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 28),
      stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -28),
      stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 28),
      progress.widthAnchor.constraint(equalTo: stack.widthAnchor)
    ])
    window.title = "Kotoba Torrent"; window.center(); window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    if CommandLine.arguments.count > 1 {
      let candidate = CommandLine.arguments[1]
      if candidate.hasSuffix(".torrent") { begin(URL(fileURLWithPath: candidate)) }
    }
  }

  func application(_ sender: NSApplication, openFiles filenames: [String]) {
    if let path = filenames.first, path.hasSuffix(".torrent") { begin(URL(fileURLWithPath: path)) }
    sender.reply(toOpenOrPrint: .success)
  }

  @objc func pickFile() {
    let panel = NSOpenPanel(); panel.allowsMultipleSelection = false; panel.canChooseDirectories = false
    panel.allowedFileTypes = ["torrent"]
    if panel.runModal() == .OK, let url = panel.url { begin(url) }
  }

  @objc func stopDownload() {
    task?.interrupt(); task = nil; status.stringValue = "Stopped"; stopButton.isEnabled = false; openButton.isEnabled = true
  }

  func begin(_ torrent: URL) {
    guard task == nil else { return }
    let output = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
      .appendingPathComponent("KotobaTorrent", isDirectory: true)
    try? FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    fileLabel.stringValue = torrent.lastPathComponent
    status.stringValue = "Starting…"; progress.doubleValue = 0; openButton.isEnabled = false; stopButton.isEnabled = true
    let p = Process(); let pipe = Pipe()
    p.currentDirectoryURL = URL(fileURLWithPath: ProcessInfo.processInfo.environment["KOTOBA_TORRENT_APP_DIR"] ?? FileManager.default.currentDirectoryPath)
    p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    p.arguments = ["kbb", "-M", "-m", "kotoba.torrent-app.download", torrent.path, output.path]
    p.standardOutput = pipe; p.standardError = pipe
    pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
      let data = handle.availableData
      guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
      for line in text.split(separator: "\n") { self?.handleEvent(String(line)) }
    }
    p.terminationHandler = { [weak self] process in DispatchQueue.main.async {
      self?.task = nil; self?.openButton.isEnabled = true; self?.stopButton.isEnabled = false
      if process.terminationStatus != 0 { self?.status.stringValue = "Download failed" }
    }}
    do { try p.run(); task = p } catch { status.stringValue = error.localizedDescription; openButton.isEnabled = true; stopButton.isEnabled = false }
  }

  func handleEvent(_ line: String) {
    guard let data = line.data(using: .utf8),
          let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
    DispatchQueue.main.async { [weak self] in
      guard let self = self else { return }
      switch event["event"] as? String {
      case "torrent/start": self.status.stringValue = "Connected to \(event["peers"] ?? 0) peers"
      case "torrent/progress":
        let done = event["bytes"] as? Double ?? 0, total = event["total"] as? Double ?? 1
        self.progress.doubleValue = done / total
        self.status.stringValue = String(format: "%.1f%% — %.1f / %.1f MB", done / total * 100, done / 1_000_000, total / 1_000_000)
      case "torrent/complete": self.progress.doubleValue = 1; self.status.stringValue = "Complete: \(event["path"] ?? "")"
      case "torrent/error": self.status.stringValue = "Error: \(event["message"] ?? "unknown")"
      default: break
      }
    }
  }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
