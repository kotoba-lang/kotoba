(ns floorplan-lab.sensing-bridge
  "Adapter between a raw device-sensing driver and this lab's pure
  algorithm inputs (`floorplan-lab.motion`/`sonar`/`ble`). No real sensor
  is ever called from this namespace -- see README \"No native code\".

  ============================================================
  DISCREPANCY NOTE (recorded 2026-07-13, at scaffold time, after reading
  the actual upstream source instead of trusting the prior task's
  summary -- per this lab's own scaffolding task instructions):

  The task that authored this scaffold was told `kotoba-lang/device`'s
  `src/kotoba/lang/device.cljc` already registered capability tokens
  `:motion` / `:audio-io` / `:ble-scan` / `:wifi-info` wired to
  `kotoba.sensing-host` (ADR-2607140600's ops, kotoba-core-contracts
  capability ids 234-237). Reading the ACTUAL `device.cljc` (HEAD
  d63eb7e3d588df680134eea6f20088d984bb390b at scaffold time; `git log`
  on that repo shows only 5 commits, none mentioning sensing/motion/
  audio/ble) shows this is NOT true:

    - `device`'s `surface-effects` map only has `:bluetooth` / `:wifi` /
      `:display` / `:geolocation` / `:camera` -- no `:motion`,
      `:audio-io`, `:ble-scan`, or `:wifi-info` keys exist.
    - Nothing in `device.cljc` references `kotoba.sensing-host`, its 5
      ops, or capability ids 234-237.
    - `kotoba-core-contracts` DOES register those 4 capabilities/ids
      (confirmed: resources/kotoba/runtime/capability_contract.edn +
      test/kotoba/core/contracts_test.cljc), and `kotoba-lang/kotoba`'s
      `src/kotoba/sensing_host.cljc` DOES implement the deterministic-
      stub driver-dispatch layer for them (confirmed by reading that
      file directly). So the CONTRACTS + HOST-STUB half of ADR-2607140600
      Phase 3a is real and landed; the DEVICE-INTEGRATION half (ADR
      section \"3. kotoba-lang/device への統合\") is NOT landed.

  DESIGN RESPONSE: rather than depend on the heavy, chicory/ed25519/
  dag-cbor-transitive `kotoba-lang/kotoba` repo just to reuse
  `kotoba.sensing-host`'s ~30-line pure driver-dispatch functions
  (`read-motion`/`play-audio!`/`record-audio`/`scan-ble`/
  `read-wifi-info`), this namespace defines its OWN driver contract that
  intentionally MIRRORS `kotoba.sensing-host`'s documented shape
  byte-for-byte:

    {:motion-read  (fn [] [ax ay az gx gy gz mx my mz])   ; 9 floats
     :audio-play   (fn [freq-hz duration-ms] true/false)
     :audio-record (fn [duration-ms] [sample ...])         ; floats
     :ble-scan     (fn [duration-ms] [{:id :rssi} ...])
     :wifi-info    (fn [] {:signal-dbm ...})}

  A real driver -- a native shim per ADR-2607030900's
  aiueos-device-provider pattern, or `kotoba.sensing-host` itself once
  `device` grows the matching surfaces -- is a drop-in swap into this
  same shape; nothing in `floorplan-lab.motion`/`sonar`/`ble` needs to
  change when that lands, only which driver map gets passed to this
  namespace's adapter functions.

  This namespace still genuinely DEPENDS ON AND USES `kotoba-lang/device`
  (this repo's one external dependency, deps.edn): `as-idevice` wraps the
  mirrored driver contract in device's `IDevice` protocol, so a caller
  already using `device`'s `discover`/`call`/`IDevice` vocabulary for the
  5 EXISTING surfaces (bluetooth/wifi/display/geolocation/camera) gets
  the same shape here, poll-based (`subscribe` is a no-op -- there is no
  push/event surface on the kotoba.sensing-host side either).

  FOLLOW-UP (out of this scaffold's scope): once `device.cljc` registers
  `:motion`/`:audio-io`/`:ble-scan`/`:wifi-info` in its own
  `surface-effects`/`surface-schema` (closing ADR-2607140600 section 3),
  this namespace's `as-idevice` wrapper becomes unnecessary scaffolding
  -- `device/make-device-manager` + `device/call` can gate these surfaces
  directly, and floorplan-lab can depend on `kotoba-lang/kotoba` (or
  whatever thin re-export `device` ends up using) for the real
  `kotoba.sensing-host` driver-dispatch instead of this mirrored
  contract.
  ============================================================"
  (:require [kotoba.lang.device :as device]))

(defn motion-sample-from-raw9
  "Convert a driver's flat 9-value motion-read output (accel x/y/z, gyro
  x/y/z, mag x/y/z -- `kotoba.sensing-host/read-motion`'s documented
  shape, already decoded from fixed-point to float by the caller) plus a
  DT (seconds, the sample interval) into `floorplan-lab.motion`'s sample
  map. Mag (indices 6-8) is accepted but unused by the current 2D
  estimator."
  [[ax ay az gx gy gz mx my mz] dt]
  {:ax ax :ay ay :az az :gx gx :gy gy :gz gz :mx mx :my my :mz mz :dt dt})

(defn ble-readings->beacons
  "Merge SCAN-RESULTS (seq of {:id :rssi}, `kotoba.sensing-host/scan-ble`'s
  shape) with KNOWN-POSITIONS ({id {:x :y}}, this lab's own beacon
  survey/config, out of scope for auto-discovery) into
  `floorplan-lab.ble/trilaterate`'s beacon input ({:x :y :distance}),
  converting each RSSI via RSSI->DISTANCE-FN (e.g.
  `floorplan-lab.ble/rssi->distance-m`). Beacons with no known position
  are dropped -- can't trilaterate against an unknown-position anchor."
  [scan-results known-positions rssi->distance-fn]
  (keep (fn [{:keys [id rssi]}]
          (when-let [{:keys [x y]} (get known-positions id)]
            {:x x :y y :distance (rssi->distance-fn rssi)}))
        scan-results))

(defn mock-driver
  "A deterministic mirrored-driver map for tests / OSS standalone runs --
  same role as `kotoba.lang.device/mock-device`, but shaped for THIS
  namespace's `kotoba.sensing-host`-mirroring driver contract rather than
  device's `IDevice` protocol. DATA is a map of any of:
    :motion-samples     seq of raw9 vectors, consumed one per call (in
                         order); once exhausted, falls back to 9 zeros
                         (mirrors kotoba.sensing-host's \"no driver\"
                         stub answer shape, just non-empty instead of []
                         since a fixed-width sample is more useful here)
    :audio-recording     a single buffer (vector of floats) returned by
                         every audio-record call
    :ble-scan-results    a single seq of {:id :rssi} returned by every
                         ble-scan call"
  [{:keys [motion-samples audio-recording ble-scan-results]}]
  (let [remaining (atom (vec motion-samples))]
    {:motion-read (fn []
                     (if-let [s (first @remaining)]
                       (do (swap! remaining subvec 1) s)
                       [0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0]))
     :audio-play (fn [freq-hz duration-ms] (and (pos? freq-hz) (pos? duration-ms)))
     :audio-record (fn [_duration-ms] (or audio-recording []))
     :ble-scan (fn [_duration-ms] (or ble-scan-results []))
     :wifi-info (fn [] nil)}))

(defn as-idevice
  "Wrap a mirrored-driver DRIVER (this namespace's contract) as a
  `kotoba.lang.device/IDevice` -- `scan` -> ble-scan (0ms duration),
  `read-dev` dispatches on HANDLE (\"motion\"/\"audio\"/\"wifi\"),
  `write-dev` with HANDLE \"audio\" plays a {:freq-hz :duration-ms} DATA
  map, `subscribe` is a no-op (poll-based bridge, see namespace
  docstring)."
  [driver]
  (reify device/IDevice
    (scan [_] ((:ble-scan driver) 0))
    (read-dev [_ handle]
      (case handle
        "motion" ((:motion-read driver))
        "audio" ((:audio-record driver) 0)
        "wifi" ((:wifi-info driver))
        nil))
    (write-dev [_ handle data]
      (if (= handle "audio")
        (boolean ((:audio-play driver) (:freq-hz data) (:duration-ms data)))
        false))
    (subscribe [_ _handle _f] nil)))
