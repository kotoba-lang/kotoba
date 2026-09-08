(ns kotoba.sensing-host-portable-test
  "The genuinely portable half of kotoba.sensing-host-test: the pure
  driver-dispatch layer (kotoba.sensing-host's own docstring: \"unit-testable
  on any runtime without a wasm instance or any Wasm memory ABI involved at
  all\"). `sensing-ops-registered-in-op->kind` stays in
  kotoba.sensing-host-test (.clj) because kotoba.runtime is itself a .clj-only
  namespace, and `sensing-effects-stub-path-returns-deterministic-values` /
  `sensing-host-functions-builds-one-guarded-host-function-per-op` stay
  because they exercise the Chicory-facing raw-effect and HostFunction wiring
  (long-array, com.dylibso.chicory.runtime.HostFunction)."
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing] :include-macros true])
            [kotoba.sensing-host :as sensing]))

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
