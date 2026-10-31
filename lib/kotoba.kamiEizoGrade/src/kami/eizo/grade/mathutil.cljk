(ns kami.eizo.grade.mathutil
  "Portable (:clj/:cljs) scalar math helpers — `Math/pow` et al. exist on
   both platforms but under different symbols, so every other namespace
   in this repo goes through here rather than sprinkling reader
   conditionals throughout the actual grading math."
  (:refer-clojure :exclude [abs]))

(defn pow [x p] #?(:clj (Math/pow x p) :cljs (js/Math.pow x p)))
(defn sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn floor [x] #?(:clj (Math/floor x) :cljs (js/Math.floor x)))
(defn abs [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))
