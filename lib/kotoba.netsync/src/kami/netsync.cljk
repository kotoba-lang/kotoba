(ns kami.netsync
  "hiccup for replication — what crosses the wire, described as EDN. A schema names the
   synced components, their fields, authority, and interpolation. The wire payload is
   derived from the schema, not hand-coded; store the schema as datoms, fork it, retune
   bandwidth without touching transport code.

     {:components {:transform {:fields [:x :y :z] :authority :server :interp :lerp}
                   :health    {:fields [:hp]      :authority :server :interp :snap}}}

   Pure + cross-platform (.cljc): `snapshot` extracts the wire payload; `apply-snapshot`
   merges a received one; `interp` blends toward a target per each component's :interp.
   The same EDN drives any transport (WebRTC/WebSocket here-or-later).

   Genre lag compensation lives in sibling namespaces, required only by the
   games that need them:

   - `kami.netsync.fps` — hitscan rewind (the shot; movement stays here)
   - `kami.netsync.fighting` — rollback / delay-based lockstep")

(def default-schema
  {:components {:transform {:fields [:x :y :z]  :authority :server :interp :lerp}
                :facing    {:fields [:rx :ry]   :authority :server :interp :lerp}
                :health    {:fields [:hp]       :authority :server :interp :snap}}
   ;; Client-side prediction (Co-Scientist iter-02 predicted-thirdperson-squad). `:predict`
   ;; names the components the local player predicts ahead of the server; `:prediction` tunes
   ;; the rollback buffer and the snap threshold. Pure feel-as-data — fork to retune.
   :predict #{:transform}
   :prediction {:buffer 64 :snap-threshold 0.5}})

(def fps-schema
  "PALISADE / nightglass-strike. Shooter predicts transform+facing; HP snaps
   from the authority; `:fps` is the rewind policy `kami.netsync.fps` consumes."
  {:components {:transform {:fields [:x :y :z] :authority :server :interp :lerp}
                :facing    {:fields [:rx :ry]  :authority :server :interp :lerp}
                :health    {:fields [:hp]      :authority :server :interp :snap}}
   :predict #{:transform :facing}
   :prediction {:buffer 64 :snap-threshold 0.5}
   :genre :fps
   :fps {:history 128 :max-rewind 20 :hit-radius 0.55 :origin-slop 2.0}})

(def fighting-schema
  "Network 2P fighting. Authority is the deterministic sim every peer runs,
   not a damage-deciding client. Rollback window is the rewrite horizon."
  {:components {:transform {:fields [:x :y] :authority :sim :interp :snap}
                :health    {:fields [:hp]   :authority :sim :interp :snap}
                :fsm       {:fields [:st]   :authority :sim :interp :snap}}
   :predict #{}
   :genre :fighting
   :fighting {:mode :rollback :players #{:p1 :p2}
              :rollback-window 8 :save-cap 16
              :empty-input {:dx 0 :attack false}}})

(defn synced-fields
  "All fields the schema replicates, across components."
  [schema]
  (vec (mapcat (comp :fields val) (:components schema))))

(defn snapshot
  "The wire payload for an entity: only the schema's synced fields."
  [schema entity]
  (select-keys entity (synced-fields schema)))

(defn apply-snapshot
  "Merge a received snapshot into an entity (schema fields only)."
  [schema entity snap]
  (merge entity (select-keys snap (synced-fields schema))))

(defn interp
  "Blend an entity toward `target` by t∈[0,1] using each component's :interp — :lerp
   numerically tweens fields, anything else snaps. Pure."
  [schema entity target t]
  (reduce-kv
    (fn [e _ {:keys [fields interp]}]
      (reduce (fn [e f]
                (let [a (get e f) b (get target f)]
                  (cond
                    (not (contains? target f)) e
                    (and (= interp :lerp) (number? a) (number? b)) (assoc e f (+ a (* (- b a) t)))
                    :else (assoc e f b))))
              e fields))
    entity (:components schema)))

;; ── client-side prediction + remote interpolation (pure, cross-platform) ──

(defn- sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))

(defn- dist
  "Euclidean distance between two entities over a field set (missing field = 0)."
  [fields a b]
  (sqrt (reduce (fn [s f] (let [d (- (get a f 0) (get b f 0))] (+ s (* d d)))) 0 fields)))

(defn pred-record
  "Append a local input to the pending (unconfirmed) buffer, trimmed to the schema's
   :prediction :buffer length. Pure — `pending` is a vector you thread each frame."
  [schema pending input]
  (let [cap (get-in schema [:prediction :buffer] 64)]
    (vec (take-last cap (conj (vec pending) input)))))

(defn pred-reconcile
  "Client reconciliation against an authoritative snapshot (ported from prediction.rs).
   `local` is the client-predicted entity; `authoritative` is the server-confirmed snapshot;
   `pending` are the inputs not yet acked; `step` is a pure (entity input) -> entity.

   Replays `pending` from the authoritative base. If that reconciled position differs from the
   local prediction by more than the schema's :snap-threshold, SNAP to it (a visible
   correction); otherwise the prediction was right — keep `local` (no rubber-banding). Pure."
  [schema local authoritative pending step]
  (let [threshold (get-in schema [:prediction :snap-threshold] 0.5)
        fields    (get-in schema [:components :transform :fields] [:x :y :z])
        base      (apply-snapshot schema local authoritative)
        replayed  (reduce step base pending)]
    (if (> (dist fields local replayed) threshold)
      replayed
      local)))

(defn remote-interp
  "Interpolate a REMOTE entity between two buffered snapshots by `alpha`∈[0,1] — `prev` at 0,
   `next` at 1. Smooths other players' motion between sparse server updates. Pure."
  [schema prev next alpha]
  (interp schema prev next alpha))
