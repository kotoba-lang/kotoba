# kotoba-lang/floorplan-lab

Algorithms for estimating a building's interior floorplan (room shape /
wall outline) from phone-sensor data: dead-reckoning from motion samples,
acoustic chirp-echo sonar, and BLE RSSI trilateration, fused into a wall
point cloud and a simplified room polygon.

Design: `90-docs/adr/2607140600-indoor-floorplan-lab-compiler-phase3-device-capability-bridge.md`
in [`com-junkawasaki/root`](https://github.com/com-junkawasaki/root)
(status `proposed`, Phase 3a implementation authorized by the repo owner).

## Scope: algorithm-only, no real sensors (yet) — except `ios/`

**`src/`/`test/` (the `.cljc` algorithms) contain no native code and talk
to no real sensor.** Every algorithm there operates on plain data
structures (motion sample seqs, PCM float buffers, BLE `{:id :rssi}`
readings) and is verified against **synthetic/mock data** — a synthetic
square-room walk for dead-reckoning, a synthetic chirp + known-delay
echo for sonar, and known beacon positions + exact geometric distances
for BLE trilateration. No CoreMotion / CoreBluetooth / AVAudioEngine /
any other native OS API is called anywhere under `src/`/`test/`, by
design (see the ADR's "native shim" section — that boundary was, at
first-increment scaffold time, explicitly out of this repo's scope).

**`ios/` is the native shim** the ADR called out as a separate,
explicitly-authorized increment (owner authorization recorded
2026-07-13) — see the `ios/` section below for what it actually calls
and what it deliberately does not do.

Real-device connection is a **driver injection point**, not a rewrite:
`src/floorplan_lab/sensing_bridge.cljk` defines the driver-map contract
(mirroring `kotoba.sensing-host`'s shape) that a real native shim would
implement; wiring in a real driver there does not require touching
`motion.cljc` / `sonar.cljc` / `ble.cljc` / `fusion.cljc` at all.

## A discrepancy worth knowing about

`sensing_bridge.cljc`'s docstring has the full account, but the short
version: the task that scaffolded this repo was told
`kotoba-lang/device` already registered `:motion`/`:audio-io`/
`:ble-scan`/`:wifi-info` capability tokens wired to
`kotoba-lang/kotoba`'s `kotoba.sensing-host`. Reading the actual
`device.cljc` source at scaffold time showed this is **not** true —
`device` only has `:bluetooth`/`:wifi`/`:display`/`:geolocation`/
`:camera`. `kotoba-core-contracts` (capability ids 234-237) and
`kotoba.sensing-host` (the deterministic-stub driver-dispatch layer) do
exist and are real; the `device`-side integration (ADR-2607140600
section 3) does not. This repo works around that with a locally-defined
driver contract that mirrors `kotoba.sensing-host`'s shape instead of
depending on it directly (see `sensing_bridge.cljc` for the full
reasoning, including why this repo avoids a direct dependency on the
much-heavier `kotoba-lang/kotoba` repo).

## Algorithms

- **`floorplan-lab.motion`** — dead-reckoning: integrates a walking
  trajectory (position + heading) from accelerometer + gyroscope
  samples. Naive double integration (semi-implicit Euler), explicitly
  not a Kalman filter.
- **`floorplan-lab.sonar`** — chirp-echo acoustic sonar: generates a
  linear-sweep chirp, cross-correlates it against a recorded buffer to
  find the round-trip echo delay, converts to a wall distance via
  time-of-flight at the speed of sound (`343 m/s` default).
- **`floorplan-lab.ble`** — BLE RSSI trilateration: converts RSSI to
  distance via the free-space log-distance path-loss model, then
  trilaterates a 2D position from >= 3 known-position beacons via linear
  least squares.
- **`floorplan-lab.fusion`** — combines the above: BLE-corrects a
  dead-reckoning pose (simple weighted average, not a Kalman gain),
  projects sonar readings into world-frame wall points along the
  walker's heading, and estimates a room outline as the convex hull of
  the collected wall points.
- **`floorplan-lab.sensing-bridge`** — the driver injection point
  (mirrors `kotoba.sensing-host`'s driver-map contract) plus a
  `kotoba.lang.device/IDevice` adapter, this repo's one dependency
  (`kotoba-lang/device`).

## `ios/` — the native sensing shim

`ios/` is a native iOS app target (`xcodegen` spec: `ios/project.yml`,
bundle id `dev.kotoba-lang.FloorplanLab`, iOS 17+, generated project
`FloorplanLab.xcodeproj` — not checked in, run `xcodegen generate` under
`ios/` to produce it) whose one job is `ios/FloorplanLabApp/SensingBridge.swift`:
5 functions/class that call the **real** OS sensing APIs and return raw
results, mirroring `kotoba.sensing-host`'s op shapes byte-for-byte
(`orgs/kotoba-lang/kotoba/src/kotoba/sensing_host.cljc`):

- `SensingBridge.motionRead() async -> [Double]` — one `CMDeviceMotion`
  sample (`CoreMotion`) as `[ax,ay,az, gx,gy,gz, mx,my,mz]` (accel =
  `userAcceleration`, gyro = `rotationRate`, mag = `magneticField.field`).
- `SensingBridge.audioPlay(frequencyHz:durationMs:)` — plays a
  linear-sweep chirp (`AVAudioEngine`/`AVAudioPlayerNode`), the sonar
  pulse.
- `SensingBridge.audioRecord(durationMs:) async -> [Float]` — records
  raw PCM from the input node's tap, the sonar echo capture.
- `SensingBridge.bleScan(durationMs:) async -> [(peripheralId: String, rssi: Int)]`
  — a `CoreBluetooth` `CBCentralManager` scan (RSSI read-only, no
  pairing/GATT writes).
- `SensingBridge.wifiInfo() async -> String?` — best-effort
  `NEHotspotNetwork.fetchCurrent` read of the currently-connected
  network; **iOS has no raw Wi-Fi RSSI scan API for third-party apps**,
  so `nil` (missing entitlement / location permission not yet granted)
  is the expected, honest answer on most builds, not a bug — see the
  function's doc comment.

**Same judgment-free-shim boundary as `sensing_bridge.cljc`'s docstring
and ADR-2607030900's `aiueos-device-provider` precedent**: `SensingBridge`
performs no capability/permission decisions, no rate limiting, no
persistence, no sensor fusion. It is the concrete implementation of the
driver contract `sensing_bridge.cljc` already defines
(`{:motion-read :audio-play :audio-record :ble-scan :wifi-info}`) —
wiring `SensingBridge`'s output into that CLJC driver map (WKWebView JS
bridge, XPC, or similar) is the next increment, not done here (see
"Future work" below).

`ios/FloorplanLabApp/ContentView.swift` is a minimal SwiftUI screen (one
button + raw-output `Text` per capability) for manually verifying each
call against a physical device — no design intent beyond that.

Build/verify:

```sh
cd ios && xcodegen generate
xcodebuild -project FloorplanLab.xcodeproj -scheme FloorplanLabApp \
  -destination 'generic/platform=iOS Simulator' build
```

Real-device deploy additionally needs a matching provisioning profile
(`xcodebuild ... -destination 'platform=iOS,id=<UDID>' -allowProvisioningUpdates`)
and a connected, trusted, `devicectl`-visible device — both require
interactive Apple Developer Portal / device-trust steps outside a CI
agent's scope.

## Verify

```sh
kbb -M:test
kbb -M:lint
```

## Future work (explicitly out of scope for this first increment)

- Real sensor fusion (EKF/UKF with per-source noise covariance) in place
  of `fusion/correct-with-ble`'s plain weighted average; heading drift
  correction (currently only x/y are corrected).
- Dead-reckoning bias correction / zero-velocity updates (ZUPT) instead
  of raw double integration.
- FFT-based matched filter for chirp-echo detection instead of direct
  O(n·m) cross-correlation; multiple simultaneous echoes / multipath.
- Per-beacon/per-site calibration of the BLE path-loss model constants
  (`ble/default-tx-power-at-1m-dbm`, `ble/default-path-loss-exponent`)
  instead of fixed defaults.
- Concave room outlines (alpha-shape / occupancy-grid) instead of
  `fusion/convex-hull`, which clips L-shaped and other non-convex rooms.
- Wiring `sensing-bridge`'s mirrored driver contract to the real native
  shim that now exists (`ios/FloorplanLabApp/SensingBridge.swift`, see
  the `ios/` section above) and/or to the real `kotoba.sensing-host`
  once `kotoba-lang/device` registers the matching capability surfaces
  (closing ADR-2607140600 section 3) — see `sensing_bridge.cljc`'s
  docstring for the exact swap point. `SensingBridge` itself only calls
  the OS APIs and returns raw results; it is not yet reachable FROM the
  `.cljc` driver map (no WKWebView/JS bridge, no XPC, no host-import
  wiring exists yet) — that connection is still open work.
- A `kotoba-ui`/`shitsuke.hig`-stack PWA UI (per the ADR's "lab 本体"
  section) — this repo is algorithms only, no UI yet.
