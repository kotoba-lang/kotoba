(ns kotoba.shibuya
  "Shibuya street digital-twin scene model — pure data/config, no I/O.

  Ported from `kami-app-shibuya` (Rust, `kotoba-lang/kami-engine`) per
  ADR-2607010000. That crate loaded a real OSM-baked city block, ran a
  kami-genesis full-physics multi-agent sim on it and rendered the result
  with wgpu. This library keeps only the parts that are pure data/config
  math with no engine/GPU/wasm dependency:

  - the `Scene` model (buildings, roads, point objects) and its pure
    derived geometry (`scene-center`, `building-obstacles`, `spawn-points`);
  - `agent-urdf`, the pure string-template function that builds a 4-DOF
    floating-base URDF for an agent body (this only generates config data —
    it does not execute physics);
  - the `object-footprint` / `object-color` lookup tables and colour
    constants used by the renderer;
  - `agent-spawn-config`, deriving the per-agent spawn configuration
    (size/mass/color/drive/steer-phase) that the original `Agent::new` +
    `Agent::place` set up *before* physics stepping started.

  Explicitly NOT ported (see README): wgpu render mesh accumulation, the
  wasm_bindgen entry points, the Gaussian-splat overlay, and the actual
  physics stepping (`Agent::step`/`body_world`, `ContactWorld`,
  `Articulation3dConfig`) — no kotoba port of the kami-genesis rigid-body
  contact solver exists yet, so agents stop at \"spawn configuration\", not
  simulation.

  No network, no I/O: callers read/parse EDN scene data (e.g. from
  `resources/kotoba/shibuya/*.edn`) and hand it to `parse-scene`. Portable
  `.cljc` across JVM / ClojureScript / SCI / GraalVM.")

;; ---------------------------------------------------------------------------
;; Colours (renderer palette — pure data, no GPU)
;; ---------------------------------------------------------------------------

(def asphalt [0.16 0.16 0.18])
(def road-color [0.30 0.30 0.33])
(def concrete [0.58 0.57 0.55])
(def glass [0.42 0.52 0.60])

(def agent-colors
  [[0.93 0.35 0.25]
   [0.20 0.62 0.86]
   [0.96 0.72 0.18]
   [0.30 0.72 0.55]
   [0.74 0.40 0.85]
   [0.90 0.50 0.70]])

;; ---------------------------------------------------------------------------
;; Timestep
;; ---------------------------------------------------------------------------

(def dt (/ 1.0 120.0))

;; ---------------------------------------------------------------------------
;; Point-asset lookup tables (kind -> render footprint / colour)
;; ---------------------------------------------------------------------------

(def ^:private footprint-table
  {"tree"             [4.0 4.0]
   "bench"            [1.6 0.5]
   "vending_machine"  [1.2 0.8]
   "telephone"        [0.9 0.9]
   "fire_hydrant"     [0.6 0.6]
   "waste_basket"     [0.7 0.7]
   "advertising"      [1.2 0.3]})

(def ^:private default-footprint [0.5 0.5]) ; poles: lamp / utility / signal

(defn object-footprint
  "Render footprint `[width depth]` in metres for a point-asset `kind`."
  [kind]
  (get footprint-table kind default-footprint))

(def ^:private color-table
  {"tree"             [0.20 0.58 0.24]
   "traffic_signals"  [0.96 0.74 0.10]
   "street_lamp"      [0.78 0.78 0.82]
   "utility_pole"     [0.52 0.46 0.40]
   "fire_hydrant"     [0.86 0.16 0.13]
   "bench"            [0.60 0.45 0.30]
   "vending_machine"  [0.22 0.52 0.82]
   "telephone"        [0.12 0.60 0.42]
   "advertising"      [0.90 0.30 0.55]})

(def ^:private default-color [0.70 0.70 0.72])

(defn object-color
  "Render colour `[r g b]` for a point-asset `kind`."
  [kind]
  (get color-table kind default-color))

;; ---------------------------------------------------------------------------
;; Scene model — parse + validate
;; ---------------------------------------------------------------------------

(def provenance-values #{"osm" "synthesized-demo"})

(defn- parse-object-attrs
  [{:keys [install-year company cost-jpy provenance]}]
  {:attrs/install-year install-year
   :attrs/company       company
   :attrs/cost-jpy      cost-jpy
   :attrs/provenance    provenance})

(defn- parse-city-object
  [{:keys [id kind pos h attrs]}]
  {:object/id    id
   :object/kind  kind
   :object/pos   pos
   :object/h     h
   :object/attrs (parse-object-attrs attrs)})

(defn- parse-building
  [{:keys [aabb height]}]
  {:building/aabb   aabb
   :building/height height})

(defn- parse-road
  [{:keys [path width]}]
  {:road/path  path
   :road/width width})

(defn parse-scene
  "Normalize a raw EDN scene map (as read from `resources/kotoba/shibuya/*.edn`
  by the caller — this function performs no I/O) into the internal `:scene/*`
  representation. Field names mirror the original Rust `Scene`/`Building`/
  `Road`/`CityObject`/`ObjectAttrs` structs (camelCase JSON -> kebab-case
  EDN)."
  [{:keys [name bbox-m buildings roads objects]}]
  {:scene/name      name
   :scene/bbox-m    bbox-m
   :scene/buildings (mapv parse-building buildings)
   :scene/roads     (mapv parse-road roads)
   :scene/objects   (mapv parse-city-object (or objects []))})

(defn valid-scene?
  "True if `scene` (already `parse-scene`d) has the minimal shape a
  downstream consumer needs: a 4-element bbox, and every building/road/object
  well-formed."
  [scene]
  (and (map? scene)
       (= 4 (count (:scene/bbox-m scene)))
       (every? #(= 4 (count (:building/aabb %))) (:scene/buildings scene))
       (every? #(>= (count (:road/path %)) 0) (:scene/roads scene))
       (every? (fn [o]
                 (and (seq (:object/id o))
                      (seq (:object/kind o))
                      (contains? provenance-values (:attrs/provenance (:object/attrs o)))))
               (:scene/objects scene))))

;; ---------------------------------------------------------------------------
;; Pure derived geometry
;; ---------------------------------------------------------------------------

(defn scene-center
  "Centre point `[x y z]` of the scene bbox (z = 0)."
  [scene]
  (let [[min-x min-y max-x max-y] (:scene/bbox-m scene)]
    [(* 0.5 (+ min-x max-x)) (* 0.5 (+ min-y max-y)) 0.0]))

(defn building-obstacles
  "Building footprints -> static AABB collision-volume bounds
  `{:min [x y 0] :max [x y height]}` (data only — no physics `Obstacle`
  type; a physics adapter can materialize its own from this)."
  [scene]
  (mapv (fn [{:keys [building/aabb building/height]}]
          (let [[min-x min-y max-x max-y] aabb]
            {:min [min-x min-y 0.0]
             :max [max-x max-y height]}))
        (:scene/buildings scene)))

(defn spawn-points
  "Up to `n` agent spawn points `{:pos [x y z] :yaw radians}` sampled along
  the road network, mirroring the original's stride-7 sampling: it walks
  roads at index `(i * 7) mod (count roads)`, taking the midpoint of each
  road's path and orienting toward the previous point, until `n` points are
  collected or every road has been visited once."
  [scene n]
  (let [roads (:scene/roads scene)
        cnt   (count roads)]
    (loop [i 0 out []]
      (if (or (>= (count out) n) (>= i cnt))
        out
        (let [r    (nth roads (mod (* i 7) (max cnt 1)))
              path (:road/path r)]
          (if (>= (count path) 2)
            (let [mid (quot (count path) 2)
                  p   (nth path mid)
                  q   (nth path (dec mid))
                  yaw (Math/atan2 (- (p 1) (q 1)) (- (p 0) (q 0)))]
              (recur (inc i) (conj out {:pos [(p 0) (p 1) 3.0] :yaw yaw})))
            (recur (inc i) out)))))))

;; ---------------------------------------------------------------------------
;; Agent spawn config (pre-physics setup only — see ns docstring)
;; ---------------------------------------------------------------------------

(def default-agent-size [4.2 1.9 1.6])
(def default-agent-mass 1100.0)
(def drive-accel 2.2) ; m/s^2, matches Agent::new's `mass * 2.2` forward force

(defn agent-spawn-config
  "Given a `{:pos :yaw}` spawn point (as returned by `spawn-points`) and its
  index `k` among spawned agents, derive the configuration
  `Agent::new`/`Agent::place` set up before any physics stepping: size,
  mass, colour (cycled through `agent-colors`), forward drive force, and
  steer-phase offset. Does not construct or step an articulation/contact
  world."
  ([spawn-point k] (agent-spawn-config spawn-point k default-agent-size default-agent-mass))
  ([{:keys [pos yaw]} k size mass]
   {:pos         pos
    :yaw         yaw
    :size        size
    :mass        mass
    :color       (nth agent-colors (mod k (count agent-colors)))
    :drive       (* mass drive-accel)
    :steer-phase (* k 1.3)}))

;; ---------------------------------------------------------------------------
;; Agent URDF generation (pure string template — no physics execution)
;; ---------------------------------------------------------------------------

(defn- prismatic-joint-xml
  [joint-name parent child axis]
  (str "<joint name=\"" joint-name "\" type=\"prismatic\">"
       "<parent link=\"" parent "\"/><child link=\"" child "\"/>"
       "<origin xyz=\"0 0 0\"/><axis xyz=\"" axis "\"/>"
       "<limit lower=\"-100000\" upper=\"100000\" effort=\"100000000\" velocity=\"1000\"/>"
       "</joint>\n"
       "<link name=\"" child "\"><inertial><mass value=\"0.0001\"/>"
       "<inertia ixx=\"1e-7\" iyy=\"1e-7\" izz=\"1e-7\" ixy=\"0\" ixz=\"0\" iyz=\"0\"/>"
       "</inertial></link>"))

(defn agent-urdf
  "Box-inertia URDF XML string for a 4-DOF floating-base agent: world -> px
  -> py -> pz -> (yaw) body. Intermediate links are ~massless; the body link
  carries `mass` + box inertia derived from `size` (`[length width height]`).
  This generates *config data* consumed by a URDF/articulation parser — it
  does not execute physics."
  [[l w h] mass]
  (let [ixx (/ (* mass (+ (* w w) (* h h))) 12.0)
        iyy (/ (* mass (+ (* l l) (* h h))) 12.0)
        izz (/ (* mass (+ (* l l) (* w w))) 12.0)
        jx  (prismatic-joint-xml "jx" "world" "lx" "1 0 0")
        jy  (prismatic-joint-xml "jy" "lx" "ly" "0 1 0")
        jz  (prismatic-joint-xml "jz" "ly" "lz" "0 0 1")]
    (str "<robot name=\"agent\">\n"
         "<link name=\"world\"/>\n"
         jx "\n" jy "\n" jz "\n"
         "<joint name=\"jyaw\" type=\"continuous\"><parent link=\"lz\"/><child link=\"body\"/>"
         "<origin xyz=\"0 0 0\"/><axis xyz=\"0 0 1\"/><dynamics damping=\"0\"/></joint>\n"
         "<link name=\"body\"><inertial><origin xyz=\"0 0 0\"/><mass value=\"" mass "\"/>"
         "<inertia ixx=\"" ixx "\" iyy=\"" iyy "\" izz=\"" izz
         "\" ixy=\"0\" ixz=\"0\" iyz=\"0\"/></inertial></link>\n"
         "</robot>")))
