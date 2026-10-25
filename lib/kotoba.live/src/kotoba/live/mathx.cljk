(ns kotoba.live.mathx
  "Portable transcendental math — `#?(:clj :cljs)` wrappers around
  `java.lang.Math` / `js/Math` so the domain namespaces stay `.cljc` (JVM /
  ClojureScript) without sprinkling reader conditionals through the show
  logic."
  (:refer-clojure :exclude [abs]))

#?(:clj
   (do
     (defn sin [x] (Math/sin (double x)))
     (defn cos [x] (Math/cos (double x)))
     (defn abs [x] (Math/abs (double x)))
     (defn floor [x] (Math/floor (double x)))
     (defn sqrt [x] (Math/sqrt (double x)))
     (defn pow [b e] (Math/pow (double b) (double e)))
     (defn exp [x] (Math/exp (double x)))
     (defn to-degrees [r] (Math/toDegrees (double r)))
     (def pi Math/PI))
   :cljs
   (do
     (defn sin [x] (js/Math.sin x))
     (defn cos [x] (js/Math.cos x))
     (defn abs [x] (js/Math.abs x))
     (defn floor [x] (js/Math.floor x))
     (defn sqrt [x] (js/Math.sqrt x))
     (defn pow [b e] (js/Math.pow b e))
     (defn exp [x] (js/Math.exp x))
     (defn to-degrees [r] (/ (* r 180.0) js/Math.PI))
     (def pi js/Math.PI)))

(def tau (* 2.0 pi))
