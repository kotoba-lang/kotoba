(ns character.hair
  "Hair mesh generation — bridges `character.hair`'s 23 named presets
  (short-hand `HairParams`: `{:preset :color :highlight-color :length-scale
  :volume :part-position}`) to `character.hair-gen`'s layered polygon-shell
  hair mesh (`generate-hair-mesh`, 3 ribbon-strip layers -> a real
  hairstyle silhouette), instead of the raw strand-quad-strips this
  namespace generated directly before. Restored from the legacy
  kami-engine/kami-character Rust crate's `hair.rs` (deleted in
  kotoba-lang/kami-engine PR #82) as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Real gap closed (/loop maturity pass, visual-quality follow-up): the
  previous pass in this namespace (strand-count/width tuning) reduced
  individually-visible tendril messiness but explicitly did not produce a
  distinct hairstyle silhouette — its own report called the result 'a
  large, round, unstyled mass' and flagged `character.hair-gen`/
  `character.groom` (an Alembic-style strand system with a hair-card
  converter, `character.cljc`'s own docstring already describes the
  intended 'HairStyle -> hair-gen/generate-groom -> GroomAsset ->
  groom/to-hair-cards' pipeline) as real, working, but never wired into
  this namespace's `generate-hair` entry point. `generate-hair-mesh`
  (layered ribbon strips forming a volumetric shell, not sparse cards) is
  used here rather than `generate-hair-cards` — a continuous shell reads as
  a coherent hairstyle silhouette at low layer count (3), where sparse
  individual cards would look gappy without a much larger card count this
  pass doesn't need. `generate-character`'s call site
  (`hair/generate-hair (:hair def)`) is UNCHANGED — this is an internal
  geometry-technique swap, not an API change."
  (:require [character.math :as m]
            [character.hair-gen :as hair-gen]))

(def hash-f32 m/hash-f32)

;; ── preset -> HairStyle base ---------------------------------------------
;; `character.hair-gen/HairStyle`'s `:style` only has 5 real archetypes
;; (straight/wavy/curly/afro/braided) and its shell generator has no
;; concept of ties/buns/shaved-sides/a central mohawk strip — presets whose
;; real-world shape needs those (ponytail/bun/undercut/mohawk) are mapped
;; to the closest archetype + a length/volume that reads reasonably, not a
;; pixel-exact recreation. Documented approximation, same honesty
;; convention as `character-creator.expression-bridge`'s VRM<->ARKit table.
;; `:length`/`:density`/`:curl`/`:bangs-length`/`:bangs-width` are
;; `hair-gen`'s own 0..1-ish ranges (see `default-hair-style`), NOT the old
;; per-namespace absolute-metre `base-length` this replaces.
(defn- preset->style-base [preset]
  (case preset
    :bald              {:style :straight :length 0.0  :density 0.0 :curl 0.0  :bangs-length 0.0 :bangs-width 0.0}
    :buzz              {:style :straight :length 0.05 :density 1.0 :curl 0.0  :bangs-length 0.0  :bangs-width 0.0}
    :pixie             {:style :straight :length 0.12 :density 0.85 :curl 0.05 :bangs-length 0.2  :bangs-width 0.4}
    :short-straight    {:style :straight :length 0.18 :density 0.85 :curl 0.03 :bangs-length 0.2  :bangs-width 0.5}
    :short-wavy        {:style :wavy     :length 0.18 :density 0.85 :curl 0.25 :bangs-length 0.2  :bangs-width 0.5}
    :short-curly       {:style :curly    :length 0.18 :density 0.9  :curl 0.55 :bangs-length 0.15 :bangs-width 0.5}
    :bob               {:style :straight :length 0.28 :density 0.9  :curl 0.03 :bangs-length 0.3  :bangs-width 0.55}
    :medium-straight   {:style :straight :length 0.45 :density 0.85 :curl 0.03 :bangs-length 0.3  :bangs-width 0.5}
    :medium-wavy       {:style :wavy     :length 0.45 :density 0.85 :curl 0.3  :bangs-length 0.3  :bangs-width 0.5}
    ;; "layered" has no hair-gen equivalent (multiple cut lengths blended) —
    ;; approximated as plain medium-straight, documented not silently guessed.
    :medium-layered    {:style :straight :length 0.42 :density 0.85 :curl 0.05 :bangs-length 0.3  :bangs-width 0.5}
    :long-straight     {:style :straight :length 0.75 :density 0.85 :curl 0.03 :bangs-length 0.3  :bangs-width 0.5}
    :long-wavy         {:style :wavy     :length 0.75 :density 0.85 :curl 0.3  :bangs-length 0.3  :bangs-width 0.5}
    :long-curly        {:style :curly    :length 0.7  :density 0.9  :curl 0.6  :bangs-length 0.25 :bangs-width 0.5}
    ;; ponytail/bun: no tied-back geometry in hair-gen's shell generator —
    ;; approximated as a plain flowing shell at a shorter effective length
    ;; (reads as "gathered," not loose-and-long).
    :ponytail-high     {:style :straight :length 0.55 :density 0.8  :curl 0.05 :bangs-length 0.2  :bangs-width 0.4}
    :ponytail-low      {:style :straight :length 0.65 :density 0.8  :curl 0.05 :bangs-length 0.2  :bangs-width 0.4}
    :bun-top           {:style :straight :length 0.2  :density 0.75 :curl 0.05 :bangs-length 0.1  :bangs-width 0.3}
    :bun-low           {:style :straight :length 0.25 :density 0.75 :curl 0.05 :bangs-length 0.1  :bangs-width 0.3}
    ;; undercut/mohawk: no shaved-sides/central-strip modeling — approximated
    ;; as short, low-density coverage (reads as close-cropped, not the real
    ;; shape).
    :undercut          {:style :straight :length 0.15 :density 0.5  :curl 0.0  :bangs-length 0.15 :bangs-width 0.4}
    :mohawk            {:style :straight :length 0.2  :density 0.35 :curl 0.0  :bangs-length 0.0  :bangs-width 0.0}
    :afro-short        {:style :afro     :length 0.2  :density 1.0  :curl 0.85 :bangs-length 0.0  :bangs-width 0.0}
    :afro-large        {:style :afro     :length 0.32 :density 1.0  :curl 0.95 :bangs-length 0.0  :bangs-width 0.0}
    ;; braids: no braid-strand-plaiting geometry — approximated as the
    ;; `:braided` curl-frequency archetype at a long length.
    :braids-twin       {:style :braided  :length 0.65 :density 0.8  :curl 0.15 :bangs-length 0.2  :bangs-width 0.4}
    :braids-single     {:style :braided  :length 0.75 :density 0.8  :curl 0.15 :bangs-length 0.2  :bangs-width 0.4}))

;; This codebase's head (`character.base-mesh/generate-head`) is a small
;; head-LOCAL ellipsoid (radius x=0.09/y=0.12/z=0.08, centred at local
;; origin — eyes/brow/mouth all sit within +-0.1 of y=0) — NOT
;; `hair-gen/default-hair-style`'s own `:head-radius 0.09 :head-center-y
;; 1.43` (a full-body WORLD-space convention inherited from the original
;; Rust crate's coordinate system, where a head sits ~1.4m off the ground).
;; Using that stock default here would place every strand root ~1.3m above
;; where this codebase's actual head mesh is — hair-gen's own radius
;; happens to already match (0.09), only `:head-center-y` needs overriding
;; to 0.0.
(def ^:private head-radius 0.10)
(def ^:private head-center-y 0.0)

(defn- hair-def->style
  "`HairParams` (this namespace's own def shape) -> a full `character.hair-
  gen/HairStyle`. `:length-scale`/`:volume`/`:part-position`/`:color`/
  `:highlight-color` come straight from the def; the rest of the style
  (archetype/base-length/density/curl/bangs) comes from `preset->style-
  base`. `:part-position` (this def's own 0..1 range, 0.5 = centred, same
  convention `strand-origin` used before this pass) maps to hair-gen's
  `:part-side` (roughly -1..1 around a centred part)."
  [{:keys [preset length-scale volume part-position color highlight-color]}]
  (let [base (preset->style-base preset)]
    (merge
     (hair-gen/default-hair-style)
     base
     {:length (* (:length base) (max 0.05 (or length-scale 1.0)))
      :volume (or volume 0.5)
      :part-side (- (* 2.0 (or part-position 0.5)) 1.0)
      :color (or color [0.5 0.35 0.2])
      :highlight-color (or highlight-color color [0.6 0.45 0.3])
      :head-radius head-radius
      :head-center-y head-center-y})))

(defn- merge-hair-parts
  "Concatenate `hair-gen/generate-hair-mesh`'s 3 layer `MeshPart`s
  (`hair_outer`/`hair_mid`/`hair_inner`) into ONE part named `\"hair\"` —
  `generate-character`'s call site expects a single hair `MeshPart`, same
  contract as this namespace's previous strand-quad-strip output (an
  internal swap, not an API change). Same index-offsetting technique as
  `character.body/merge-mesh-parts`."
  [layer-parts]
  (let [[vertices indices]
        (reduce (fn [[vs is] {pv :vertices pi :indices}]
                  (let [base (count vs)]
                    [(into vs pv) (into is (map #(+ % base) pi))]))
                [[] []]
                layer-parts)]
    {:name "hair" :vertices vertices :indices indices :material :hair}))

(defn generate-hair
  "Generate hair mesh from `HairParams` (`{:preset :color :highlight-color
  :length-scale :volume :part-position}`). `:bald` returns an empty part
  (unchanged contract). Otherwise: build a `character.hair-gen/HairStyle`
  from the preset + def fields, run `hair-gen/generate-hair-mesh` (the
  layered polygon-shell generator, 3 ribbon-strip layers), and merge those
  layers into one `\"hair\"` MeshPart."
  [{:keys [preset] :as hair-def}]
  (if (= preset :bald)
    {:name "hair" :vertices [] :indices [] :material :hair}
    (let [style (hair-def->style hair-def)
          {:keys [parts]} (hair-gen/generate-hair-mesh style)]
      (merge-hair-parts parts))))
