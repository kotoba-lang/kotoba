(ns kotoba.capability.time.now-days.provider
  "JVM reference host provider for actor:host field \"now_days\".

  ABI: () -> f32 simulated day count (host-owned).
  Uses UTC millis / 86400000 as a continuous day counter. The core wasm
  returns 0.0 as an ABI packaging stub; production hosts recompute from
  wall clock each frame (capability_contract.edn notes)."
  (:import [java.lang System]))

(def ^:private ms-per-day 86400000.0)

(defn now-days
  "Fractional UTC days since Unix epoch as f32."
  []
  (float (/ (double (System/currentTimeMillis)) ms-per-day)))

(defn host-export
  []
  {:module "kotoba"
   :field "now_days"
   :params []
   :result :f32
   :fn now-days})
