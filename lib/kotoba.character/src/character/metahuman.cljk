(ns character.metahuman
  "MetaHuman support — DNA calibration, FACS action units, LOD,
  extended face rig. Integrates an Unreal MetaHuman-compatible digital
  human pipeline: DNA-based parametric definition, FACS (Facial Action
  Coding System) action units (46 AUs + 52 ARKit mapped), LOD0-LOD3
  progressive mesh quality, extended skeleton with face rig bones,
  teeth/tongue/inner-mouth geometry, multi-layer skin SSS. Restored
  from the legacy kami-engine/kami-character Rust crate's
  `metahuman.rs` (deleted in kotoba-lang/kami-engine PR #82) as part
  of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root)."
  (:require [character.math :as m]
            [character.base-mesh :as base-mesh]
            [character.blendshape :as blendshape]
            [character.hair :as hair]
            [character.body :as body]
            [character.material :as material]))

;; ── LOD ───────────────────────────────────────────

(defn head-resolution [lod]
  (case lod :lod0 [128 192] :lod1 [80 120] :lod2 [48 64] :lod3 [24 32]))

(defn body-resolution [lod]
  (case lod :lod0 [40 48] :lod1 [28 36] :lod2 [20 28] :lod3 [12 16]))

;; ── FACS Action Units (46) ────────────────────────

(def facs-action-units
  [:au1-inner-brow-raise :au2-outer-brow-raise :au4-brow-lower :au5-upper-lid-raise
   :au6-cheek-raise :au7-lid-tighten :au9-nose-wrinkle :au10-upper-lip-raise
   :au11-nasolabial-deepen :au12-lip-corner-pull :au13-sharp-lip-pull :au14-dimple
   :au15-lip-corner-depress :au16-lower-lip-depress :au17-chin-raise :au18-lip-pucker
   :au20-lip-stretch :au22-lip-funnel :au23-lip-tighten :au24-lip-press :au25-lips-part
   :au26-jaw-drop :au27-mouth-stretch :au28-lip-suck :au29-jaw-thrust :au30-jaw-sideways
   :au31-jaw-clench :au32-lip-bite :au33-cheek-blow :au34-cheek-puff :au35-cheek-suck
   :au36-tongue-bulge :au37-lip-wipe :au38-nostril-dilate :au39-nostril-compress
   :au41-lid-droop :au42-slit :au43-eyes-closed :au44-squint :au45-blink :au46-wink
   :au51-head-turn-left :au52-head-turn-right :au53-head-up :au54-head-down
   :au55-head-tilt-left :au56-head-tilt-right])

;; ── MetaHuman DNA calibration ─────────────────────

(defn default-wrinkle-regions []
  {:forehead 0.3 :glabellar 0.2 :crows-feet 0.2 :nasolabial 0.3
   :under-eye 0.1 :perioral 0.1 :neck 0.1 :chin 0.1})

(defn default-skin-layers []
  {:epidermis-thickness 0.5 :melanin-density 0.3 :dermis-thickness 0.6
   :hemoglobin-density 0.4 :subdermal-scatter 0.5 :pore-density 0.5 :oiliness 0.3})

(defn default-metahuman-dna []
  {:archetype-weights [] :joint-deltas [] :skin-weight-overrides []
   :wrinkle-regions (default-wrinkle-regions) :skin-layers (default-skin-layers)
   :age 0.3 :asymmetry 0.05})

;; ── Head deformation passes ───────────────────────

(defn apply-age-deformation
  "Apply age-related deformation to head vertices."
  [verts age]
  (if (< age 0.01)
    verts
    (mapv
     (fn [[x y z]]
       (let [[x y] (if (and (< y -0.04) (> y -0.10))
                     (let [sag (* age 0.005 (max 0.0 (- 1.0 (Math/pow (/ (+ y 0.07) 0.03) 2))))
                           y (- y sag)
                           jowl-x (/ (max 0.0 (- (Math/abs (double x)) 0.04)) 0.04)
                           x (+ x (* (m/signum x) sag 0.3 (max 0.0 (- 1.0 jowl-x))))]
                       [x y])
                     [x y])
             nl-x (Math/abs (double (- (Math/abs (double x)) 0.025)))
             nl-y (max 0.0 (- 1.0 (Math/pow (/ (+ y 0.01) 0.04) 2)))
             z (if (and (< nl-x 0.008) (> nl-y 0.0))
                 (- z (* age 0.003 nl-y (- 1.0 (/ nl-x 0.008))))
                 z)
             z (reduce
                (fn [z ex]
                  (let [ed (m/sqrt (+ (Math/pow (- x ex) 2) (Math/pow (- y 0.035) 2)))]
                    (if (< ed 0.015) (- z (* age 0.002 (- 1.0 (/ ed 0.015)))) z)))
                z [-0.032 0.032])
             z (if (> y 0.10)
                 (let [t (min 1.0 (/ (- y 0.10) 0.02))] (- z (* age 0.002 t)))
                 z)]
         [x y z]))
     verts)))

(defn apply-asymmetry
  "Apply bilateral asymmetry to head vertices (deterministic via
  vertex-index hash)."
  [verts asymmetry]
  (if (< asymmetry 0.001)
    verts
    (vec
     (map-indexed
      (fn [i [x y z]]
        (let [hash (m/hash-u32-x i -1640531535)]
          (if (> x 0.0)
            [(+ x (* (- hash 0.5) asymmetry 0.002))
             (+ y (* (- (* hash 0.7) 0.35) asymmetry 0.001))
             z]
            [x y z])))
      verts))))

(defn apply-wrinkle-displacement
  "Apply wrinkle displacement to vertices (LOD-dependent detail)."
  [verts wrinkles lod]
  (let [scale (case lod :lod0 1.0 :lod1 0.6 :lod2 0.2 :lod3 0.0)]
    (if (< scale 0.01)
      verts
      (vec
       (map-indexed
        (fn [i [x y z]]
          (let [hash (m/hash-u32-x i -2048144789)
                z (if (and (> y 0.06) (< y 0.11))
                    (let [freq (m/sin (* y 300.0))
                          center (max 0.0 (- 1.0 (Math/pow (/ x 0.06) 2)))]
                      (+ z (* freq (:forehead wrinkles) scale 0.0005 center)))
                    z)
                z (reduce
                   (fn [z ex]
                     (let [d (m/sqrt (+ (Math/pow (- x ex) 2) (Math/pow (- y 0.04) 2)))]
                       (if (and (< d 0.02) (> d 0.008))
                         (let [radial (m/sin (* (- d 0.008) 500.0))]
                           (+ z (* radial (:crows-feet wrinkles) scale 0.0003)))
                         z)))
                   z [-0.05 0.05])
                nl-region (max 0.0 (- 1.0 (Math/pow (/ (+ y 0.01) 0.03) 2)))
                nl-x-dist (Math/abs (double (- (Math/abs (double x)) 0.022)))
                z (if (and (< nl-x-dist 0.005) (> nl-region 0.0))
                    (- z (* (:nasolabial wrinkles) scale 0.0006 nl-region (- 1.0 (/ nl-x-dist 0.005))))
                    z)
                z (if (= lod :lod0)
                    (let [front (m/clamp (/ z 0.08) 0.0 1.0)]
                      (+ z (* (- hash 0.5) 0.0002 front)))
                    z)]
            [x y z]))
        verts)))))

;; ── Body / teeth / tongue mesh ────────────────────

(defn generate-metahuman-body [{:keys [neck-thickness shoulder-width build height]} n-rings n-seg]
  (let [neck-thick (+ 0.035 (* neck-thickness 0.02))
        shoulder-w (+ 0.1 (* shoulder-width 0.08))
        vertices
        (vec
         (for [i (range (inc n-rings))
               :let [t (/ (double i) n-rings)
                     y (- -0.12 (* t 0.28 height))
                     [rx rz] (cond
                               (< t 0.2) [(+ neck-thick (* t 0.06)) (+ (* neck-thick 0.85) (* t 0.05))]
                               (< t 0.5) (let [s (- t 0.2)]
                                           [(+ neck-thick 0.012 (* s (/ (- shoulder-w neck-thick) 0.3)))
                                            (+ (* neck-thick 0.85) 0.01 (* s 0.1))])
                               :else (let [s (- t 0.5)]
                                       [(+ shoulder-w (* s 0.02) (* build 0.02))
                                        (+ 0.08 (* build 0.03) (* s 0.01))]))]
               j (range (inc n-seg))]
           (let [theta (* 2.0 m/pi (/ (double j) n-seg))
                 x (* rx (m/cos theta))
                 z (* rz (m/sin theta))
                 n (m/vec3-normalize [(m/cos theta) 0.0 (m/sin theta)])]
             {:position [x y z] :normal n :uv [(/ (double j) n-seg) t]})))
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i (inc n-seg)) j) b (+ a n-seg 1)]
                 [a b (inc a) (inc a) b (inc b)]))
             (range n-seg)))
          (range n-rings)))]
    {:name "body" :vertices vertices :indices indices :material :skin}))

(defn- generate-teeth [upper]
  (let [n-teeth 14
        arch-y (if upper -0.035 -0.042)
        arch-z 0.055
        tooth-h (if upper -0.006 0.006)
        hw 0.0015 hd 0.002
        tooth-results
        (for [t (range n-teeth)]
          (let [angle (+ (* -1.0 m/pi 0.45) (* m/pi 0.9 (/ (double t) (dec n-teeth))))
                cx (* 0.025 (m/sin angle))
                cz (+ arch-z (* 0.025 (m/cos angle)))
                cy arch-y
                perp [(m/cos angle) 0.0 (- (m/sin angle))]
                n-front (m/vec3-normalize [(m/sin angle) 0.0 (m/cos angle)])
                n-back (m/vec3-scale n-front -1.0)
                front-verts (for [dy [0.0 tooth-h] dw [(- hw) hw]]
                              {:position [(+ cx (* (nth perp 0) dw)) (+ cy dy) (+ cz (* (nth perp 2) dw) hd)]
                               :normal n-front :uv [0.0 0.0]})
                back-verts (for [dy [0.0 tooth-h] dw [(- hw) hw]]
                             {:position [(+ cx (* (nth perp 0) dw)) (+ cy dy) (- (+ cz (* (nth perp 2) dw)) hd)]
                              :normal n-back :uv [0.0 0.0]})]
            {:verts (vec (concat front-verts back-verts))}))
        vertices (vec (mapcat :verts tooth-results))
        indices
        (vec
         (mapcat
          (fn [t]
            (let [base-idx (* t 8)]
              [base-idx (+ base-idx 2) (+ base-idx 1) (+ base-idx 1) (+ base-idx 2) (+ base-idx 3)
               (+ base-idx 4) (+ base-idx 5) (+ base-idx 6) (+ base-idx 5) (+ base-idx 7) (+ base-idx 6)
               (+ base-idx 2) (+ base-idx 6) (+ base-idx 3) (+ base-idx 3) (+ base-idx 6) (+ base-idx 7)]))
          (range n-teeth)))
        name (if upper "teeth_upper" "teeth_lower")]
    {:name name :vertices vertices :indices indices :material :skin}))

(defn- generate-tongue []
  (let [n-seg 8 n-len 6
        vertices
        (vec
         (for [i (range (inc n-len))
               :let [t (/ (double i) n-len)
                     y (- -0.04 (* t 0.005))
                     z (+ 0.04 (* t 0.02))
                     w (* 0.008 (- 1.0 (* t 0.4)))]
               j (range (inc n-seg))]
           (let [s (/ (double j) n-seg)
                 x (* (- s 0.5) 2.0 w)
                 arch (* (m/sin (* s m/pi)) 0.002)]
             {:position [x (+ y arch) z] :normal [0.0 1.0 0.0] :uv [s t]})))
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i (inc n-seg)) j) b (+ a n-seg 1)]
                 [a b (inc a) (inc a) b (inc b)]))
             (range n-seg)))
          (range n-len)))]
    {:name "tongue" :vertices vertices :indices indices :material :lip}))

;; ── LOD mesh generation ────────────────────────────

(defn- generate-metahuman-lod [def dna lod]
  (let [[n-lat n-lon] (head-resolution lod)
        [body-rings body-seg] (body-resolution lod)
        {:keys [vertices indices]} (base-mesh/generate-head n-lat n-lon)
        head-verts (-> vertices
                        (blendshape/apply-face-shape (:face def))
                        (blendshape/apply-eye-shape (:eyes def))
                        (blendshape/apply-nose-shape (:nose def))
                        (blendshape/apply-mouth-shape (:mouth def))
                        (apply-age-deformation (:age dna))
                        (apply-asymmetry (:asymmetry dna))
                        (apply-wrinkle-displacement (:wrinkle-regions dna) lod))
        smooth-iters (case lod :lod0 3 :lod1 2 1)
        head-verts (base-mesh/laplacian-smooth head-verts indices smooth-iters 0.15)
        head-normals (base-mesh/compute-normals head-verts indices)
        head-uvs (base-mesh/frontal-uv head-verts)
        head-vertices (vec (map-indexed (fn [i pos] {:position pos :normal (nth head-normals i) :uv (nth head-uvs i)}) head-verts))
        head-part {:name "head" :vertices head-vertices :indices indices :material :skin}
        parts (into [head-part] (base-mesh/generate-eyes (:eyes def)))
        parts (conj parts (hair/generate-hair (:hair def)))
        parts (conj parts (generate-metahuman-body (:body def) body-rings body-seg))
        parts (conj parts (body/generate-clothing (:clothing def) (:body def)))
        parts (if (contains? #{:lod0 :lod1} lod)
                (into parts [(generate-teeth true) (generate-teeth false) (generate-tongue)])
                parts)]
    parts))

(defn generate-metahuman-skeleton
  "Generate MetaHuman extended skeleton with 47 face rig bones (13 VRM
  base + 34 face rig extensions)."
  [dna]
  (let [id-rot [0.0 0.0 0.0 1.0]
        b (fn [name parent pos] (body/bone name parent pos id-rot))
        bones
        [(b "hips" nil [0.0 -0.2 0.0]) (b "spine" 0 [0.0 0.08 0.0]) (b "chest" 1 [0.0 0.08 0.0])
         (b "upperChest" 2 [0.0 0.06 0.0]) (b "neck" 3 [0.0 0.06 0.0]) (b "head" 4 [0.0 0.06 0.0])
         (b "leftEye" 5 [-0.03 0.04 0.06]) (b "rightEye" 5 [0.03 0.04 0.06]) (b "jaw" 5 [0.0 -0.02 0.04])
         (b "leftShoulder" 3 [-0.04 0.04 0.0]) (b "leftUpperArm" 9 [-0.06 0.0 0.0])
         (b "rightShoulder" 3 [0.04 0.04 0.0]) (b "rightUpperArm" 11 [0.06 0.0 0.0])
         (b "leftUpperEyelid" 6 [0.0 0.005 0.005]) (b "leftLowerEyelid" 6 [0.0 -0.004 0.005])
         (b "rightUpperEyelid" 7 [0.0 0.005 0.005]) (b "rightLowerEyelid" 7 [0.0 -0.004 0.005])
         (b "leftBrowInner" 5 [-0.015 0.065 0.07]) (b "leftBrowMid" 5 [-0.03 0.068 0.065]) (b "leftBrowOuter" 5 [-0.045 0.063 0.055])
         (b "rightBrowInner" 5 [0.015 0.065 0.07]) (b "rightBrowMid" 5 [0.03 0.068 0.065]) (b "rightBrowOuter" 5 [0.045 0.063 0.055])
         (b "noseBridge" 5 [0.0 0.035 0.085]) (b "leftNostril" 5 [-0.008 0.005 0.08]) (b "rightNostril" 5 [0.008 0.005 0.08])
         (b "upperLipLeft" 5 [-0.012 -0.03 0.075]) (b "upperLipMid" 5 [0.0 -0.028 0.078]) (b "upperLipRight" 5 [0.012 -0.03 0.075])
         (b "lowerLipLeft" 8 [-0.012 -0.005 0.035]) (b "lowerLipMid" 8 [0.0 -0.007 0.038]) (b "lowerLipRight" 8 [0.012 -0.005 0.035])
         (b "leftLipCorner" 5 [-0.022 -0.032 0.068]) (b "rightLipCorner" 5 [0.022 -0.032 0.068])
         (b "leftCheek" 5 [-0.04 0.01 0.06]) (b "rightCheek" 5 [0.04 0.01 0.06])
         (b "leftNasolabial" 5 [-0.025 -0.01 0.07]) (b "rightNasolabial" 5 [0.025 -0.01 0.07])
         (b "chinTip" 8 [0.0 -0.02 0.03]) (b "mentalis" 8 [0.0 -0.012 0.035])
         (b "tongueRoot" 8 [0.0 0.0 0.01]) (b "tongueMid" 42 [0.0 0.0 0.008]) (b "tongueTip" 43 [0.0 0.0 0.008])
         (b "leftEar" 5 [-0.07 0.03 0.0]) (b "rightEar" 5 [0.07 0.03 0.0])]
        bones (reduce
               (fn [bones {:keys [bone-index position-delta]}]
                 (if (< bone-index (count bones))
                   (update bones bone-index #(update % :local-position (fn [p] (mapv + p position-delta))))
                   bones))
               (vec bones) (:joint-deltas dna))]
    {:bones bones}))

(def facs-names
  {:au1-inner-brow-raise "AU1_innerBrowRaise" :au2-outer-brow-raise "AU2_outerBrowRaise"
   :au4-brow-lower "AU4_browLower" :au5-upper-lid-raise "AU5_upperLidRaise"
   :au6-cheek-raise "AU6_cheekRaise" :au7-lid-tighten "AU7_lidTighten"
   :au9-nose-wrinkle "AU9_noseWrinkle" :au10-upper-lip-raise "AU10_upperLipRaise"
   :au11-nasolabial-deepen "AU11_nasolabialDeepen" :au12-lip-corner-pull "AU12_lipCornerPull"
   :au13-sharp-lip-pull "AU13_sharpLipPull" :au14-dimple "AU14_dimple"
   :au15-lip-corner-depress "AU15_lipCornerDepress" :au16-lower-lip-depress "AU16_lowerLipDepress"
   :au17-chin-raise "AU17_chinRaise" :au18-lip-pucker "AU18_lipPucker"
   :au20-lip-stretch "AU20_lipStretch" :au22-lip-funnel "AU22_lipFunnel"
   :au23-lip-tighten "AU23_lipTighten" :au24-lip-press "AU24_lipPress"
   :au25-lips-part "AU25_lipsPart" :au26-jaw-drop "AU26_jawDrop"
   :au27-mouth-stretch "AU27_mouthStretch" :au28-lip-suck "AU28_lipSuck"
   :au29-jaw-thrust "AU29_jawThrust" :au30-jaw-sideways "AU30_jawSideways"
   :au31-jaw-clench "AU31_jawClench" :au32-lip-bite "AU32_lipBite"
   :au33-cheek-blow "AU33_cheekBlow" :au34-cheek-puff "AU34_cheekPuff"
   :au35-cheek-suck "AU35_cheekSuck" :au36-tongue-bulge "AU36_tongueBulge"
   :au37-lip-wipe "AU37_lipWipe" :au38-nostril-dilate "AU38_nostrilDilate"
   :au39-nostril-compress "AU39_nostrilCompress" :au41-lid-droop "AU41_lidDroop"
   :au42-slit "AU42_slit" :au43-eyes-closed "AU43_eyesClosed" :au44-squint "AU44_squint"
   :au45-blink "AU45_blink" :au46-wink "AU46_wink"
   :au51-head-turn-left "AU51_headTurnLeft" :au52-head-turn-right "AU52_headTurnRight"
   :au53-head-up "AU53_headUp" :au54-head-down "AU54_headDown"
   :au55-head-tilt-left "AU55_headTiltLeft" :au56-head-tilt-right "AU56_headTiltRight"})

(def facs-wrinkle-intensities
  {:au1-inner-brow-raise 0.4 :au2-outer-brow-raise 0.3 :au4-brow-lower 0.5 :au5-upper-lid-raise 0.2
   :au6-cheek-raise 0.6 :au7-lid-tighten 0.2 :au9-nose-wrinkle 0.7 :au10-upper-lip-raise 0.3
   :au11-nasolabial-deepen 0.5 :au12-lip-corner-pull 0.4 :au13-sharp-lip-pull 0.3 :au14-dimple 0.4
   :au15-lip-corner-depress 0.3 :au16-lower-lip-depress 0.2 :au17-chin-raise 0.5 :au18-lip-pucker 0.3
   :au20-lip-stretch 0.4 :au22-lip-funnel 0.3 :au23-lip-tighten 0.2 :au24-lip-press 0.2 :au25-lips-part 0.1
   :au26-jaw-drop 0.2 :au27-mouth-stretch 0.3 :au28-lip-suck 0.3 :au29-jaw-thrust 0.2 :au30-jaw-sideways 0.1
   :au31-jaw-clench 0.3 :au32-lip-bite 0.4 :au33-cheek-blow 0.5 :au34-cheek-puff 0.5 :au35-cheek-suck 0.4
   :au36-tongue-bulge 0.3 :au37-lip-wipe 0.2 :au38-nostril-dilate 0.3 :au39-nostril-compress 0.3
   :au41-lid-droop 0.2 :au42-slit 0.2 :au43-eyes-closed 0.2 :au44-squint 0.3 :au45-blink 0.2 :au46-wink 0.2
   :au51-head-turn-left 0.0 :au52-head-turn-right 0.0 :au53-head-up 0.0 :au54-head-down 0.0
   :au55-head-tilt-left 0.0 :au56-head-tilt-right 0.0})

(defn generate-facs-targets
  "Generate FACS blendshape targets: 46 action units + head AU
  (51-56) = 47 total, each producing zero-placeholder vertex deltas."
  [n-verts]
  (mapv (fn [au] {:action-unit au :name (get facs-names au) :deltas (vec (repeat n-verts m/vec3-zero))
                   :wrinkle-intensity (get facs-wrinkle-intensities au 0.0)})
        facs-action-units))

(defn generate-metahuman
  "Generate MetaHuman-quality character from DNA and base CharacterDef.
  Produces LOD0-LOD3 meshes, FACS blendshapes, and extended face rig."
  [def dna lods]
  (let [lod-meshes (mapv #(generate-metahuman-lod def dna %) lods)
        skeleton (generate-metahuman-skeleton dna)
        lod0-head-verts (if-let [lod0 (first lod-meshes)]
                           (count (:vertices (first (filter #(= (:name %) "head") lod0))))
                           0)
        facs-targets (generate-facs-targets lod0-head-verts)
        arkit-targets (blendshape/generate-arkit-targets lod0-head-verts)]
    {:lod-meshes lod-meshes :skeleton skeleton :facs-targets facs-targets
     :arkit-targets arkit-targets :dna dna}))

;; ── MetaHuman-specific PBR materials ──────────────

(defn metahuman-material-to-pbr
  "Generate PBR material for MetaHuman-specific parts. `id` is
  `[:base base-material-id]` or one of `:teeth-upper :teeth-lower :gum
  :tongue :oral-mucosa :tear-film :sclera :cornea`."
  [id skin-layers]
  (cond
    (and (vector? id) (= (first id) :base))
    {:name (clojure.core/name (second id)) :base-color [0.9 0.8 0.75 1.0] :metallic 0.0 :roughness 0.4
     :subsurface (+ (* (:epidermis-thickness skin-layers) 0.5) (* (:dermis-thickness skin-layers) 0.3))
     :subsurface-color [(- 0.9 (* (:melanin-density skin-layers) 0.3))
                         (+ 0.5 (* (:hemoglobin-density skin-layers) 0.2)) 0.35]
     :anisotropic 0.0 :clearcoat (* (:oiliness skin-layers) 0.3) :clearcoat-roughness 0.2 :emission [0.0 0.0 0.0]}

    (contains? #{:teeth-upper :teeth-lower} id)
    {:name "teeth" :base-color [0.95 0.93 0.88 1.0] :metallic 0.0 :roughness 0.2 :subsurface 0.4
     :subsurface-color [0.92 0.85 0.75] :anisotropic 0.0 :clearcoat 0.6 :clearcoat-roughness 0.1 :emission [0.0 0.0 0.0]}

    (= id :gum)
    {:name "gum" :base-color [0.75 0.45 0.45 1.0] :metallic 0.0 :roughness 0.35 :subsurface 0.6
     :subsurface-color [0.8 0.3 0.25] :anisotropic 0.0 :clearcoat 0.2 :clearcoat-roughness 0.3 :emission [0.0 0.0 0.0]}

    (= id :tongue)
    {:name "tongue" :base-color [0.78 0.48 0.48 1.0] :metallic 0.0 :roughness 0.45 :subsurface 0.5
     :subsurface-color [0.85 0.35 0.3] :anisotropic 0.0 :clearcoat 0.3 :clearcoat-roughness 0.2 :emission [0.0 0.0 0.0]}

    (= id :oral-mucosa)
    {:name "oral_mucosa" :base-color [0.7 0.4 0.38 1.0] :metallic 0.0 :roughness 0.3 :subsurface 0.7
     :subsurface-color [0.8 0.3 0.2] :anisotropic 0.0 :clearcoat 0.4 :clearcoat-roughness 0.15 :emission [0.0 0.0 0.0]}

    (= id :tear-film)
    {:name "tear_film" :base-color [0.98 0.98 0.98 0.3] :metallic 0.0 :roughness 0.05 :subsurface 0.0
     :subsurface-color [0.0 0.0 0.0] :anisotropic 0.0 :clearcoat 1.0 :clearcoat-roughness 0.02 :emission [0.0 0.0 0.0]}

    (= id :sclera)
    {:name "sclera" :base-color [0.97 0.96 0.95 1.0] :metallic 0.0 :roughness 0.12 :subsurface 0.4
     :subsurface-color [0.95 0.85 0.82] :anisotropic 0.0 :clearcoat 0.5 :clearcoat-roughness 0.08 :emission [0.0 0.0 0.0]}

    (= id :cornea)
    {:name "cornea" :base-color [1.0 1.0 1.0 0.05] :metallic 0.0 :roughness 0.02 :subsurface 0.0
     :subsurface-color [0.0 0.0 0.0] :anisotropic 0.0 :clearcoat 1.0 :clearcoat-roughness 0.01 :emission [0.0 0.0 0.0]}))

;; ── FACS -> ARKit mapping ──────────────────────────

(defn facs-to-arkit
  "Map FACS action units to ARKit blendshape weights. Returns a vector
  of `[arkit-target-index weight]` pairs for a given AU activation
  (indices match `character.blendshape/arkit-names` order)."
  [au intensity]
  (case au
    :au1-inner-brow-raise [[43 intensity]]
    :au2-outer-brow-raise [[44 intensity] [45 intensity]]
    :au4-brow-lower [[42 (* intensity 0.7)] [43 (- (* intensity 0.5))]]
    :au5-upper-lid-raise [[12 intensity] [13 intensity]]
    :au6-cheek-raise [[47 intensity] [48 intensity]]
    :au7-lid-tighten [[10 (* intensity 0.6)] [11 (* intensity 0.6)]]
    :au9-nose-wrinkle [[49 intensity] [50 intensity]]
    :au10-upper-lip-raise [[40 intensity] [41 intensity]]
    :au12-lip-corner-pull [[23 intensity] [24 intensity]]
    :au14-dimple [[27 intensity] [28 intensity]]
    :au15-lip-corner-depress [[25 intensity] [26 intensity]]
    :au16-lower-lip-depress [[37 intensity] [38 intensity]]
    :au17-chin-raise [[33 intensity]]
    :au18-lip-pucker [[20 intensity]]
    :au20-lip-stretch [[29 intensity] [30 intensity]]
    :au22-lip-funnel [[19 intensity]]
    :au25-lips-part [[18 (* intensity 0.3)]]
    :au26-jaw-drop [[17 intensity]]
    :au34-cheek-puff [[46 intensity]]
    (:au43-eyes-closed :au45-blink) [[0 intensity] [1 intensity]]
    :au51-head-turn-left [[15 intensity]]
    :au52-head-turn-right [[16 intensity]]
    :au36-tongue-bulge [[51 intensity]]
    []))
