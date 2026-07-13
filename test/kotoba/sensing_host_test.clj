(ns kotoba.sensing-host-test
  "ADR-2607140600 Phase 3a device-capability bridge (iPhone sensing for the
  indoor floorplan-lab): confirms (1) kotoba.runtime/op->kind registers the
  5 new ops against real (not :unsupported-kind) capability kinds, (2)
  kotoba.sensing-host's pure driver-dispatch layer is deterministic --
  same stub answer every call with no driver injected, and a fake
  test-only driver's values pass through unchanged, (3) the deterministic
  stub answers documented in kotoba.sensing-host and
  capability_contract.edn are exactly what `sensing-effects`' raw host
  fns return with no driver, and (4) `sensing-host-functions` builds a
  real guarded HostFunction per op (Chicory wiring smoke test), same
  style as kotoba.kami-game-test's \"no wasm involved\" block --
  deliberately NOT a full `kotoba wasm emit` + Chicory instantiate + run
  test, since this ADR doesn't ship a `.kotoba` demo exercising these ops
  (that's the floorplan-lab itself, out of this ADR's scope)."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.sensing-host :as sensing]
            [kotoba.wasm-exec]))

(deftest sensing-ops-registered-in-op->kind
  (doseq [[op kind] {'motion-read :host/motion-read
                     'audio-play :host/audio-io
                     'audio-record :host/audio-io
                     'ble-scan :host/ble-scan
                     'wifi-info :host/wifi-info}]
    (is (= kind (get runtime/op->kind op)) (str op))))

(deftest pure-driver-dispatch-defaults-to-the-deterministic-stub
  (testing "no driver -> the documented stub answer, every call, same value"
    (is (= [] (sensing/read-motion nil)))
    (is (= [] (sensing/read-motion nil)))
    (is (false? (sensing/play-audio! nil 440 100)))
    (is (false? (sensing/play-audio! nil 880 250)))
    (is (= [] (sensing/record-audio nil 100)))
    (is (= [] (sensing/scan-ble nil 100)))
    (is (nil? (sensing/read-wifi-info nil)))))

(deftest pure-driver-dispatch-passes-through-an-injected-driver
  (testing "the ADR-2607030900 device-access-provider extension point:
            when a driver IS supplied, its answer passes through
            unchanged -- proves the swap point genuinely works without
            touching any real OS sensing API (the injected fns here are
            plain test-only Clojure data, not CoreMotion/CoreBluetooth/
            AVAudioEngine)"
    (let [driver {:motion-read (constantly [1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0 9.0])
                  :audio-play (fn [freq-hz duration-ms] (and (pos? freq-hz) (pos? duration-ms)))
                  :audio-record (fn [duration-ms] (repeat duration-ms 0.5))
                  :ble-scan (fn [_duration-ms] [{:id 1 :rssi -60} {:id 2 :rssi -80}])
                  :wifi-info (constantly {:signal-dbm -55})}]
      (is (= [1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0 9.0] (sensing/read-motion driver)))
      (is (true? (sensing/play-audio! driver 440 100)))
      (is (false? (sensing/play-audio! driver 0 100)) "freq-hz 0 -> the driver itself says no")
      (is (= 3 (count (sensing/record-audio driver 3))))
      (is (= [{:id 1 :rssi -60} {:id 2 :rssi -80}] (sensing/scan-ble driver 100)))
      (is (= {:signal-dbm -55} (sensing/read-wifi-info driver))))))

(deftest sensing-effects-stub-path-returns-deterministic-values
  (testing "sensing-effects' raw (fn [instance args] -> long) bodies with NO
            driver (the deterministic stub, capability_contract.edn's
            documented per-op result) never touch `instance` -- safe to
            call with instance nil, same as kotoba.wasm-exec/real-op-
            effects' -1-on-overflow convention doubles as a recoverable-
            failure signal a guest can react to"
    (let [effects (sensing/sensing-effects)]
      (is (= 0 ((get effects 'motion-read) nil (long-array [0 0])))
          "(out-ptr, out-cap) -> 0 samples written")
      (is (= -1 ((get effects 'audio-play) nil (long-array [440 100])))
          "(freq-hz, duration-ms) -> -1, nothing was actually played")
      (is (= 0 ((get effects 'audio-record) nil (long-array [100 0 0])))
          "(duration-ms, out-ptr, out-cap) -> 0 samples written")
      (is (= 0 ((get effects 'ble-scan) nil (long-array [100 0 0])))
          "(duration-ms, out-ptr, out-cap) -> 0 peripherals found")
      (is (= 0 ((get effects 'wifi-info) nil (long-array [0 0])))
          "(out-ptr, out-cap) -> 0, info unavailable"))
    (testing "deterministic: same op, same args, same result across repeated calls"
      (let [effects (sensing/sensing-effects)
            motion-read (get effects 'motion-read)]
        (is (apply = (repeatedly 3 #(motion-read nil (long-array [0 0])))))))))

(deftest sensing-host-functions-builds-one-guarded-host-function-per-op
  (testing "Chicory wiring smoke test (mirrors kotoba.kami-host's
            kami-host-functions build) -- a policy that doesn't grant any
            of the 4 capabilities still builds cleanly (the guard fires
            per-CALL, at run time, not at build time)"
    (let [no-grant {:kotoba.policy/capabilities #{}}
          host-fns (sensing/sensing-host-functions no-grant)]
      (is (= 5 (count host-fns)))
      (is (every? #(instance? com.dylibso.chicory.runtime.HostFunction %) host-fns)))))
