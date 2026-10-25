(ns character.hair-gen
  "Parametric hair generator — `HairStyle` -> Strands / Hair Cards /
  Hair Mesh. Restored from the legacy kami-engine/kami-character Rust
  crate's `hair_gen.rs` (deleted in kotoba-lang/kami-engine PR #82) as
  part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root)."
  (:require [character.math :as m]
            [character.groom :as groom]
            [character.export :as export]
            [character.params :as params]))

(def hair-types #{:straight :wavy :curly :afro :braided})
(def hair-render-modes #{:strands :cards :mesh})

(defn default-hair-style []
  {:style :straight
   :length 0.7 :density 0.8 :volume 0.5 :curl 0.03
   :part-side 0.1 :bangs-length 0.3 :bangs-width 0.5
   :color [0.93 0.86 0.72] :highlight-color [0.97 0.92 0.82]
   :highlight-ratio 0.35 :root-darken 0.7
   :head-radius 0.09 :head-center-y 1.43})

(defn blonde-long [] (default-hair-style))

(defn dark-short []
  (merge (default-hair-style)
         {:style :straight :length 0.2 :density 0.9 :volume 0.3 :curl 0.02
          :part-side 0.0 :bangs-length 0.15 :bangs-width 0.6
          :color [0.12 0.08 0.06] :highlight-color [0.20 0.15 0.12]
          :highlight-ratio 0.15 :root-darken 0.5}))

(defn red-wavy []
  (merge (default-hair-style)
         {:style :wavy :length 0.6 :density 0.8 :volume 0.7 :curl 0.25
          :part-side -0.2 :bangs-length 0.35 :bangs-width 0.4
          :color [0.55 0.18 0.10] :highlight-color [0.70 0.30 0.18]
          :highlight-ratio 0.25 :root-darken 0.6}))

(defn brown-curly []
  (merge (default-hair-style)
         {:style :curly :length 0.5 :density 0.9 :volume 0.8 :curl 0.6
          :part-side 0.0 :bangs-length 0.2 :bangs-width 0.5
          :color [0.25 0.15 0.08] :highlight-color [0.35 0.22 0.12]
          :highlight-ratio 0.2 :root-darken 0.5}))

(defn afro []
  (merge (default-hair-style)
         {:style :afro :length 0.3 :density 1.0 :volume 1.0 :curl 0.9
          :part-side 0.0 :bangs-length 0.0 :bangs-width 0.0
          :color [0.08 0.05 0.03] :highlight-color [0.15 0.10 0.06]
          :highlight-ratio 0.1 :root-darken 0.4}))

(def hash-f32 m/hash-f32)

(defn- strand-root
  "Compute strand root position on scalp + strand direction `theta`."
  [{:keys [head-radius head-center-y part-side] :as _style} is-bangs h1 h2]
  (let [r head-radius
        cy head-center-y
        theta (if is-bangs
                (+ (* m/pi 0.35) (* h2 m/pi 0.3))
                (+ m/pi (* h2 m/pi)))
        phi (* h1 m/pi 0.33)
        part-offset (* part-side r 0.5)
        root [(+ part-offset (* (+ r 0.001) (m/sin phi) (m/cos theta)))
              (+ cy (* r 1.2 (m/cos phi)))
              (* (* r 0.95) (m/sin phi) (m/sin theta))]]
    [root theta]))

(defn- strand-point
  "Compute a point along a strand at parameter `t` (0=root, 1=tip)."
  [root theta t strand-len {:keys [style curl volume head-radius] :as _style-map} h3 is-bangs]
  (let [curl-freq (case style :straight 0.5 :wavy 2.5 :curly 5.0 :afro 8.0 :braided 3.0)
        curl-amp (* curl head-radius 0.8)
        afro-vol (if (= style :afro) (* volume 0.15) 0.0)
        grav (if (= style :afro) (* t 0.3) (* t t))
        curl-v (* (m/sin (+ (* t curl-freq) (* h3 7.0))) curl-amp t)
        outward (+ (* afro-vol t) (* t 0.2 (- 1.0 t)))
        r head-radius
        [rx ry rz] root]
    [(+ rx (* outward r (m/cos theta) 0.15) curl-v)
     (- ry (* strand-len (+ (* t (if is-bangs 0.6 0.15)) (* grav (if is-bangs 0.4 0.85)))))
     (+ rz (* outward r (m/sin theta) 0.15) (if is-bangs (* t strand-len 0.05) 0.0))]))

;; ── Mode 1: Strands (GroomAsset) ───

(defn- generate-groom-inner [{:keys [head-radius length bangs-width bangs-length highlight-ratio] :as style} points-per-strand strand-count]
  (let [base-length (* head-radius 2.0 (+ 0.3 (* length 2.5)))
        strands
        (vec
         (for [si (range strand-count)]
           (let [h1 (hash-f32 si 42)
                 h2 (hash-f32 si 99)
                 h3 (hash-f32 si 77)
                 is-bangs (and (< (double si) (* strand-count bangs-width 0.05)) (> bangs-length 0.05))
                 [root theta] (strand-root style is-bangs h1 h2)
                 strand-len (if is-bangs (* base-length bangs-length 0.5) (* base-length (+ 0.7 (* h1 0.3))))
                 points (vec (for [pi (range points-per-strand)]
                               (let [t (/ (double pi) (dec points-per-strand))]
                                 (strand-point root theta t strand-len style h3 is-bangs))))
                 widths (vec (for [pi (range points-per-strand)]
                               (let [t (/ (double pi) (dec points-per-strand))]
                                 (* 0.0008 (- 1.0 (* t 0.7)) (+ 1.0 (* (:volume style) 0.5))))))]
             (groom/strand points widths [(/ theta (* 2.0 m/pi)) h1] (if (> h3 (- 1.0 highlight-ratio)) 1 0)))))
        guide-indices (vec (range 0 (count strands) 4))
        total-points (reduce + (map #(count (:points %)) strands))]
    {:strands strands :guide-indices guide-indices :total-points total-points
     :groups [(groom/groom-group "base" strand-count 0 0.5 0.1)
              (groom/groom-group "highlight" 0 1 0.3 0.05)]}))

(defn generate-groom
  "Generate strand curves from HairStyle. Default density=0.8 -> ~160
  strands. For 100K strands, use `generate-groom-count`."
  [style points-per-strand]
  (generate-groom-inner style points-per-strand (int (* 200.0 (:density style)))))

(defn generate-groom-count
  "Generate groom with explicit strand count (e.g. 100000 for cinematic
  quality)."
  [style points-per-strand strand-count]
  (generate-groom-inner style points-per-strand strand-count))

;; ── Mode 2: Hair Cards ───

(defn generate-hair-cards
  "Generate hair card quads from HairStyle. For rasterization."
  [style]
  (let [g (generate-groom style 8)
        cards-count (max 1 (quot (count (:strands g)) 10))]
    (groom/to-hair-cards g cards-count)))

;; ── Mode 3: Hair Mesh (polygon shell) ───

(defn generate-hair-mesh
  "Generate a polygon shell hair mesh from HairStyle. Creates layered
  ribbon strips forming a volumetric hair shape."
  [{:keys [head-radius length density bangs-width bangs-length volume] :as style}]
  (let [base-length (* head-radius 2.0 (+ 0.3 (* length 2.5)))
        n-strips (int (* 80.0 density))
        n-layers 3
        segs-per-strip 12
        layer-results
        (for [layer (range n-layers)]
          (let [layer-t (/ (double layer) (max 1 (dec n-layers)))
                layer-offset (* layer-t head-radius 0.08 (+ 1.0 volume))
                layer-len-mul (- 1.0 (* layer-t 0.3))
                strip-results
                (for [si (range n-strips)]
                  (let [h1 (hash-f32 (+ si (* layer 1000)) 42)
                        h2 (hash-f32 (+ si (* layer 1000)) 99)
                        h3 (hash-f32 (+ si (* layer 1000)) 77)
                        is-bangs (and (< (double si) (* n-strips bangs-width 0.05)) (> bangs-length 0.05))
                        [root theta] (strand-root style is-bangs h1 h2)
                        strand-len (if is-bangs (* base-length bangs-length 0.5)
                                       (* base-length (+ 0.6 (* h1 0.4)) layer-len-mul))
                        strip-w (* head-radius (+ 0.03 (* h3 0.04)) (+ 1.0 (* volume 0.3)))
                        outward-dir [(m/cos theta) 0.0 (m/sin theta)]
                        perp [(- (m/sin theta)) 0.0 (m/cos theta)]]
                    (for [seg (range (inc segs-per-strip))]
                      (let [t (/ (double seg) segs-per-strip)
                            p (m/vec3+ (strand-point root theta t strand-len style h3 is-bangs)
                                       (m/vec3-scale outward-dir layer-offset))
                            w (* strip-w (- 1.0 (* t 0.25)))
                            left (m/vec3- p (m/vec3-scale perp w))
                            right (m/vec3+ p (m/vec3-scale perp w))
                            [px _py pz] p
                            [rx _ry rz] root
                            n (m/vec3-normalize-or-zero [(- px rx) 0.2 (- pz rz)])]
                        {:left left :right right :normal n :t t}))))
                vertices (vec (mapcat (fn [segs] (mapcat (fn [{:keys [left right normal t]}]
                                                            [{:position left :normal normal :uv [0.0 t]}
                                                             {:position right :normal normal :uv [1.0 t]}])
                                                          segs))
                                       strip-results))
                indices (vec (mapcat
                              (fn [strip-idx]
                                (let [base-idx (* strip-idx (inc segs-per-strip) 2)]
                                  (mapcat (fn [seg]
                                            (if (pos? seg)
                                              (let [i (+ base-idx (* (dec seg) 2))]
                                                [i (+ i 2) (+ i 1) (+ i 1) (+ i 2) (+ i 3)])
                                              []))
                                          (range (inc segs-per-strip)))))
                              (range n-strips)))
                layer-name (case layer 0 "hair_outer" 1 "hair_mid" "hair_inner")]
            {:name layer-name :vertices vertices :indices indices :material :hair}))
        total-verts (reduce + (map #(count (:vertices %)) layer-results))
        total-tris (reduce + (map #(quot (count (:indices %)) 3) layer-results))]
    {:parts (vec layer-results) :total-vertices total-verts :total-triangles total-tris}))

(defn generate-hair-mesh-data
  "Generate hair mesh as flat arrays for GPU upload (interleaved
  pos+norm+uv + indices)."
  [style]
  (let [{:keys [parts total-vertices total-triangles]} (generate-hair-mesh style)]
    (loop [parts parts vert-offset 0 vertices (transient []) indices (transient [])]
      (if (empty? parts)
        {:vertex-count total-vertices :triangle-count total-triangles
         :vertices (persistent! vertices) :indices (persistent! indices)}
        (let [part (first parts)
              pverts (:vertices part)
              pidx (:indices part)
              vertices (reduce (fn [vs {:keys [position normal uv]}]
                                  (let [[px py pz] position [nx ny nz] normal [u v] uv]
                                    (-> vs (conj! px) (conj! py) (conj! pz)
                                        (conj! nx) (conj! ny) (conj! nz)
                                        (conj! u) (conj! v))))
                                vertices pverts)
              indices (reduce (fn [is idx] (conj! is (+ idx vert-offset))) indices pidx)]
          (recur (rest parts) (+ vert-offset (count pverts)) vertices indices))))))

(defn generate-hair-glb
  "Export hair mesh as GLB binary."
  [style]
  (let [mesh (generate-hair-mesh style)
        char-mesh {:parts (:parts mesh) :skeleton nil :blendshape-targets []}
        def (params/default-character-def)]
    (export/export-glb char-mesh def)))
