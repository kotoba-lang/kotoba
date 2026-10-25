(ns game.trigger
  "Trigger system: portal traversal + item pickup via sensor collisions.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/trigger.rs`.

  Cross-cluster note: the original Rust depends on `crate::physics::
  {PhysicsCollider, TriggerKind, TriggerZone}` (physics.rs is not part of
  this cluster) plus `hecs::World` and `rapier3d::ColliderHandle`. This
  namespace has zero hard deps, so:
  - `ColliderHandle` is duck-typed as an opaque value (any equality-
    comparable value works, e.g. an integer id or keyword).
  - `TriggerKind` is a local keyword enum mirroring physics.rs's shape:
    `:portal` / `:item-pickup` / `:damage-zone`.
  - `hecs::World`'s ECS query is replaced by a plain seq of trigger-zone
    maps `{:collider-handle :kind :data}` passed in directly by the
    caller (the final assembly pass may replace this with a real ECS
    query once physics.rs/scene.rs land in another cluster).")

(def trigger-kinds
  "Local mirror of physics.rs's `TriggerKind` enum."
  #{:portal :item-pickup :damage-zone})

(defn- trigger-event-portal [entity-collider island-id]
  {:type :portal :entity-collider entity-collider :island-id island-id})

(defn- trigger-event-item-pickup [entity-collider item-id]
  {:type :item-pickup :entity-collider entity-collider :item-id item-id})

(defn- trigger-event-damage [entity-collider amount]
  {:type :damage :entity-collider entity-collider :amount amount})

(defn- parse-damage-amount [data]
  (try
    #?(:clj (Long/parseLong data) :cljs (js/parseInt data 10))
    (catch #?(:clj Exception :cljs :default) _ 10)))

(defn process-triggers
  "Process sensor intersections and emit trigger events.

  `trigger-zones` is a seq of `{:collider-handle :kind :data}` maps
  (duck-typed stand-in for a `hecs::World` query over `TriggerZone`
  components). `intersection-pairs` is a seq of `[collider-a collider-b]`
  pairs. Returns a vector of TriggerEvent maps."
  [trigger-zones intersection-pairs]
  (vec
   (for [[c1 c2] intersection-pairs
         {:keys [collider-handle kind data]} trigger-zones
         :let [entity-collider (cond
                                  (= c1 collider-handle) c2
                                  (= c2 collider-handle) c1
                                  :else ::no-match)]
         :when (not= entity-collider ::no-match)]
     (case kind
       :portal (trigger-event-portal entity-collider data)
       :item-pickup (trigger-event-item-pickup entity-collider data)
       :damage-zone (trigger-event-damage entity-collider (parse-damage-amount data))))))
