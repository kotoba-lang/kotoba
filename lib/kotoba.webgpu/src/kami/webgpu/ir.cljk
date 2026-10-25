(ns kami.webgpu.ir
  "render-IR — the EDN data the renderer consumes (hiccup for WebGPU).

   This namespace is .cljc: it holds the *shape* of a frame and pure constructors
   for building it. It contains NO platform code — it works identically in Clojure,
   ClojureScript, and (read as plain EDN) Rust / Datomic. The browser executor that
   turns this data into WebGPU draw calls lives in `kami.webgpu` (.cljs).

   A render-IR is a plain map:

     {:globals   {:sky    {:horizon [r g b]      ;; clear / ambient sky colour
                           :sun-dir [x y z]       ;; directional light (world space)
                           :sun     [r g b]}      ;; sun colour
                  :lighting {…}                   ;; lighting-model coefficients (optional —
                  :eye    [x y z]                 ;;   `default-lighting` below fills the rest)
                  :target [x y z]}                ;;   else an overview is derived)
      :instances [{:pos   [x y z]                 ;; world position (ground at y)
                   :color [r g b]                 ;; albedo
                   :size  [w h d]                 ;; width × height × depth
                                                  ;; legacy [w h] means depth=w
                   :yaw   theta                    ;; rotation about Y (radians)
                   :metallic m :roughness r :emissive e
                   :textured? true}]} ;; sample bound albedo/normal/MR textures

   A material is just the PBR fields — author a palette as data and merge it into
   instances (or store it as Datomic datoms and query/as-of/fork it):

      {:metallic 0.0 :roughness 0.65 :emissive 0.0}

   Everything is data: build it with assoc/update/merge, store it in Datomic, send
   it over the wire, fork it. Future keys (:passes, :pipelines, :materials, WGSL as
   EDN) extend the same map without changing the contract — the executor reads what
   it understands and ignores the rest."
  (:require [kami.webgpu.geometry :as geom]
            [kotoba.render.building :as building]
            [kotoba.render.terrain :as terrain]
            [kotoba.render.terrain-biome :as terrain-biome]
            [kotoba.render.road :as road]))

(defn material
  "A PBR material — pure data. metallic 0=dielectric…1=metal; roughness 0=mirror…1=matte;
   emissive ≥0 = self-glow (× albedo). Store these as datoms and query/as-of/fork them."
  [& {:keys [metallic roughness emissive textured?]
      :or {metallic 0.0 roughness 0.65 emissive 0.0 textured? false}}]
  {:metallic metallic :roughness roughness :emissive emissive :textured? textured?})

;; --- lighting model: the shader's look, as data -------------------------------
;; The fragment shader used to bake these coefficients in as literals; now they are EDN under
;; the frame's [:globals :lighting]. `default-lighting` reproduces the original constants
;; EXACTLY, so a frame that omits :lighting renders identically — authoring it is opt-in.
;; A game overrides any subset in its scene.edn :render/lighting (e.g. a warmer ambient, a
;; punchier rim) and the executor merges it over these defaults. Store it as datoms, fork it.

(def default-lighting
  {:ambient              [0.20 0.22 0.26] ;; hemisphere ground/ambient colour (down-facing)
   :ambient-sky          0.65             ;; how much sky colour bleeds into the up-facing ambient
   :spec-min             0.25             ;; specular strength — dielectric
   :spec-max             0.90             ;; specular strength — metal
   :rim                  0.25             ;; Fresnel rim-light strength
   :rim-power            3.0              ;; rim falloff exponent
   :shininess-min        4.0              ;; Blinn-Phong exponent — rough surface
   :shininess-max        256.0            ;; Blinn-Phong exponent — smooth surface
   :sun-diffuse          0.9              ;; direct-sun diffuse scale
   :metallic-diffuse-cut 0.7              ;; how strongly metal suppresses diffuse
   :gamma                2.2              ;; output gamma (encoding exponent)
   :shadow-bias-slope    0.0025           ;; shadow depth-bias, scaled by (1 - N·L)
   :shadow-bias-min      0.0006           ;; shadow depth-bias floor
   :shadow-texel         (/ 1.0 2048.0)}) ;; 1 / shadow-map size (match :targets :shadow :size)

(defn lighting
  "A lighting map merged over the defaults — pass a partial override, get a complete map."
  [m] (merge default-lighting m))

;; --- sun shadow frustum: the directional light's orthographic camera, as data ----
;; draw! used to bake the shadow frustum in (ortho ±130, near 1, far 420, light 200 units
;; back along the sun). Now it's [:globals :shadow]; defaults reproduce the old frustum, so
;; omitting it changes nothing. Widen :extent for a bigger world, raise :distance to keep
;; tall geometry inside the light's depth range. (:shadow-texel — the PCF tap size — lives in
;; the lighting map and should track the :targets :shadow :size in the render graph.)

(def default-shadow
  {:extent   130.0   ;; half-width of the ortho light frustum (world units)
   :near     1.0     ;; light near plane
   :far      420.0   ;; light far plane
   :distance 200.0}) ;; how far back along -sun-dir the light is placed

(defn shadow
  "A shadow-frustum map merged over the defaults — partial override → complete map."
  [m] (merge default-shadow m))

;; --- geometry library: the :geo mesh kinds, as data ------------------------------
;; The executor used to hardcode three meshes (box/sphere/cylinder at fixed tessellation).
;; Now each `:geo` kind is a {:type … params} spec, baked into a mesh by `mesh-from-spec`
;; via kami.webgpu.geometry (the shared cross-platform mesh source). `default-geometry`
;; reproduces the original three EXACTLY; pass {:geometry {…}} to init! to add a kind (e.g.
;; :plane) or retessellate one — an instance then references the kind by its `:geo` keyword.

(def default-geometry
  {:box      {:type :box      :size [1 1 1]}
   :sphere   {:type :sphere   :r 0.5 :rings 14 :sectors 20}
   :sphere-lod1 {:type :sphere :r 0.5 :rings 6 :sectors 10}
   :cylinder {:type :cylinder :r 0.5 :h 1 :sectors 20}
   :cylinder-lod1 {:type :cylinder :r 0.5 :h 1 :sectors 8}
   :stepped-tower {:type :building :variant :stepped-tower :detail :high :seed 17}
   :stepped-tower-lod1 {:type :building :variant :stepped-tower :detail :medium :seed 17}
   :stepped-tower-lod2 {:type :building :variant :stepped-tower :detail :low :seed 17}
   :industrial-block {:type :building :variant :industrial-block :detail :high :seed 29}
   :industrial-block-lod1 {:type :building :variant :industrial-block :detail :medium :seed 29}
   :industrial-block-lod2 {:type :building :variant :industrial-block :detail :low :seed 29}})

(defn- building-geometry [{:keys [variant detail seed]}]
  (let [[positions normals uvs indices]
        (building/building-mesh {:variant variant :width 1.0 :depth 1.0
                                 :height 1.0 :seed (or seed 0)}
                                (or detail :high))]
    {:positions (mapv vec (partition 3 positions))
     :normals (mapv vec (partition 3 normals))
     :uvs (mapv vec (partition 2 uvs))
     :indices indices}))

(defn- registered-mesh [{:keys [mesh]}]
  (let [{:keys [positions normals biome-weights biome-layer-indices indices]} mesh
        vertex-count (count positions)]
    (when-not (and (map? mesh)
                   (seq positions)
                   (seq indices)
                   (= vertex-count (count normals))
                   (or (nil? biome-weights) (= vertex-count (count biome-weights)))
                   (or (nil? biome-layer-indices) (= vertex-count (count biome-layer-indices)))
                   (every? #(= 3 (count %)) positions)
                   (every? #(= 3 (count %)) normals)
                   (zero? (mod (count indices) 3))
                   (every? #(< -1 % vertex-count) indices))
      (throw (ex-info "invalid registered geometry mesh"
                      {:vertex-count vertex-count :normal-count (count normals)
                       :index-count (count indices)})))
    (select-keys mesh [:positions :normals :uvs :biome-weights :biome-layer-indices :indices])))

(defn- terrain-geometry [{:keys [detail] :as spec}]
  (let [[positions normals uvs indices]
        (terrain/terrain-mesh
         (select-keys spec [:patch :size :base-segments :amplitude :seed :skirt-depth])
         (or detail :high))
        positions (mapv vec (partition 3 positions))
        normals (mapv vec (partition 3 normals))
        biome (or (:biome spec) terrain-biome/default-biome)
        by-id (into {} (map (juxt :id :texture-layer) (:layers biome)))
        layer-indices (mapv by-id [:grass :soil :rock])]
    {:positions positions
     :normals normals
     :uvs (mapv vec (partition 2 uvs))
     :biome-weights (terrain-biome/mesh-weights
                     biome
                     [(vec (mapcat identity positions)) (vec (mapcat identity normals)) uvs indices])
     :biome-layer-indices (vec (repeat (count positions) layer-indices))
     :indices indices}))

(defn- road-ribbon-geometry [{:keys [detail part] :as spec}]
  (let [road-spec (select-keys spec [:path :width :shoulder :camber :shoulder-drop
                                      :clearance :uv-scale :base-subdivisions
                                      :miter-limit :terrain :marking])
        parts (road/road-mesh-parts road-spec (or detail :high))
        [positions normals uvs indices]
        (or (get parts (or part :surface))
            (throw (ex-info "unsupported road ribbon material part"
                            {:part part :supported (set (keys parts))})))]
    {:positions (mapv vec (partition 3 positions))
     :normals (mapv vec (partition 3 normals))
     :uvs (mapv vec (partition 2 uvs))
     :indices indices}))

(defn mesh-from-spec
  "Bake one geometry spec → a mesh {:positions :normals :indices}. Pure + cross-platform
   (a native executor reimplements this dispatch over the same data). Unknown :type → unit box."
  [{:keys [type size r rings sectors h w d] :as spec}]
  (case type
    :box      (let [s (or size [1 1 1])] (geom/box (nth s 0) (nth s 1) (nth s 2)))
    :sphere   (geom/sphere (or r 0.5) (or rings 14) (or sectors 20))
    :cylinder (geom/cylinder (or r 0.5) (or h 1) (or sectors 20))
    :plane    (geom/plane (or w 10) (or d 10))
    :building (building-geometry spec)
    :mesh     (registered-mesh spec)
    :terrain  (terrain-geometry spec)
    :road-ribbon (road-ribbon-geometry spec)
    (geom/box 1 1 1)))

(defn geometry-biome-evidence
  "Summarize biome attributes on the baked meshes handed to a renderer upload.
   Pixel/vertex payloads stay private; capture gates receive only mesh/vertex
   counts and the distinct grass/soil/rock texture-layer mappings."
  [meshes]
  (let [weighted (keep (fn [[_ {:keys [biome-weights biome-layer-indices] :as mesh}]]
                         (when (and (seq biome-weights)
                                    (= (count (:positions mesh)) (count biome-weights))
                                    (= (count biome-weights) (count biome-layer-indices))
                                    (some #(some pos? %) biome-weights))
                           mesh))
                       meshes)]
    {:uploaded-biome-mesh-count (count weighted)
     :uploaded-biome-vertex-count (reduce + 0 (map (comp count :positions) weighted))
     :layer-index-mappings (->> weighted
                                (mapcat :biome-layer-indices)
                                distinct
                                sort
                                vec)}))

(defn geometry-decal-evidence
  "Summarize uploaded terrain-decal contracts without exposing texture pixels.
   The geometry is already physically normal-biased by the portable baker;
   this proves the executor received the matching projection/material metadata."
  [specs meshes]
  (let [entries (keep (fn [[id {:keys [decal]}]]
                        (when decal [id decal (get meshes id)])) specs)
        biases (map #(get-in % [1 :depth-bias]) entries)]
    {:schema :kotoba.webgpu/decal-evidence-v1
     :uploaded-decal-mesh-count (count entries)
     :uploaded-decal-vertex-count (reduce + 0 (map #(count (get-in % [2 :positions])) entries))
     :projections (->> entries (map #(get-in % [1 :projection])) distinct sort vec)
     :alpha-modes (->> entries (map #(get-in % [1 :alpha-mode])) distinct sort vec)
     :depth-bias-range (when (seq biases) [(apply min biases) (apply max biases)])
     :pbr-bound-count (count (filter #(map? (get-in % [1 :pbr])) entries))}))

(defn instance
  "An instanced cuboid. `size` is `[width height depth]`; legacy `[w h]`
   remains supported and means `[w h w]`. Pure data. Merge a `material` map in
   for PBR."
  [pos color size & {:keys [yaw metallic roughness emissive textured?] :or {yaw 0}}]
  (cond-> {:pos pos :color color :size size :yaw yaw}
    metallic  (assoc :metallic metallic)
    roughness (assoc :roughness roughness)
    emissive  (assoc :emissive emissive)
    textured? (assoc :textured? true)))

(defn instance-size
  "Normalize an instance size to `[width height depth]`. The historical two-axis
   form described a square x/z footprint, so `[w h]` expands to `[w h w]`."
  [size]
  (let [[width height depth] (or size [1 1 1])]
    [(or width 1) (or height 1) (or depth width 1)]))

(defn sky
  [horizon sun-dir sun]
  {:horizon horizon :sun-dir sun-dir :sun sun})

(defn render-ir
  "Assemble a frame's render-IR from sky, instances, and an optional camera."
  ([sky-map instances] {:globals {:sky sky-map} :instances (vec instances)})
  ([sky-map instances eye target]
   {:globals {:sky sky-map :eye eye :target target} :instances (vec instances)}))

(defn with-camera
  "Return ir with the camera set to eye→target (3rd-person follow, overview, …)."
  [ir eye target]
  (-> ir (assoc-in [:globals :eye] eye) (assoc-in [:globals :target] target)))

;; --- camera rig: EDN data → eye/target (pure, cross-platform) ----------------
;;   {:distance 64 :height 55 :azimuth 0.785 :look-height 0.0}
;; A rig is data: store it as datoms, fork it, animate :azimuth — the executor just
;; consumes the eye/target it produces.

(def default-rig
  {:distance 64.0 :height 55.0 :azimuth 0.785 :look-height 0.0 :follow-height 0.0})

(defn rig->camera
  "Given a camera-rig map and the follow point (world), return {:eye :target}.
   eye orbits the target at :distance/:azimuth, raised to :height; target sits at
   :look-height above the follow point.

   The follow point is `[x z]` (ground plane) or `[x y z]`. With `[x y z]`, `:follow-height`
   is the fraction of the followed altitude that the rig rises by — 0.0 (the default, and
   what every 2-element caller gets) pins the camera at a fixed height exactly as before,
   1.0 tracks the subject one-for-one.

   A rig that ignores altitude entirely is fine for a game played on the ground, and wrong
   for one where altitude IS the mechanic: with a fixed eye and a fixed look-at, climbing
   moves the subject a few pixels up a frame that never reacts, so the player has no way to
   read their own height or judge another object's. Partial follow (~0.6-0.8) is usually
   better than 1.0 — it keeps some parallax against the ground so the climb still *reads*
   as a climb rather than as the world sliding down."
  [rig follow]
  (let [{:keys [distance height azimuth look-height follow-height]} (merge default-rig rig)
        [px py pz] (if (<= 3 (count follow)) follow [(nth follow 0) 0.0 (nth follow 1)])
        dy (* (or follow-height 0.0) (or py 0.0))
        ;; a rig that isn't following altitude returns its heights untouched rather than
        ;; widened by a `(+ h 0.0)` — every existing caller keeps the exact value it had
        raise (fn [h] (if (zero? dy) h (+ h dy)))]
    {:eye    [(+ px (* distance #?(:clj (Math/cos azimuth) :cljs (js/Math.cos azimuth))))
              (raise height)
              (+ pz (* distance #?(:clj (Math/sin azimuth) :cljs (js/Math.sin azimuth))))]
     :target [px (raise look-height) pz]}))

(defn valid?
  "A cheap structural check — enough to catch obvious authoring mistakes."
  [ir]
  (and (map? ir)
       (map? (:globals ir))
       (sequential? (:instances ir))
       (every? (fn [i] (and (vector? (:pos i)) (vector? (:color i)) (vector? (:size i))))
               (:instances ir))))

;; --- vertex layout --------------------------------------------------------
;;
;; The executor's vertex layout used to be a literal `#js` structure inside
;; `kami.webgpu/vlayout`, which meant two things: no pipeline could declare its
;; own layout (every pipeline got the mesh+instance pair or, for `:fullscreen`,
;; nothing), and the instance buffer's byte stride was written as a bare `128`
;; next to an `INST-FLOATS 32` that separately implied it. Raising the float
;; count to add an instance attribute left the stride at 128, and nothing in the
;; repo compared them — the pipeline would read the wrong bytes per instance,
;; which shows up as geometry in the wrong place rather than as an error.
;;
;; Here the layout is data, the instance stride is *derived* from the float
;; count, and [[vertex-layout-problems]] is a pure checker the JVM can run.
;; `kami.webgpu` turns this into `#js` and refuses to build a pipeline whose
;; layout has problems.

(def vertex-formats
  "WebGPU vertex formats this executor accepts, mapped to their byte size.
   Deliberately not the full spec list: a format nobody packs is a typo, and
   accepting it would let a layout claim a stride the packer never fills."
  {"float32" 4 "float32x2" 8 "float32x3" 12 "float32x4" 16
   "uint32" 4 "uint32x2" 8 "uint32x3" 12 "uint32x4" 16
   "sint32" 4 "sint32x2" 8 "sint32x3" 12 "sint32x4" 16
   "float16x2" 4 "float16x4" 8
   "unorm8x2" 2 "unorm8x4" 4 "snorm8x2" 2 "snorm8x4" 4
   "uint8x2" 2 "uint8x4" 4 "sint8x2" 2 "sint8x4" 4})

(def instance-floats
  "Floats per instance written by `kami.webgpu/pack-instance!`. The instance
   buffer's stride is 4x this — the two must not be stated independently."
  32)

(def default-vertex-layout
  "The mesh + instance pair every non-`:fullscreen` pipeline gets unless it
   declares its own `:vertex-layout`. Shader locations are globally unique
   across both buffers, as WebGPU requires."
  [{:stride 72
    :step :vertex
    :attributes [{:format "float32x3" :offset 0 :location 0}    ;; position
                 {:format "float32x3" :offset 12 :location 1}   ;; normal
                 {:format "float32x2" :offset 24 :location 8}   ;; uv
                 {:format "float32x4" :offset 32 :location 9}   ;; tangent
                 {:format "float32x3" :offset 48 :location 11}  ;; skin weights
                 {:format "float32x3" :offset 60 :location 12}]} ;; layer indices
   {:stride (* 4 instance-floats)
    :step :instance
    :floats instance-floats
    :attributes [{:format "float32x4" :offset 0 :location 2}     ;; model matrix
                 {:format "float32x4" :offset 16 :location 3}
                 {:format "float32x4" :offset 32 :location 4}
                 {:format "float32x4" :offset 48 :location 5}
                 {:format "float32x4" :offset 64 :location 6}    ;; colour
                 {:format "float32x4" :offset 80 :location 7}    ;; material
                 {:format "float32x4" :offset 96 :location 10}   ;; uv transform
                 {:format "float32x4" :offset 112 :location 13}]}])

(defn vertex-layout-problems
  "Pure check of a `:vertex-layout` (a vector of buffer maps). Returns a vector
   of `{:reason … }` problems, or `nil` when the layout is usable.

   An empty layout is legal — that is what a `:fullscreen` pass wants. What is
   not legal is a layout that a device would reject or, worse, accept while
   reading bytes the packer never wrote:

     :vertex-layout/not-sequential      the layout is not a sequence of buffers
     :vertex-layout/bad-buffer          a buffer is not a map
     :vertex-layout/bad-stride          stride missing, <= 0, or not a multiple of 4
     :vertex-layout/bad-step            :step outside #{:vertex :instance}
     :vertex-layout/no-attributes       a buffer declares no attributes
     :vertex-layout/unknown-format      format outside [[vertex-formats]]
     :vertex-layout/bad-offset          offset missing, negative, or not a multiple of 4
     :vertex-layout/overflows-stride    offset + size > stride
     :vertex-layout/bad-location        location missing or negative
     :vertex-layout/duplicate-location  the same location in two places
     :vertex-layout/stride-floats-drift :floats declared but stride != 4x it"
  [layout]
  (if-not (sequential? layout)
    [{:reason :vertex-layout/not-sequential :layout layout}]
    (let [problems
          (into []
                (comp
                 (map-indexed vector)
                 (mapcat
                  (fn [[bi buf]]
                    (if-not (map? buf)
                      [{:reason :vertex-layout/bad-buffer :buffer bi :value buf}]
                      (let [{:keys [stride step attributes floats]} buf]
                        (concat
                         (when-not (and (number? stride) (pos? stride)
                                        (zero? (mod stride 4)))
                           [{:reason :vertex-layout/bad-stride :buffer bi :stride stride}])
                         (when (and (some? step) (not (#{:vertex :instance} step)))
                           [{:reason :vertex-layout/bad-step :buffer bi :step step}])
                         (when (and (some? floats)
                                    (number? stride)
                                    (not= stride (* 4 floats)))
                           [{:reason :vertex-layout/stride-floats-drift :buffer bi
                             :stride stride :floats floats :expected-stride (* 4 floats)}])
                         (when-not (seq attributes)
                           [{:reason :vertex-layout/no-attributes :buffer bi}])
                         (mapcat
                          (fn [{:keys [format offset location]}]
                            (let [size (get vertex-formats format)]
                              (concat
                               (when-not size
                                 [{:reason :vertex-layout/unknown-format :buffer bi
                                   :format format}])
                               (when-not (and (number? offset) (not (neg? offset))
                                              (zero? (mod offset 4)))
                                 [{:reason :vertex-layout/bad-offset :buffer bi
                                   :offset offset}])
                               (when (and size (number? offset) (number? stride)
                                          (> (+ offset size) stride))
                                 [{:reason :vertex-layout/overflows-stride :buffer bi
                                   :offset offset :size size :stride stride}])
                               (when-not (and (number? location) (not (neg? location)))
                                 [{:reason :vertex-layout/bad-location :buffer bi
                                   :location location}]))))
                          attributes)))))))
                layout)
          locations (for [buf layout
                          :when (map? buf)
                          a (:attributes buf)]
                      (:location a))
          dupes (->> locations
                     (filter number?)
                     frequencies
                     (keep (fn [[loc n]] (when (> n 1) loc)))
                     sort)]
      (seq (into problems
                 (map (fn [loc] {:reason :vertex-layout/duplicate-location
                                 :location loc}))
                 dupes)))))

(defn valid-vertex-layout?
  [layout]
  (nil? (vertex-layout-problems layout)))
