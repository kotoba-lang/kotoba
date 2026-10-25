(ns kotoba.sarutahiko-factory.construction-order
  "4D construction order — ported from `scene.rs`'s `ConstructionOrder` /
  `OrderStep` and the `programme_days` method. Drives the giemon-factory
  4D-BIM 'reveal elements in `:seq` order' playback pattern
  (ADR-2606010030); the WASM playback loop itself
  (`run_sarutahiko_factory_build_v1`, clock/reveal-timer/HUD bridge) is
  unported host-adapter code.

  An `order` is a plain EDN map:

    :construction-order/of     string (subject factory name)
    :construction-order/steps  [{:step/seq :step/id :step/name :step/trade
                                  :step/robot :step/zone :step/duration-d
                                  :step/reveals [element-id ...]} ...]

  Pure: no I/O. See `kotoba.sarutahiko-factory.fixtures/construction-order`
  for this repo's synthetic test fixture."
  (:require [kotoba.lang.text :as str]))

(defn steps [order] (:construction-order/steps order))

(defn programme-days
  "Total nominal programme length: the sum of every step's `:step/duration-d`."
  [order]
  (reduce + 0.0 (map :step/duration-d (steps order))))

(defn seq-contiguous?
  "True when step `:step/seq` values are exactly `1..n` in order, mirroring
  the Rust test's `seqs == (1..=len)` check."
  [order]
  (= (mapv :step/seq (steps order))
     (vec (range 1 (inc (count (steps order)))))))

(defn unresolved-reveals
  "The subset of every step's `:step/reveals` ids that aren't present in
  `known-ids` (e.g. `(factory/element-ids f)`)."
  [order known-ids]
  (let [known (set known-ids)]
    (into #{} (mapcat (fn [s] (remove known (:step/reveals s)))) (steps order))))

(defn reveals-resolve?
  "True when every step's `:step/reveals` names a real factory element."
  [order known-ids]
  (empty? (unresolved-reveals order known-ids)))

(defn steps-missing-robot
  "Steps whose `:step/robot` is blank or isn't a member of `robot-ids`."
  [order robot-ids]
  (let [known (set robot-ids)]
    (filter (fn [s] (or (str/blank? (:step/robot s))
                          (not (known (:step/robot s)))))
            (steps order))))

(defn steps-resolve-robots?
  "True when every step names a robot present in `robot-ids`."
  [order robot-ids]
  (empty? (steps-missing-robot order robot-ids)))
