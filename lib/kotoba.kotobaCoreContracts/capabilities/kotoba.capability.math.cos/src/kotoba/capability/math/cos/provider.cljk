(ns kotoba.capability.math.cos.provider
  "JVM reference host provider for actor:host field \"cos\"."
  (:import [java.lang Math]))

(defn cos-f32
  [^double x]
  (float (Math/cos x)))

(defn host-export
  []
  {:module "kotoba"
   :field "cos"
   :params [:f32]
   :result :f32
   :fn (fn [x] (cos-f32 (double x)))})
