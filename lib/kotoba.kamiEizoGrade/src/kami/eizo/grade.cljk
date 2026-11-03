(ns kami.eizo.grade
  "Top-level grade node: composes a `kami.eizo.grade.cdl` primary
   correction, optional per-channel `kami.eizo.grade.curve`s, and an
   optional `kami.eizo.grade.lut` \"look\" LUT into a single ordered
   pipeline (primary -> curves -> LUT, the conventional grading order).
   A grade is designed to be carried as an opaque effect-instance entry
   on a `kami-eizo-timeline` clip/track (that repo models effect
   instances as opaque references with enable/bypass state — this repo
   is what such a reference points to for a `:grade` effect type)."
  (:require [kami.eizo.grade.cdl :as cdl]
            [kami.eizo.grade.curve :as curve]
            [kami.eizo.grade.lut :as lut]))

(defn grade
  "`cdl-node` — a map as built by `kami.eizo.grade.cdl/cdl` (optional).
   `curves` — optional {:r curve :g curve :b curve} (each a
   `kami.eizo.grade.curve/curve` value); missing channels pass through.
   `lut-node` — optional parsed `.cube` map (`kami.eizo.grade.lut/parse-cube`)."
  [{:keys [cdl-node curves lut-node]}]
  {:kami.eizo.grade/type :grade
   :cdl cdl-node
   :curves curves
   :lut lut-node
   :enabled? true})

(defn effect-instance
  "Wrap a grade as the opaque effect-instance shape kami-eizo-timeline
   expects on a clip/track's effect stack."
  [grade-node]
  {:type :grade :params grade-node :enabled? true})

(defn- apply-curves [{:keys [r g b]} [rv gv bv]]
  [(if r (curve/eval-curve r rv) rv)
   (if g (curve/eval-curve g gv) gv)
   (if b (curve/eval-curve b bv) bv)])

(defn apply-grade
  "Run the full pipeline on an [r g b] triple: CDL primary -> curves ->
   LUT look, skipping any stage whose node is nil."
  [{cdl-node :cdl curves-node :curves lut-node :lut} rgb]
  (let [after-cdl (if cdl-node (cdl/apply-cdl cdl-node rgb) rgb)
        after-curves (if curves-node (apply-curves curves-node after-cdl) after-cdl)
        after-lut (if lut-node (lut/sample-lut lut-node after-curves) after-curves)]
    after-lut))
