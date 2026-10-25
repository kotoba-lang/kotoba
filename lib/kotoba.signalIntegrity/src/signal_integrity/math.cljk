(ns signal-integrity.math
  "Cross-platform (JVM/cljs) math primitives used by the
  `signal-integrity.*` domain namespaces. No network, no I/O.

  These wrap the JVM `Math/*` static methods and `js/Math` respectively,
  per this monorepo's `#?(:clj ... :cljs ...)` convention, so the domain
  namespaces (crosstalk / eye-diagram / s-param / transmission-line) can
  stay platform-agnostic `.cljc`."
  (:refer-clojure :exclude [abs]))

(def pi
  "π, matching Rust's `std::f64::consts::PI`."
  #?(:clj Math/PI :cljs js/Math.PI))

(defn sqrt
  "Square root, matching Rust's `f64::sqrt`."
  [x]
  #?(:clj (Math/sqrt x) :cljs (.sqrt js/Math x)))

(defn ln
  "Natural logarithm, matching Rust's `f64::ln`."
  [x]
  #?(:clj (Math/log x) :cljs (.log js/Math x)))

(defn log10
  "Base-10 logarithm, matching Rust's `f64::log10`."
  [x]
  #?(:clj (Math/log10 x) :cljs (.log10 js/Math x)))

(defn exp
  "e^x, matching Rust's `f64::exp`."
  [x]
  #?(:clj (Math/exp x) :cljs (.exp js/Math x)))

(defn floor
  "Largest integer `<= x`, matching Rust's `f64::floor`."
  [x]
  #?(:clj (Math/floor x) :cljs (.floor js/Math x)))

(defn pow
  "`x` raised to the power `y`, matching Rust's `f64::powi`/`powf`."
  [x y]
  #?(:clj (Math/pow x y) :cljs (.pow js/Math x y)))

(defn abs
  "Absolute value, matching Rust's `f64::abs`."
  [x]
  #?(:clj (Math/abs (double x)) :cljs (.abs js/Math x)))
