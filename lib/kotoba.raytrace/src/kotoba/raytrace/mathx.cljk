(ns kotoba.raytrace.mathx
  "Portable scalar math shims — `Math/x` (JVM) vs `js/Math.x` (JS) — so the
   BVH/WGSL-codegen ports read straight off the Rust source without a
   per-callsite reader conditional."
  (:refer-clojure :exclude [abs]))

(defn abs [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))
(defn floor [x] #?(:clj (Math/floor (double x)) :cljs (js/Math.floor x)))
(defn round [x] #?(:clj (Math/round (double x)) :cljs (js/Math.round x)))
(defn trunc [x] #?(:clj (long x) :cljs (js/Math.trunc x)))

(defn clamp [x lo hi] (max lo (min hi x)))
