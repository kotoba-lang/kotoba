(ns kotoba.geo.math
  "Portable (JVM / ClojureScript / SCI) scalar math helpers used across
  `kotoba.geo.*`. Centralizes the `#?(:clj ... :cljs ...)` reader
  conditionals so the domain namespaces read like plain math."
  (:refer-clojure :exclude [abs]))

(def pi #?(:clj Math/PI :cljs js/Math.PI))
(def tau (* 2.0 pi))

(defn to-radians [deg] (* deg (/ pi 180.0)))
(defn to-degrees [rad] (* rad (/ 180.0 pi)))

(defn sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn tan [x] #?(:clj (Math/tan x) :cljs (js/Math.tan x)))
(defn atan [x] #?(:clj (Math/atan x) :cljs (js/Math.atan x)))
(defn atan2 [y x] #?(:clj (Math/atan2 y x) :cljs (js/Math.atan2 y x)))
(defn exp [x] #?(:clj (Math/exp x) :cljs (js/Math.exp x)))
(defn log [x] #?(:clj (Math/log x) :cljs (js/Math.log x)))
(defn pow [x y] #?(:clj (Math/pow x y) :cljs (js/Math.pow x y)))
(defn sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn floor [x] #?(:clj (Math/floor x) :cljs (js/Math.floor x)))
(defn ceil [x] #?(:clj (Math/ceil x) :cljs (js/Math.ceil x)))
(defn abs [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

(defn sinh [x] (/ (- (exp x) (exp (- x))) 2.0))

(defn clamp [x lo hi] (min (max x lo) hi))
