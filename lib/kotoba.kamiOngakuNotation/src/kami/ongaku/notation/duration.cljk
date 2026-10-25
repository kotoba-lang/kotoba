(ns kami.ongaku.notation.duration
  "Duration model: base note type (whole/half/.../64th) + dot count, kept
  as an exact kami.ongaku.notation.rational fraction of a whole note
  throughout — never native `/`/floats, which are exact on the JVM but
  silently become IEEE-754 doubles under ClojureScript.

  Portable .cljc."
  (:require [kami.ongaku.notation.rational :as r]))

(def base-values
  {:whole (r/make 1 1) :half (r/make 1 2) :quarter (r/make 1 4) :eighth (r/make 1 8)
   :16th (r/make 1 16) :32nd (r/make 1 32) :64th (r/make 1 64)})

(defn valid-type? [t] (contains? base-values t))
(defn valid-dots? [d] (and (integer? d) (<= 0 d 3)))

(defn dot-multiplier
  "Total-length multiplier for n dots: 1 dot = 3/2, 2 dots = 7/4, 3 dots =
  15/8 — as an exact kami.ongaku.notation.rational, never floating-point pow."
  [n]
  (reduce r/add r/one (map (fn [k] (r/make 1 (bit-shift-left 1 k))) (range 1 (inc n)))))

(defn duration-value
  "Total length (fraction of a whole note) for {:type :dots}, as an exact
  kami.ongaku.notation.rational."
  [{:keys [type dots] :or {dots 0}}]
  (when (and (valid-type? type) (valid-dots? dots))
    (r/mul (base-values type) (dot-multiplier dots))))

(defn closest-type+dots
  "Exact decomposition of a rational whole-note-fraction `v` into a
  {:type :dots} pair (dots in [0,3]); nil if `v` has no exact
  representation as (base-type * dot-multiplier)."
  [v]
  (some (fn [dots]
          (some (fn [[type base]]
                  (when (= v (r/mul base (dot-multiplier dots)))
                    {:type type :dots dots}))
                base-values))
        (range 0 4)))
