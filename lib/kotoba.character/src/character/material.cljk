(ns character.material
  "PBR material definitions for character parts. Restored from the
  legacy kami-engine/kami-character Rust crate's `material.rs`
  (deleted in kotoba-lang/kami-engine PR #82) as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root)."
  )

(defn for-part
  "Generate PBR material for a character part from parameters. `id`
  is one of `:skin :eye-white :iris :pupil :lip :eyebrow :hair
  :clothing :eyelash`."
  [id {:keys [tone roughness subsurface] :as _skin}
   {:keys [iris-color] :as _eyes}
   {:keys [lip-color] :as _mouth}
   hair
   clothing]
  (let [hair-color (:color hair)
        shininess (:shininess hair)
        color (:color clothing)]
    (case id
      :skin {:name "skin" :base-color (conj (vec tone) 1.0)
             :metallic 0.0 :roughness roughness
             :subsurface (* subsurface 0.8) :subsurface-color [0.9 0.5 0.35]
             :anisotropic 0.0 :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]}
      :eye-white {:name "eye_white" :base-color [0.97 0.97 0.97 1.0]
                  :metallic 0.0 :roughness 0.15 :subsurface 0.3 :subsurface-color [0.95 0.85 0.85]
                  :anisotropic 0.0 :clearcoat 0.4 :clearcoat-roughness 0.1 :emission [0.0 0.0 0.0]}
      :iris {:name "iris" :base-color (conj (vec iris-color) 1.0)
             :metallic 0.05 :roughness 0.12 :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
             :anisotropic 0.0 :clearcoat 0.8 :clearcoat-roughness 0.05 :emission [0.0 0.0 0.0]}
      :pupil {:name "pupil" :base-color [0.05 0.03 0.02 1.0]
              :metallic 0.0 :roughness 0.3 :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
              :anisotropic 0.0 :clearcoat 0.9 :clearcoat-roughness 0.05 :emission [0.0 0.0 0.0]}
      :lip {:name "lip" :base-color (conj (vec lip-color) 1.0)
            :metallic 0.0 :roughness 0.3 :subsurface 0.5 :subsurface-color [0.9 0.4 0.3]
            :anisotropic 0.0 :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]}
      :eyebrow {:name "eyebrow" :base-color [(* (nth hair-color 0) 0.7) (* (nth hair-color 1) 0.6) (* (nth hair-color 2) 0.5) 1.0]
                :metallic 0.0 :roughness 0.7 :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
                :anisotropic 0.0 :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]}
      :hair {:name "hair" :base-color (conj (vec hair-color) 1.0)
             :metallic (+ 0.05 (* shininess 0.1)) :roughness (+ 0.25 (* (- 1.0 shininess) 0.25))
             :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
             :anisotropic (+ 0.6 (* shininess 0.3)) :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]}
      :clothing {:name "clothing" :base-color (conj (vec color) 1.0)
                 :metallic 0.0 :roughness 0.55 :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
                 :anisotropic 0.0 :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]}
      :eyelash {:name "eyelash" :base-color [0.08 0.06 0.04 1.0]
                :metallic 0.0 :roughness 0.5 :subsurface 0.0 :subsurface-color [0.0 0.0 0.0]
                :anisotropic 0.3 :clearcoat 0.0 :clearcoat-roughness 0.0 :emission [0.0 0.0 0.0]})))
