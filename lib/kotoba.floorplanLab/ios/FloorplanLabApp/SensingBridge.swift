import Foundation
import CoreMotion
import CoreBluetooth
import AVFoundation
import NetworkExtension
import CoreLocation

/// `SensingBridge` -- the native shim ADR-2607140600 section 2 calls for:
/// it calls real CoreMotion / CoreBluetooth / AVAudioEngine / NEHotspotNetwork
/// APIs and returns whatever they hand back, in a fixed shape, and does
/// NOTHING else. Specifically this file:
///
///   - performs NO capability/permission-policy decisions (whether a call
///     is "allowed" is entirely a `.kotoba`/CLJC-side concern, per
///     `kotoba.sensing-host`'s driver-injection doc and ADR-2607030900's
///     `aiueos-device-provider` "policy stays on the other side of the
///     boundary" precedent),
///   - performs NO rate limiting, NO persistence, NO sensor fusion,
///     NO filtering/smoothing beyond what the OS API itself already does,
///   - is the DRIVER INJECTION TARGET described in
///     `src/floorplan_lab/sensing_bridge.cljk`'s docstring (the mirrored
///     `{:motion-read :audio-play :audio-record :ble-scan :wifi-info}`
///     driver-map contract) -- a future bridge from this Swift code back
///     into that CLJC driver map (WKWebView JS bridge, XPC, or similar)
///     is out of this file's scope; this file only proves the OS-API
///     half works.
///
/// Every function's OUTPUT SHAPE mirrors `kotoba.sensing-host`'s 5 ops
/// (motion-read / audio-play / audio-record / ble-scan / wifi-info)
/// documented in `orgs/kotoba-lang/kotoba/src/kotoba/sensing_host.cljc`.
enum SensingBridge {

    // MARK: - motion (CoreMotion `CMDeviceMotion`, capability id 234)

    private static let motionManager = CMMotionManager()

    /// One `CMDeviceMotion` sample as a flat 9-value array: `[ax, ay, az,
    /// gx, gy, gz, mx, my, mz]` -- matching `kotoba.sensing-host/read-motion`'s
    /// documented shape exactly.
    ///
    ///   - `ax/ay/az` = `userAcceleration` (m/s^2, gravity already
    ///     subtracted by CoreMotion's sensor fusion) -- the more useful
    ///     default for dead-reckoning double integration than raw
    ///     accelerometer + gravity, and still a "the OS already computed
    ///     this" read rather than judgment on this file's part.
    ///   - `gx/gy/gz` = `rotationRate` (rad/s).
    ///   - `mx/my/mz` = `magneticField.field` (µT; `.uncalibrated` accuracy
    ///     is expected/fine since the default reference frame below
    ///     doesn't fuse magnetometer into attitude -- the raw field is
    ///     still populated).
    ///
    /// Returns 9 zeros if `CMDeviceMotion` is unavailable (simulator, or
    /// a device without the sensor) -- this mirrors, but is NOT identical
    /// to, `kotoba.sensing-host`'s "0 samples" stub (this function always
    /// returns exactly 9 values by design, since it moves one fixed-width
    /// sample rather than a variable-length buffer; an all-zero sample is
    /// the honest "nothing real available" answer for this shape).
    static func motionRead() async -> [Double] {
        guard motionManager.isDeviceMotionAvailable else {
            return Array(repeating: 0, count: 9)
        }
        return await withCheckedContinuation { continuation in
            var resumed = false
            motionManager.deviceMotionUpdateInterval = 1.0 / 60.0
            motionManager.startDeviceMotionUpdates(to: .main) { motion, _ in
                guard !resumed else { return }
                resumed = true
                motionManager.stopDeviceMotionUpdates()
                guard let motion else {
                    continuation.resume(returning: Array(repeating: 0, count: 9))
                    return
                }
                let a = motion.userAcceleration
                let g = motion.rotationRate
                let m = motion.magneticField.field
                continuation.resume(returning: [a.x, a.y, a.z, g.x, g.y, g.z, m.x, m.y, m.z])
            }
        }
    }

    // MARK: - audio-io (AVAudioEngine, capability id 235)

    private static let audioEngine = AVAudioEngine()
    private static let playerNode = AVAudioPlayerNode()
    private static var playerAttached = false
    private static let sampleRate = 44_100.0

    /// Plays a linear-sweep chirp (FREQUENCYHZ -> 2*FREQUENCYHZ) for
    /// DURATIONMS via `AVAudioEngine` + `AVAudioPlayerNode`. This is the
    /// outgoing pulse for the acoustic-sonar capability
    /// (`floorplan-lab.sonar`'s chirp generator, played for real instead
    /// of synthesized in CLJC) -- this function only plays the tone;
    /// cross-correlating a recorded echo against it is entirely a
    /// `.kotoba`/CLJC-side concern (`sonar/cross-correlate`).
    ///
    /// Returns the exact PCM samples it just played (`@discardableResult`
    /// so the original fire-and-forget call sites don't need to change).
    /// This is NOT new sonar logic -- it is the same linear-sweep buffer
    /// this function already synthesizes internally to feed the player
    /// node, now also handed back so a caller (`FloorplanMapView`) can
    /// forward the SAME samples to `floorplan-lab.sonar/estimate-wall-distance-m`
    /// (browser/cljs side) for cross-correlation, instead of that caller
    /// re-deriving the sweep from scratch and risking the two copies
    /// drifting apart.
    @discardableResult
    static func audioPlay(frequencyHz: Double, durationMs: Int) -> [Float] {
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playAndRecord, options: [.defaultToSpeaker, .mixWithOthers])
        try? session.setActive(true)

        let durationSec = Double(durationMs) / 1000.0
        let frameCount = AVAudioFrameCount(sampleRate * durationSec)
        guard frameCount > 0,
              let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount),
              let channel = buffer.floatChannelData?[0]
        else { return [] }
        buffer.frameLength = frameCount

        let startFreq = frequencyHz
        let endFreq = frequencyHz * 2
        var samples = [Float](repeating: 0, count: Int(frameCount))
        for frame in 0..<Int(frameCount) {
            let t = Double(frame) / sampleRate
            let instantaneousFreq = startFreq + (endFreq - startFreq) * (t / durationSec)
            let value = Float(sin(2 * Double.pi * instantaneousFreq * t))
            channel[frame] = value
            samples[frame] = value
        }

        if !playerAttached {
            audioEngine.attach(playerNode)
            audioEngine.connect(playerNode, to: audioEngine.mainMixerNode, format: format)
            playerAttached = true
        }
        if !audioEngine.isRunning {
            try? audioEngine.start()
        }
        playerNode.scheduleBuffer(buffer, at: nil, options: .interrupts)
        playerNode.play()

        return samples
    }

    /// Records DURATIONMS milliseconds of mono PCM audio from the input
    /// node's tap and returns the raw `Float` samples completely
    /// unprocessed (no filtering, no gain, no windowing). This is the
    /// echo-capture half of `audio-io` for acoustic sonar -- finding the
    /// echo delay in this buffer via cross-correlation against the
    /// chirp played by `audioPlay` is entirely a `.kotoba`/CLJC-side
    /// concern (`floorplan-lab.sonar/cross-correlate`).
    static func audioRecord(durationMs: Int) async -> [Float] {
        // Recording (unlike playback) requires explicit mic permission --
        // without this, `audioEngine.start()` below fails silently and the
        // tap never receives a single buffer, which previously showed up
        // as an indistinguishable "0 samples" result on a real device.
        let granted = await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
        guard granted else {
            print("[SensingBridge] audioRecord: microphone permission denied")
            return []
        }

        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playAndRecord, options: [.defaultToSpeaker, .mixWithOthers])
        try? session.setActive(true)

        // The engine's node graph (including the input bus's negotiated
        // format) only latches correctly when reconfigured from a stopped
        // state -- if `audioPlay` already started the engine for
        // output-only, `inputNode.outputFormat(forBus:)` reports a stale
        // sampleRate of 0 until we stop, re-touch the graph, and restart.
        if audioEngine.isRunning {
            audioEngine.stop()
        }

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        guard recordingFormat.sampleRate > 0 else {
            print("[SensingBridge] audioRecord: input node reports sampleRate 0, aborting")
            return []
        }

        let lock = NSLock()
        var samples: [Float] = []

        return await withCheckedContinuation { continuation in
            inputNode.installTap(onBus: 0, bufferSize: 1_024, format: recordingFormat) { buffer, _ in
                guard let channelData = buffer.floatChannelData?[0] else { return }
                lock.lock()
                samples.append(contentsOf: UnsafeBufferPointer(start: channelData, count: Int(buffer.frameLength)))
                lock.unlock()
            }
            audioEngine.prepare()
            do {
                try audioEngine.start()
            } catch {
                print("[SensingBridge] audioRecord: audioEngine.start() failed: \(error)")
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + Double(durationMs) / 1000.0) {
                inputNode.removeTap(onBus: 0)
                lock.lock()
                let result = samples
                lock.unlock()
                continuation.resume(returning: result)
            }
        }
    }

    // MARK: - ble-scan (CoreBluetooth, capability id 236)

    /// Read-only BLE scan helper. A `class` (not a free function) because
    /// `CBCentralManagerDelegate` requires a reference-type conformer --
    /// this is the ONE place in this file where that's unavoidable. It
    /// still performs no judgment: `didDiscover` just records
    /// (peripheral id, RSSI) pairs, exactly as `kotoba.sensing-host/scan-ble`'s
    /// `{:id :rssi}` shape expects, with no pairing, no GATT
    /// service/characteristic discovery, no writes.
    private final class BLEScanner: NSObject, CBCentralManagerDelegate {
        private var central: CBCentralManager?
        private let lock = NSLock()
        private var results: [String: Int] = [:]
        private var continuation: CheckedContinuation<[(peripheralId: String, rssi: Int)], Never>?

        func scan(durationMs: Int) async -> [(peripheralId: String, rssi: Int)] {
            await withCheckedContinuation { continuation in
                self.continuation = continuation
                self.results = [:]
                self.central = CBCentralManager(delegate: self, queue: nil)
                DispatchQueue.main.asyncAfter(deadline: .now() + Double(durationMs) / 1000.0) { [weak self] in
                    self?.finish()
                }
            }
        }

        func centralManagerDidUpdateState(_ central: CBCentralManager) {
            if central.state == .poweredOn {
                central.scanForPeripherals(
                    withServices: nil,
                    options: [CBCentralManagerScanOptionAllowDuplicatesKey: true]
                )
            } else {
                // Bluetooth off / unauthorized / unsupported -- honest
                // "0 peripherals found" answer, no judgment about why.
                finish()
            }
        }

        func centralManager(
            _ central: CBCentralManager,
            didDiscover peripheral: CBPeripheral,
            advertisementData: [String: Any],
            rssi RSSI: NSNumber
        ) {
            lock.lock()
            results[peripheral.identifier.uuidString] = RSSI.intValue
            lock.unlock()
        }

        private func finish() {
            guard let continuation else { return }
            self.continuation = nil
            central?.stopScan()
            lock.lock()
            let entries = results.map { (peripheralId: $0.key, rssi: $0.value) }
            lock.unlock()
            continuation.resume(returning: entries)
        }
    }

    private static let bleScanner = BLEScanner()

    /// Scans for DURATIONMS milliseconds and returns every discovered
    /// peripheral's (id, RSSI), matching
    /// `kotoba.sensing-host/scan-ble`'s `{:id :rssi}` shape -- RSSI ->
    /// distance conversion (`floorplan-lab.ble/rssi->distance-m`) and
    /// trilateration are entirely a `.kotoba`/CLJC-side concern.
    static func bleScan(durationMs: Int) async -> [(peripheralId: String, rssi: Int)] {
        await bleScanner.scan(durationMs: durationMs)
    }

    // MARK: - wifi-info (NEHotspotNetwork, capability id 237)

    /// Best-effort read of the currently-connected Wi-Fi network's info
    /// via `NEHotspotNetwork.fetchCurrent`.
    ///
    /// **iOS CONSTRAINT (see ADR-2607140600's `wifi-info` row and
    /// `kotoba.sensing-host`'s doc comment "also the honest iOS-constrained
    /// default"): there is NO raw Wi-Fi RSSI scan API available to
    /// third-party iOS apps.** This can only read metadata about the
    /// network the device is ALREADY connected to, and even that is
    /// gated behind either the (Apple-Developer-Portal-gated) "Access
    /// WiFi Information" entitlement, or CoreLocation "When In Use"
    /// authorization. This build does not assume the entitlement is
    /// configured (out of scope: "no Apple Developer account login /
    /// certificate creation" per this task); it best-effort requests
    /// location authorization, but on first launch that authorization
    /// will not have been granted synchronously by the time
    /// `fetchCurrent` runs, so **`nil` on first call is the expected,
    /// honest result**, not a bug to route around. A caller that needs
    /// this to succeed must grant Location "While Using" first and call
    /// again.
    static func wifiInfo() async -> String? {
        let locationManager = CLLocationManager()
        if locationManager.authorizationStatus == .notDetermined {
            locationManager.requestWhenInUseAuthorization()
        }

        return await withCheckedContinuation { continuation in
            NEHotspotNetwork.fetchCurrent { network in
                guard let network else {
                    continuation.resume(returning: nil)
                    return
                }
                let signalPercent = Int((network.signalStrength * 100).rounded())
                continuation.resume(
                    returning: "\(network.ssid) (signal: \(signalPercent)%, secure: \(network.isSecure))"
                )
            }
        }
    }
}
