(ns kotoba.cam.util
  "Portable math + fixed-point string formatting helpers shared by the CAM
   domain namespaces. No network/IO — pure functions only. The only platform
   difference (JVM `Math` vs JS `Math`) is isolated here behind reader
   conditionals so every other `.cljc` namespace in this repo stays platform
   agnostic.")

(defn sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn ceil [x] #?(:clj (Math/ceil x) :cljs (js/Math.ceil x)))
(defn round
  "Round to nearest integer, ties away from zero for positives (matches
   `java.lang.Math/round` / `js/Math.round`)."
  [x]
  #?(:clj (Math/round (double x)) :cljs (js/Math.round x)))

(defn pad-int
  "Zero-pad a non-negative integer `n` to at least `width` digits, e.g.
   `(pad-int 1 4)` => \"0001\". Mirrors Rust's `{:0width}` integer formatting
   used for G-code program/tool numbers."
  [n width]
  ;; Refuse a non-number instead of formatting `NaN`. `(long :em6)` yields NaN in
  ;; ClojureScript, and "TNaN M06" is a G-code line a controller rejects — emitted
  ;; by a generator that reported success. Fail closed at the formatter.
  (when-not (number? n)
    (throw (ex-info "pad-int needs a number (a NaN would be written into the G-code)"
                    {:value n :type (type n)})))
  (let [s (str (long n))]
    (str (apply str (repeat (max 0 (- width (count s))) "0")) s)))

(defn fixed
  "Format a number `x` with exactly `decimals` fixed decimal places, Rust
   `{:.N}` style (always shows the decimal point + trailing zeros, no
   thousands separator). e.g. `(fixed -10.0 4)` => \"-10.0000\"."
  [x decimals]
  (let [x (double x)
        neg? (< x 0)
        ax (if neg? (- x) x)
        scale (long (reduce * 1 (repeat decimals 10)))
        scaled (long (round (* ax scale)))
        int-part (quot scaled scale)
        frac-part (mod scaled scale)
        frac-str (let [s (str frac-part)]
                   (str (apply str (repeat (max 0 (- decimals (count s))) "0")) s))]
    (str (when neg? "-") int-part (when (pos? decimals) (str "." frac-str)))))
