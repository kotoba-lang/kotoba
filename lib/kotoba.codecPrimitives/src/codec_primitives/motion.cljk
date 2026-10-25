(ns codec-primitives.motion
  "The reference motion-vector shape, and the predicate `motion.kotoba` is
  checked against by `codec-primitives.motion-parity-test`.

  Specified with `kotoba-lang/spec` rather than malli since 2026-09-10. malli
  was this repository's only third-party JVM dependency and it was carried for
  exactly one call — `(m/validate MotionVector x)` — in an eleven-line
  namespace. `kotoba.lang.spec` is plain EDN data plus pure functions with no
  third-party runtime dependency, so the same contract now reads on every host
  this `.cljc` claims to run on, including kotoba-WASM where a Maven jar
  cannot go at all.

  One translation is not one-for-one. malli's `[:tuple :int :int]` says
  EXACTLY TWO ints, and `kotoba.lang.spec`'s composite types are `:map`,
  `:vector` (with `:of`), `:set` (with `:of`) and `:fn` — there is no
  `:tuple`. Writing `{:type :vector :of {:type :int}}` would have admitted
  `[3 -2 1]`, which the parity test explicitly requires to be REFUSED, so the
  length is carried by a `:fn` predicate instead. That keeps the contract
  exact and loses some declarativeness for this one field; the gap belongs to
  `kotoba-lang/spec`, not here."
  (:require [kotoba.lang.spec :as spec]))

(def MotionVector
  {:type :map
   :keys {:poc {:type :int}                     ;; picture order count
          :ref-idx {:type :int}
          ;; [dx dy] クォーターペル単位 -- malli said [:tuple :int :int]
          :mv {:type :fn
               :pred (fn [v] (and (vector? v) (= 2 (count v)) (every? int? v)))}
          ;; フレームを指すID(実体はVault blob CID等、codec側が解決)
          :ref-frame {:type :keyword}}})

(defn valid-mv? [x] (spec/valid? MotionVector x))
