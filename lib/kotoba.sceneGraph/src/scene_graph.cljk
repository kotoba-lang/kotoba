(ns scene-graph
  "KAMI Scene Graph — parent/child transform hierarchy with top-down world-transform
  propagation.

  Restored from the legacy `kami-scene-graph` Rust crate
  (kotoba-lang/kami-engine, `kami-scene-graph/src/lib.rs`, deleted in PR #82
  \"Remove Rust workspace from kami-engine\") as zero-dependency portable `.cljc`,
  per the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Purpose: maintain a scene DAG of entities, each with an optional local transform
  (position/rotation/scale), parent, and children, and propagate world transforms
  down the tree by composing each entity's local transform matrix with its parent's
  already-computed world matrix (root entities compose against the identity matrix).

  Adaptation note: the original Rust implementation stored entities/components in a
  `hecs::World` ECS (hecs `Entity` handles, `world.query`/`world.get`/`world.insert_one`
  etc). hecs is an ECS storage library with no meaningful CLJC equivalent (raw entity
  allocator/generational-index internals), so it has been dropped entirely. Entities
  are plain CLJC values (keywords, integers, strings — anything usable as a map key)
  and the \"world\" is a plain CLJC map from entity id to an entity map
  `{:local-transform {...}, :world-transform mat4, :parent id, :children [ids], :root? bool}`.
  This preserves the scene-hierarchy + transform-propagation *behavior* exactly while
  discarding ECS-storage-specific plumbing.

  Transform convention: position/scale are 3-vectors `[x y z]`, rotation is a
  quaternion `[x y z w]` (matches glam's `Quat` component order), and matrices are
  16-element column-major vectors (matches glam's `Mat4::to_cols_array`), i.e.
  `[m00 m10 m20 m30  m01 m11 m21 m31  m02 m12 m22 m32  m03 m13 m23 m33]` where
  the translation column is at indices 12/13/14.")

;; ---------------------------------------------------------------------------
;; Local transform (position/rotation/scale) — was `struct LocalTransform`.
;; ---------------------------------------------------------------------------

(def identity-quat
  "Identity rotation quaternion `[x y z w]` — was `Quat::IDENTITY`."
  [0.0 0.0 0.0 1.0])

(def zero-vec3
  "`[0.0 0.0 0.0]` — was `Vec3::ZERO`."
  [0.0 0.0 0.0])

(def one-vec3
  "`[1.0 1.0 1.0]` — was `Vec3::ONE`."
  [1.0 1.0 1.0])

(def identity-mat4
  "16-element column-major identity matrix — was `Mat4::IDENTITY`."
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn default-local-transform
  "Default local transform: zero position, identity rotation, unit scale.
  Was `impl Default for LocalTransform`."
  []
  {:position zero-vec3
   :rotation identity-quat
   :scale one-vec3})

(defn local-transform->matrix
  "Compose a `{:position :rotation :scale}` local transform into a 16-element
  column-major Mat4. Was `LocalTransform::matrix` /
  `Mat4::from_scale_rotation_translation`."
  [{:keys [position rotation scale]}]
  (let [[px py pz] position
        [x y z w] rotation
        [sx sy sz] scale
        r00 (- 1.0 (* 2.0 (+ (* y y) (* z z))))
        r01 (* 2.0 (- (* x y) (* w z)))
        r02 (* 2.0 (+ (* x z) (* w y)))
        r10 (* 2.0 (+ (* x y) (* w z)))
        r11 (- 1.0 (* 2.0 (+ (* x x) (* z z))))
        r12 (* 2.0 (- (* y z) (* w x)))
        r20 (* 2.0 (- (* x z) (* w y)))
        r21 (* 2.0 (+ (* y z) (* w x)))
        r22 (- 1.0 (* 2.0 (+ (* x x) (* y y))))]
    [(* r00 sx) (* r10 sx) (* r20 sx) 0.0
     (* r01 sy) (* r11 sy) (* r21 sy) 0.0
     (* r02 sz) (* r12 sz) (* r22 sz) 0.0
     px py pz 1.0]))

;; ---------------------------------------------------------------------------
;; Mat4 helpers — enough of glam's Mat4 surface to support propagation.
;; ---------------------------------------------------------------------------

(defn mat4-mul
  "Multiply two 16-element column-major Mat4s: `a * b` (b applied first, matching
  glam's `Mat4 * Mat4` semantics used by `parent_world * local`)."
  [a b]
  (vec (for [col (range 4)
             row (range 4)]
         (reduce + (for [k (range 4)]
                     (* (nth a (+ (* k 4) row))
                        (nth b (+ (* col 4) k))))))))

(defn mat4-translation
  "Extract the `[x y z]` translation column (indices 12/13/14) from a Mat4."
  [m]
  [(nth m 12) (nth m 13) (nth m 14)])

;; ---------------------------------------------------------------------------
;; Scene graph — a world is a plain map: entity-id -> entity-map.
;; Entity-map keys: :local-transform, :world-transform, :parent, :children, :root?
;; Was: `Parent`, `Children`, `Root`, `WorldTransform` hecs components.
;; ---------------------------------------------------------------------------

(defn- roots
  "Entities with `:root? true` and a `:local-transform` — was the
  `world.query::<(&Root, &LocalTransform)>()` scan in `propagate_transforms`."
  [world]
  (for [[id entity] world
        :when (and (:root? entity) (:local-transform entity))]
    id))

(defn- propagate-recursive
  "Compute `entity`'s world transform from `parent-world`, store it, then recurse
  into its children with the freshly computed world matrix. Was
  `fn propagate_recursive`."
  [world entity parent-world]
  (let [local (get-in world [entity :local-transform])
        world-mat (if local
                    (mat4-mul parent-world (local-transform->matrix local))
                    parent-world)
        world' (assoc-in world [entity :world-transform] world-mat)
        children (get-in world' [entity :children] [])]
    (reduce (fn [w child] (propagate-recursive w child world-mat))
            world'
            children)))

(defn propagate-transforms
  "Propagate transforms down the scene graph: for every root entity (has `:root?`
  and `:local-transform`), walk its subtree top-down composing each child's local
  matrix with its parent's already-computed world matrix, writing `:world-transform`
  on every visited entity. Was `fn propagate_transforms`. Call once per \"frame\"
  after updating `:local-transform`s. Returns the updated world."
  [world]
  (reduce (fn [w root] (propagate-recursive w root identity-mat4))
          world
          (roots world)))

(defn attach
  "Attach `child` to `parent`: set `child`'s `:parent` and append `child` to
  `parent`'s `:children`. Was `fn attach`. Returns the updated world."
  [world parent child]
  (-> world
      (assoc-in [child :parent] parent)
      (update-in [parent :children] (fnil conj []) child)))

(defn detach
  "Detach `child` from its current parent (if any): remove it from the parent's
  `:children` and clear `child`'s `:parent`. Was `fn detach`. Returns the updated
  world."
  [world child]
  (let [parent (get-in world [child :parent])]
    (cond-> world
      (some? parent) (update-in [parent :children]
                                 (fn [children] (vec (remove #(= % child) children))))
      true (update child dissoc :parent))))
