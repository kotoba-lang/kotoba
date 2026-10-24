import SwiftUI

/// Minimal on-device verification screen for `SensingBridge` -- one
/// button per capability, showing raw output. No design polish intended
/// (see `FloorplanLabApp.swift`'s doc comment); this exists only to let
/// a human confirm each real-OS-API call actually works on a physical
/// device.
struct ContentView: View {
    @State private var motionText = "\u{2014}"
    @State private var audioPlayText = "\u{2014}"
    @State private var audioRecordText = "\u{2014}"
    @State private var bleText = "\u{2014}"
    @State private var wifiText = "\u{2014}"
    @State private var isBusy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    NavigationLink("Open 3D floorplan viewer") {
                        FloorplanMapView()
                            .navigationTitle("Floorplan Lab -- 3D viewer")
                            .navigationBarTitleDisplayMode(.inline)
                            .ignoresSafeArea(edges: .bottom)
                    }
                } footer: {
                    Text("WKWebView host for the web/ cljs 3D viewer (kotoba-lang/webgpu render-IR). Streams raw motion/audio/BLE samples from SensingBridge into it; all floorplan estimation runs in the cljs bundle, not in this app.")
                }
                Section {
                    Button("Run ALL (prints to console log)") { Task { await runAllAndLog() } }
                } footer: {
                    Text("For automated verification via `devicectl device process launch --console` -- runs every capability in sequence and prints each result with a unique marker.")
                }
                Section("motion — CMDeviceMotion (cap 234)") {
                    Button("Read 1 motion sample") { Task { await runMotion() } }
                    Text(motionText).font(.footnote).foregroundStyle(.secondary)
                }
                Section("audio-io: play chirp — AVAudioEngine (cap 235)") {
                    Button("Play 2kHz→4kHz chirp, 300ms") { Task { await runAudioPlay() } }
                    Text(audioPlayText).font(.footnote).foregroundStyle(.secondary)
                }
                Section("audio-io: record — AVAudioEngine (cap 235)") {
                    Button("Record 1s") { Task { await runAudioRecord() } }
                    Text(audioRecordText).font(.footnote).foregroundStyle(.secondary)
                }
                Section("ble-scan — CoreBluetooth (cap 236)") {
                    Button("Scan BLE 3s") { Task { await runBleScan() } }
                    Text(bleText).font(.footnote).foregroundStyle(.secondary)
                }
                Section("wifi-info — NEHotspotNetwork (cap 237, best-effort)") {
                    Button("Read Wi-Fi info") { Task { await runWifiInfo() } }
                    Text(wifiText).font(.footnote).foregroundStyle(.secondary)
                }
            }
            .disabled(isBusy)
            .navigationTitle("FloorplanLab SensingBridge")
        }
        .task {
            // Auto-run once on launch so a `devicectl --console` capture
            // can verify all capabilities without any manual tap.
            await runAllAndLog()
        }
    }

    private func runMotion() async {
        isBusy = true
        defer { isBusy = false }
        let values = await SensingBridge.motionRead()
        motionText = values.map { String(format: "%.3f", $0) }.joined(separator: ", ")
    }

    private func runAudioPlay() async {
        isBusy = true
        defer { isBusy = false }
        SensingBridge.audioPlay(frequencyHz: 2_000, durationMs: 300)
        audioPlayText = "played (fire-and-forget, no return value)"
    }

    private func runAudioRecord() async {
        isBusy = true
        defer { isBusy = false }
        let samples = await SensingBridge.audioRecord(durationMs: 1_000)
        let peak = samples.map { abs($0) }.max() ?? 0
        audioRecordText = "\(samples.count) samples, peak amplitude \(String(format: "%.4f", peak))"
    }

    private func runBleScan() async {
        isBusy = true
        defer { isBusy = false }
        let results = await SensingBridge.bleScan(durationMs: 3_000)
        bleText = results.isEmpty
            ? "0 peripherals found"
            : results.map { "\($0.peripheralId): \($0.rssi) dBm" }.joined(separator: "\n")
    }

    private func runWifiInfo() async {
        isBusy = true
        defer { isBusy = false }
        wifiText = await SensingBridge.wifiInfo()
            ?? "nil (expected without Access-WiFi-Information entitlement / granted location permission — see SensingBridge.wifiInfo doc comment)"
    }

    /// Runs every capability once, in sequence, printing each result with
    /// a `[RUN-ALL]` marker so a `devicectl --console` capture can grep
    /// for real-device verification output without any manual tapping.
    private func runAllAndLog() async {
        isBusy = true
        defer { isBusy = false }

        await runMotion()
        print("[RUN-ALL] motion: \(motionText)")

        await runAudioPlay()
        print("[RUN-ALL] audio-play: \(audioPlayText)")

        await runAudioRecord()
        print("[RUN-ALL] audio-record: \(audioRecordText)")

        await runBleScan()
        print("[RUN-ALL] ble-scan: \(bleText.replacingOccurrences(of: "\n", with: " | "))")

        await runWifiInfo()
        print("[RUN-ALL] wifi-info: \(wifiText)")

        print("[RUN-ALL] DONE")
    }
}

#Preview {
    ContentView()
}
