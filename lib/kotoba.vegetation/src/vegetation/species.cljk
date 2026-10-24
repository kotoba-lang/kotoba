(ns vegetation.species
  "Species definitions: grass, fern, palm, tree with placement rules.

  Restored from `kami-vegetation/src/species.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Each species is a plain CLJC map of placement constraints (height/slope/
  splatmap affinity/density/min-distance) plus render params (scale, wind
  sway, color gradient). `species-id` values (Rust `SpeciesId` enum, GPU
  atlas index) map to keywords; `species-id->index`/`index->species-id`
  round-trip the numeric GPU index used by `InstanceData.species`.")

;; ---------------------------------------------------------------------
;; SpeciesId — maps to GPU atlas index
;; ---------------------------------------------------------------------

(def species-ids
  "All species identifiers, in GPU-atlas-index order."
  [:grass :fern :palm-tree :conifer :bush])

(def species-id->index
  "SpeciesId -> u32 atlas index (matches the original `#[repr(u32)]` enum)."
  {:grass 0 :fern 1 :palm-tree 2 :conifer 3 :bush 4})

(def index->species-id
  "u32 atlas index -> SpeciesId. Anything outside 0-3 maps to :bush,
   matching the original Rust `match` fallback (`_ => SpeciesId::Bush`)."
  (fn [i]
    (case (long i)
      0 :grass
      1 :fern
      2 :palm-tree
      3 :conifer
      :bush)))

;; ---------------------------------------------------------------------
;; Species table
;; ---------------------------------------------------------------------
;; Keys mirror the Rust struct fields 1:1:
;;   :id :name
;;   :min-height :max-height :max-slope :material-affinity :density
;;   :min-distance
;;   :height :scale-range :wind-sway :color :tip-color

(defn species-table
  "Full species table — the set of things that can grow in the world."
  []
  [{:id :grass
    :name "grass"
    :min-height 16.0
    :max-height 95.0
    :max-slope 0.55
    :material-affinity [1.0 0.5 0.6 0.0]
    :density 500.0
    :min-distance 0.5
    :height 0.8
    :scale-range [0.7 1.4]
    :wind-sway 0.35
    :color [0.18 0.42 0.08]
    :tip-color [0.42 0.68 0.15]}
   {:id :fern
    :name "fern"
    :min-height 18.0
    :max-height 80.0
    :max-slope 0.5
    :material-affinity [0.8 0.4 0.2 0.0]
    :density 60.0
    :min-distance 2.0
    :height 1.4
    :scale-range [0.8 1.5]
    :wind-sway 0.25
    :color [0.12 0.28 0.04]
    :tip-color [0.3 0.55 0.12]}
   {:id :palm-tree
    :name "palm"
    :min-height 16.0
    :max-height 30.0
    :max-slope 0.3
    :material-affinity [0.5 0.0 0.6 0.0]
    :density 2.0
    :min-distance 8.0
    :height 8.5
    :scale-range [0.85 1.25]
    :wind-sway 0.6
    :color [0.35 0.22 0.08]
    :tip-color [0.18 0.45 0.1]}
   {:id :conifer
    :name "conifer"
    :min-height 30.0
    :max-height 85.0
    :max-slope 0.55
    :material-affinity [0.9 0.3 0.0 0.0]
    :density 5.0
    :min-distance 5.5
    :height 10.0
    :scale-range [0.7 1.3]
    :wind-sway 0.2
    :color [0.25 0.18 0.08]
    :tip-color [0.12 0.3 0.08]}
   {:id :bush
    :name "bush"
    :min-height 17.0
    :max-height 70.0
    :max-slope 0.5
    :material-affinity [0.7 0.2 0.2 0.0]
    :density 15.0
    :min-distance 3.0
    :height 1.8
    :scale-range [0.8 1.4]
    :wind-sway 0.3
    :color [0.15 0.28 0.06]
    :tip-color [0.28 0.48 0.1]}])
