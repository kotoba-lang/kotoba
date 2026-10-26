(ns kotoba.capability.clock.monotonic.provider
  "JVM reference host provider for actor:host field \"clock_monotonic\".

  ABI: () -> i64 nanoseconds-ish monotonic tick.
  Uses System/nanoTime. The core wasm ships an instance-local counter as a
  portable ABI packaging reference; production hosts should inject wall/OS
  monotonic time (this namespace)."
  (:import [java.lang System]))

(defn monotonic-ns
  "Monotonic nanoseconds from System/nanoTime (not wall-clock)."
  []
  (System/nanoTime))

(defn host-export
  []
  {:module "kotoba"
   :field "clock_monotonic"
   :params []
   :result :i64
   :fn monotonic-ns})
