(ns kotoba.sarutahiko-factory.clashes
  "Engineering-clash records — ported from `scene.rs`'s `Clashes` / `Clash`
  (generated upstream by `engineering.py`, a clash-detection tool this repo
  does not port; only the resulting data model + a pure well-formedness
  check are ported here).

  A `clashes` value is a plain EDN map:

    :clashes/of       string (subject factory name)
    :clashes/clashes  [{:clash/id :clash/kind :clash/systems [...]
                         :clash/x :clash/y :clash/z} ...]

  `:clash/kind` is `\"hard\"` (utility ∩ structure) or `\"coordination\"`
  (services below clearance), per the Rust doc-comment.

  Pure: no I/O. See `kotoba.sarutahiko-factory.fixtures/clashes` for this
  repo's synthetic test fixture."
  )

(defn- finite-num? [n]
  (and (number? n)
       #?(:clj (Double/isFinite (double n))
          :cljs (js/isFinite n))))

(defn all [clashes] (:clashes/clashes clashes))

(defn valid-clash?
  "True when a clash's `:clash/x` `:clash/y` `:clash/z` are all finite,
  mirroring the Rust test's `x.is_finite() && z.is_finite()` check
  (extended here to also cover y)."
  [clash]
  (and (finite-num? (:clash/x clash))
       (finite-num? (:clash/y clash))
       (finite-num? (:clash/z clash))))

(defn valid?
  "True when every clash in `clashes` is `valid-clash?`."
  [clashes]
  (every? valid-clash? (all clashes)))

(defn hard [clashes] (filter #(= "hard" (:clash/kind %)) (all clashes)))
(defn coordination [clashes] (filter #(= "coordination" (:clash/kind %)) (all clashes)))
