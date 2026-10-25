(ns character.params
  "Character definition parameters — continuous parametric values (maps
  1:1 to WIT `gftd:kami/character-maker` types). Restored from the
  legacy kami-engine/kami-character Rust crate's `params.rs` (deleted
  in kotoba-lang/kami-engine PR #82) as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  All params are plain maps; enums (`HairPreset`/`ClothingPreset`) are
  keywords.")

(def hair-presets
  #{:short-straight :short-wavy :short-curly
    :medium-straight :medium-wavy :medium-layered
    :long-straight :long-wavy :long-curly
    :ponytail-high :ponytail-low :bun-top :bun-low
    :bob :pixie :buzz :undercut :mohawk
    :afro-short :afro-large
    :braids-twin :braids-single
    :bald})

(def clothing-presets
  #{:tank-top :t-shirt :blouse :hoodie :jacket
    :dress-casual :dress-formal
    :suit-casual :suit-formal
    :uniform-school :uniform-military
    :nude-shoulders})

(def body-presets
  "Named quick-pick body-type presets, analogous to `hair-presets`/
  `clothing-presets` (a validation set of keyword ids) plus
  `resolve-body-preset` (below) as the value-table, mirroring how
  `character.hair/preset-config` resolves `hair-presets`' keywords to
  concrete generation values. `character-creator.app`'s existing
  continuous body sliders are unaffected — a preset is a quick starting
  point a user can still fine-tune with the sliders afterward, same
  relationship the hair carousel already has to raw `:hair` params (not
  wired into the app in this pass; that's `kami-app-character-creator`'s
  own follow-up)."
  #{:petite :slim :average :athletic :heavy :tall})

(defn resolve-body-preset
  "`body-presets` keyword -> a `{:height :build :shoulder-width
  :neck-thickness}` map (the same shape `default-character-def`'s `:body`
  already uses, so `(update character-def :body merge (resolve-body-preset
  k))` drops straight in). `:average` matches `default-character-def`'s
  existing `:body` values exactly, so switching to `:average` is a no-op."
  [preset]
  (case preset
    :petite         {:height 0.85 :build 0.20 :shoulder-width 0.30 :neck-thickness 0.28}
    :slim           {:height 1.0  :build 0.15 :shoulder-width 0.32 :neck-thickness 0.28}
    :average        {:height 1.0  :build 0.30 :shoulder-width 0.40 :neck-thickness 0.35}
    :athletic       {:height 1.0  :build 0.55 :shoulder-width 0.55 :neck-thickness 0.45}
    :heavy          {:height 0.98 :build 0.85 :shoulder-width 0.60 :neck-thickness 0.55}
    :tall           {:height 1.15 :build 0.40 :shoulder-width 0.45 :neck-thickness 0.38}))

(defn default-character-def
  "Default: young feminine character matching the reference photo."
  []
  {:face {:jaw-width 0.4 :jaw-length 0.5 :chin-shape 0.3
          :cheekbone-width 0.55 :cheekbone-height 0.6
          :forehead-height 0.5 :forehead-width 0.5
          :temple-width 0.5 :face-length 0.6}
   :eyes {:size 0.7 :width 0.6 :height 0.55 :spacing 0.5
          :tilt 0.1 :depth 0.5 :iris-size 0.8
          :iris-color [0.45 0.65 0.85]}
   :nose {:length 0.4 :width 0.35 :bridge-height 0.45
          :tip-shape 0.6 :tip-angle 0.55 :nostril-width 0.35}
   :mouth {:width 0.55 :upper-lip-thickness 0.5 :lower-lip-thickness 0.55
           :corner-angle 0.15 :philtrum-depth 0.5
           :lip-color [0.85 0.62 0.62]}
   :brows {:thickness 0.35 :arch-height 0.5 :spacing 0.5
           :angle 0.1 :color [0.65 0.55 0.42]}
   :skin {:tone [0.94 0.87 0.82] :roughness 0.45
          :subsurface 0.6 :freckles 0.0 :blemishes 0.0}
   :hair {:preset :long-straight
          :color [0.92 0.85 0.70]
          :highlight-color [0.95 0.90 0.78]
          :length-scale 1.0 :volume 0.6
          :part-position 0.5 :shininess 0.5}
   :clothing {:preset :tank-top
              :color [0.95 0.95 0.95]
              :secondary-color nil :fit 0.5}
   :body {:height 1.0 :shoulder-width 0.4
          :build 0.3 :neck-thickness 0.35}})
