(ns kotoba.webgpu-rs.prefab
  "Data-level prefabs: a named, nestable, per-instance-overridable authoring
  unit that expands to plain render-IR instances
  ([[kotoba.webgpu-rs.render-ir/parse-instance]]-shaped maps).

  Unlike the rest of this namespace family, this has no kami-webgpu-rs Rust
  original — it is the EDN `prefab/spawn table` that kami-engine ADR-0040
  names as belonging on the data side of the boundary. It is a pure
  EDN-in/data-out transform: no wgpu calls, no network, no I/O, and no
  randomness (a scatter that *places* prefabs stays the caller's job, e.g.
  [[kotoba.webgpu-rs.scene]]).

  ## Why this exists

  Two reusable-unit mechanisms already existed and neither covers authoring:

    - `defentity` (kami-engine-guest `kotoba.engine-clj.ast`) is a *guest
      code* constructor compiled into WASM. ADR-0037 calls it \"the prefab
      DSL\", but it is code: you cannot instantiate it from a scene EDN, nest
      it, or override one field of one instance without recompiling.
    - `:render/props` in a `scene.edn` templates exactly two shapes
      (`:buildings`, `:trees`) with resolution semantics hardcoded in
      [[kotoba.webgpu-rs.scene]]. `:trees` already expands one template into
      *two* instances (trunk + canopy) — a two-part prefab, spelled in
      Clojure instead of data. `prefab-oracle-reproduces-scene-trees` in this
      namespace's test asserts that this expander reproduces that shipped
      output exactly, which is what makes the general form trustworthy.

  ## Shape

      {:prefab/defs
       {:tree  {:parts [{:name :trunk  :pos [0 0 0]     :size [0.33 1.3] ...}
                        {:name :canopy :pos [0 1.3 0]   :size [1.1 1.56] ...}]}
        :oak   {:variant-of :tree :overrides {:canopy {:color [0.2 0.4 0.2]}}}
        :grove {:parts [{:name :left  :prefab :tree :pos [-3 0 0]}
                        {:name :right :prefab :oak  :pos [3 0 0] :yaw 0.4}]}}
       :prefab/instances
       [{:prefab :grove :pos [10 0 -4] :yaw 1.57 :scale 2.0
         :overrides {[:left :canopy] {:color [1 0 0]}}}]}

  A *part* is either a **leaf** (any instance field: `:pos` `:size` `:color`
  `:yaw` `:metallic` `:roughness` `:emissive`) or a **nested reference**
  (`:prefab <def-id>`, plus its own local `:pos`/`:yaw`/`:scale` and
  `:overrides`). `:name` addresses it for overrides and must be unique among
  its siblings.

  ## Local transforms are translation + Y-yaw + uniform scale, only

  Not because that is elegant, but because a render-IR instance carries
  `:pos`/`:size`/`:yaw` and *not* a matrix — the executor derives the model
  matrix itself ([[kotoba.webgpu-rs.frame/model-mat]]). A prefab whose parts
  needed pitch/roll or non-uniform scale could not be expressed as instances
  at all, so this expander refuses to pretend otherwise. That is a real
  parity gap against Unity's full TRS prefab, not a simplification.

  Composition reuses [[kotoba.webgpu-rs.mat4]] rather than open-coding a
  rotation, so there is exactly one handedness convention in this repo.

  ## Overrides

  Addressed by part `:name`: a bare keyword for a direct child, a vector for
  a path through nesting (`[:left :canopy]`). An override is `merge`d over
  the part's own map (parts are flat maps of scalars and short vectors, so
  shallow merge is the whole story). Precedence, lowest to highest: the
  variant chain's `:overrides`, the parent part's `:overrides`, then the
  instance's `:overrides`.

  ## Budgets

  Expansion refuses rather than diverges: cycles through `:prefab`/
  `:variant-of` throw with the offending chain, and `:max-depth` (8) and
  `:max-instances` (100000) are checked while expanding, not after."
  (:require [kotoba.webgpu-rs.edn :as e]
            [kotoba.webgpu-rs.mat4 :as m]
            [kotoba.webgpu-rs.render-ir :as ir]))

(def default-limits
  "Refusal thresholds for [[expand]]. `:max-depth` counts nesting levels
  below an instance; `:max-instances` bounds the emitted leaf count."
  {:max-depth 8 :max-instances 100000})

(def identity-frame
  "World frame of a prefab instance before its own transform is applied."
  {:pos [0.0 0.0 0.0] :yaw 0.0 :scale 1.0})

;; --- overrides -------------------------------------------------------------

(defn- as-path
  "Override key -> path vector. A bare keyword addresses a direct child."
  [k]
  (if (vector? k) (vec k) [k]))

(defn normalize-overrides
  "`{:canopy {...} [:left :canopy] {...}}` -> `{[:canopy] {...} ...}`."
  [ov]
  (reduce-kv (fn [acc k v] (assoc acc (as-path k) v)) {} (or ov {})))

(defn- merge-override-maps
  "Combine already-normalized override maps, later winning per path."
  [& ovs]
  (apply merge-with merge (remove nil? ovs)))

(defn- own-override
  "The override addressed *at* `nm` (not below it)."
  [ov nm]
  (get ov [nm]))

(defn- overrides-below
  "Overrides addressed below `nm`, rebased so the child sees them as its own."
  [ov nm]
  (reduce-kv (fn [acc p v]
               (if (and (> (count p) 1) (= (first p) nm))
                 (assoc acc (subvec p 1) v)
                 acc))
             {}
             ov))

;; --- frames ----------------------------------------------------------------

(defn- local-frame
  "A part's or instance's own transform. `:scale` defaults to 1.0 (not 0.0 —
  `numf`'s missing-is-zero rule would collapse every child to a point)."
  [m]
  {:pos (e/vec3 (:pos m))
   :yaw (if (number? (:yaw m)) (double (:yaw m)) 0.0)
   :scale (if (number? (:scale m)) (double (:scale m)) 1.0)})

(defn compose
  "Child world frame from `parent` world frame and `child` local frame:
  the child's local position is scaled and Y-rotated into the parent, yaws
  add, scales multiply."
  [parent child]
  (let [mat (m/mul* (m/from-translation (:pos parent))
                    (m/from-rotation-y (:yaw parent))
                    (m/from-scale (let [s (:scale parent)] [s s s])))]
    {:pos (m/transform-point3 mat (:pos child))
     :yaw (+ (:yaw parent) (:yaw child))
     :scale (* (:scale parent) (:scale child))}))

(defn- emit-leaf
  "Leaf part + its world frame -> a render-IR instance. `:size` is scaled
  uniformly; defaults come from [[ir/parse-instance]] so a prefab leaf and a
  hand-written `:instances` entry cannot drift."
  [part frame]
  (let [base (ir/parse-instance part)
        s (:scale frame)
        [w h] (:size base)]
    (assoc base
           :pos (:pos frame)
           :yaw (+ (:yaw frame) (:yaw base))
           :size [(* w s) (* h s)])))

;; --- definitions -----------------------------------------------------------

(defn- def-chain
  "Resolve `id` through its `:variant-of` chain. Returns
  `[parts variant-overrides]`, the overrides normalized and ordered so a
  variant's own overrides win over the base's. Throws on an unknown id or a
  cycle."
  [defs id]
  (loop [id id seen [] parts nil ovs []]
    (when (some #{id} seen)
      (throw (ex-info "prefab variant cycle"
                      {:reason :prefab/variant-cycle :chain (conj seen id)})))
    (let [d (get defs id)]
      (when-not (map? d)
        (throw (ex-info "unknown prefab def"
                        {:reason :prefab/unknown-def :id id
                         :known (vec (sort-by str (keys defs)))})))
      (let [seen (conj seen id)
            ovs (conj ovs (normalize-overrides (:overrides d)))]
        (if-let [base (:variant-of d)]
          (recur base seen parts ovs)
          ;; base reached: its parts are the shape; overrides apply
          ;; base-first so the most-derived variant wins.
          [(vec (:parts d)) (apply merge-override-maps (reverse ovs))])))))

;; --- expansion -------------------------------------------------------------

(defn- expand-parts
  [defs parts frame ov chain depth limits out]
  (reduce
   (fn [acc part0]
     (let [nm (:name part0)
           part (if-let [o (own-override ov nm)] (merge part0 o) part0)
           child-frame (compose frame (local-frame part))]
       (if-let [child-id (:prefab part)]
         (do
           (when (>= depth (:max-depth limits))
             (throw (ex-info "prefab nesting too deep"
                             {:reason :prefab/max-depth
                              :max-depth (:max-depth limits)
                              :chain (conj chain child-id)})))
           (when (some #{child-id} chain)
             (throw (ex-info "prefab nesting cycle"
                             {:reason :prefab/nesting-cycle
                              :chain (conj chain child-id)})))
           (let [[cparts cov] (def-chain defs child-id)
                 sub (merge-override-maps cov
                                          (normalize-overrides (:overrides part))
                                          (overrides-below ov nm))]
             (expand-parts defs cparts child-frame sub
                           (conj chain child-id) (inc depth) limits acc)))
         (let [acc (conj! acc (emit-leaf part child-frame))]
           (when (> (count acc) (:max-instances limits))
             (throw (ex-info "prefab instance budget exceeded"
                             {:reason :prefab/max-instances
                              :max-instances (:max-instances limits)})))
           acc))))
   out
   parts))

(defn expand
  "`{:prefab/defs {...} :prefab/instances [...]}` -> vector of render-IR
  instances, in instance order and, within an instance, in part order.
  `limits` overrides [[default-limits]].

  Refuses (throws `ex-info` carrying `:reason`) on an unknown def, a variant
  or nesting cycle, or a depth/count budget breach — a malformed prefab table
  must not silently render as an empty or truncated scene."
  ([root] (expand root nil))
  ([root limits]
   (let [defs (or (:prefab/defs root) {})
         limits (merge default-limits limits)]
     (persistent!
      (reduce
       (fn [acc inst]
         (let [id (:prefab inst)
               [parts cov] (def-chain defs id)
               ov (merge-override-maps cov (normalize-overrides (:overrides inst)))]
           (expand-parts defs parts
                         (compose identity-frame (local-frame inst))
                         ov [id] 0 limits acc)))
       (transient [])
       (:prefab/instances root))))))
