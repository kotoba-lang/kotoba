(ns kotoba.capability.math.sin.provider
  "JVM reference host provider for actor:host field \"sin\"."
  (:import [java.lang Math]))

(defn sin-f32
  [^double x]
  (float (Math/sin x)))

(defn host-export
  []
  {:module "kotoba"
   :field "sin"
   :params [:f32]
   :result :f32
   :fn (fn [x] (sin-f32 (double x)))})
