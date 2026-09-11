(ns kotoba.sensing-host-test
  "The JVM-only half of ADR-2607140600 Phase 3a coverage:
  `sensing-ops-registered-in-op->kind` needs kotoba.runtime (.clj-only), and
  the `sensing-effects`/`sensing-host-functions` deftests exercise the
  Chicory-facing raw-effect and HostFunction wiring directly (long-array,
  com.dylibso.chicory.runtime.HostFunction). The pure driver-dispatch layer's
  own portable coverage lives in kotoba.sensing-host-portable-test (.cljc),
  registered on both hosts."
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
