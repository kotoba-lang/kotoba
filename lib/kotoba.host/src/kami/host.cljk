(ns kami.host
  "Browser host for compiled kami games (the CLJS twin of native kami-script-runtime).

   A game `logic.clj` is compiled to wasm by kototama, then WebAssembly.instantiate'd
   against this import object; its `kami:engine/*` calls read/write a small ECS, and
   its `*-tick` exports run each frame. This is what makes 'edit CLJ → live game' work.

   The ECS is a plain atom of {id → entity} (verified ABI-correct off-GPU in node +
   in-browser). A DataScript/Datomic query+as-of projection is the next layer (it was
   tried in the hot path first but caused subtle read bugs — kept out of the per-call
   path for now). ABI: imports are typed (i32 ptr/len, i64 eid, f32 coords); wasm i64
   crosses to JS as BigInt — eids are BigInt on the wire, keyed by Number here."
  (:require [kotoba.lang.text :as str]
            ;; SSoT: kotoba-lang/physics (ADR-2607102200 addendum 7), via its
            ;; `kotoba.physics` facade (kami.physics is the underlying SSoT impl ns in
            ;; that repo; going through the facade here mirrors kami.host's own
            ;; kami.host/kotoba.host facade convention).
            [kotoba.physics :as phys]
            ;; Shared realtime/CAE physics contract + physics-2d's realtime rigid-body
            ;; backend (kami-engine physics-2d integration): rigid-body-2d entities are
            ;; advanced through `kotoba.physics.contract/step`, not a bespoke ad-hoc
            ;; physics loop — mirroring the existing `:platformer` ad-hoc gravity path
            ;; but going through the portable contract instead. Both requires are
            ;; portable .cljc (no JS-only forms), so `step-rigid-bodies!` below works
            ;; identically on :clj and :cljs — only `tick!`'s wasm-driving wrapper is
            ;; :cljs-only.
            [kotoba.physics.contract :as physics-contract]
            [physics-2d.backend :as physics2d-backend]))

(defn new-state []
  (atom {:ents {} :next 1 :tick 0 :rng 0x2545F491
         ;; :pointer is the live pointer in 0..1 surface coordinates (kami.input's
         ;; `:on-pointer`), read by the kami:engine/input `pointer-x`/`pointer-y`
         ;; host imports. It stays {:x 0.0 :y 0.0} until a host wires a pointer,
         ;; which is exactly what those two imports returned unconditionally before.
         :keys #{} :axes {} :pointer {:x 0.0 :y 0.0}
         :mem nil :cursors {} :next-cur 1}))

;; ---------------------------------------------------------------------------
;; Rigid-body-2d ECS system — physics-2d wired through kotoba.physics.contract
;; ---------------------------------------------------------------------------
;;
;; A game attaches a rigid-body component to an entity with `attach-rigid-body!`
;; (or, for a whole scene at once, the host app can `swap!` `:rigid-body-2d`
;; directly, mirroring how `:platformer` is set from scene EDN in
;; network-isekai's `isekai.game`). `step-rigid-bodies!` then runs once per
;; `tick!` frame: it projects the tagged entities into the shared contract's
;; 2D scene envelope, steps them through `physics-2d.backend/backend`
;; (realtime fidelity — AABB/circle colliders, impulse resolution + positional
;; correction), and writes the resulting positions/velocities back onto the
;; ECS. Entities with no rigid-body component are untouched and keep using
;; the existing ad-hoc `:platformer` gravity or plain velocity integration.

(defn attach-rigid-body!
  "Attaches a `:physics/body` rigid-body component to entity ID — an EDN map
  shaped for `kotoba.physics.contract` / `physics-2d.backend`, e.g.
  `{:mass 1.0 :restitution 0.3 :friction 0.0 :collider
  (physics-2d's make-circle-collider r) :trigger? false}`. From the next
  `tick!` onward the entity is advanced by `step-rigid-bodies!` (real impulse
  physics) instead of the ad-hoc per-tag gravity/platformer path. Call after
  `spawn-entity!`/`:spawn`; a body config for an id with no live entity is
  harmless (`step-rigid-bodies!` just skips ids not present in `:ents`)."
  [state id body-cfg]
  (swap! state update-in [:rigid-body-2d :bodies] assoc id body-cfg))

(defn detach-rigid-body!
  "Removes entity ID's rigid-body component; it falls back to whatever
  ad-hoc physics (`:platformer` tags, or plain velocity integration) `tick!`
  already applies to untagged entities."
  [state id]
  (swap! state update-in [:rigid-body-2d :bodies] dissoc id))

(defn set-rigid-body-gravity!
  "Sets the `[gx gy]` gravity applied to rigid-body-2d entities (default
  `[0.0 -9.81]` when unset) — independent of the ad-hoc `:platformer`
  gravity, since the two systems own disjoint sets of entities."
  [state gravity-xy]
  (swap! state assoc-in [:rigid-body-2d :gravity] gravity-xy))

(defn rigid-body-ids
  "The set of entity ids currently carrying a rigid-body-2d component —
  `tick!` uses this to keep the ad-hoc gravity/platformer/plain-integration
  pass from double-driving them."
  [state]
  (set (keys (:bodies (:rigid-body-2d @state)))))

(defn apply-impulse!
  "Applies an external impulse `[ix iy]` to entity `id`'s velocity via the
  standard impulse-momentum relation (Δv = J / m — the same relation
  `step-rigid-bodies!`'s underlying `physics-2d.backend` already applies
  internally for collision response; this is an *external* impulse source
  instead, i.e. gameplay code saying \"give this a shove\", not a new
  collision path). Portable (no `#js`/cljs-only forms) so it's callable
  identically from the WASM guest ABI's `kami:engine/physics@1.0.0
  apply-impulse` host-import (`import-object`, below — the ABI's third f32,
  iz, is dropped before it reaches here: physics-2d is XY-plane only, ADR-
  2607122400) and directly from a JVM test.

  Only entities carrying a `:physics/body` rigid-body-2d component (via
  `attach-rigid-body!`) have a mass to convert an impulse into a velocity
  change, so this is a silent no-op — mirroring `:set-position`/
  `:set-velocity`'s existing guard-and-skip convention for a missing entity,
  rather than throwing and aborting the guest's whole tick — for any id with
  no rigid-body component, any despawned/unknown id, and a static body
  (`:mass 0`, which by `physics-2d`'s own convention never integrates;
  guarding it here also avoids a divide-by-zero)."
  [state id ix iy]
  (let [mass (get-in @state [:rigid-body-2d :bodies id :mass])]
    (when (and (get (:ents @state) id) (number? mass) (pos? mass))
      (swap! state update-in [:ents id]
             (fn [e] (assoc e
                            :vx (+ (:vx e) (/ ix mass))
                            :vy (+ (:vy e) (/ iy mass))))))
    nil))

(defn- rigid-body-scene-entities
  "Projects `ents` (the host ECS's flat id -> {:x :y :z :vx :vy :vz :tag}
  map) into `kotoba.physics.contract`'s 2D entity shape, for just the ids
  present in `bodies` ({id -> body-cfg}, physics-2d.backend's
  `:physics/body`). Z is untouched here — physics-2d is XY-plane only."
  [ents bodies]
  (into [] (keep (fn [[id body-cfg]]
                   (when-let [e (get ents id)]
                     {:entity/id id
                      :transform/position [(double (:x e)) (double (:y e))]
                      :physics/velocity [(double (:vx e)) (double (:vy e))]
                      :physics/body body-cfg})))
        bodies))

(defn step-rigid-bodies!
  "Advances every rigid-body-2d-tagged entity one frame through the shared
  `kotoba.physics.contract` using `physics-2d.backend/backend`, then writes
  the resulting :x/:y/:vx/:vy back onto the ECS `:ents`. `dt-ms` is `tick!`'s
  frame delta; clamped into physics-2d's required (0, 0.25] second range so a
  frame hitch can't throw mid-tick. No-op when there is no `:rigid-body-2d`
  config, no bodies in it, or none of those ids currently have a live entity
  (e.g. all despawned)."
  [state dt-ms]
  (when-let [rb (:rigid-body-2d @state)]
    (let [bodies (:bodies rb)]
      (when (seq bodies)
        (let [ents (:ents @state)
              scene-entities (rigid-body-scene-entities ents bodies)]
          (when (seq scene-entities)
            (let [dt-s (min 0.25 (max 1.0e-6 (/ (double dt-ms) 1000.0)))
                  scene (-> (physics-contract/make-scene
                             {:id :kami.host/rigid-body-2d :dimensions 2
                              :entities scene-entities})
                            (assoc :scene/forces {:gravity (or (:gravity rb) [0.0 -9.81])}))
                  stepped (physics-contract/step physics2d-backend/backend scene dt-s)]
              (swap! state update :ents
                     (fn [es]
                       (reduce (fn [m entity]
                                 (let [id (:entity/id entity)]
                                   (if (contains? m id)
                                     (let [[x y] (:transform/position entity)
                                           [vx vy] (:physics/velocity entity)]
                                       (assoc m id (assoc (get m id) :x x :y y :vx vx :vy vy)))
                                     m)))
                               es (:scene/entities stepped)))))))))))

#?(:cljs
   (do

(defn- mem-str [st ptr len]
  (if-let [mem (:mem @st)]
    (.decode (js/TextDecoder. "utf-8") (js/Uint8Array. (.-buffer mem) ptr len))
    ""))

(defn- ent [st id] (get-in @st [:ents (js/Number id)]))

;; the ECS tracks only position/velocity/rotation, never a render size — no entity
;; has a stored radius. `raycast` (below) approximates every entity as a sphere of this
;; radius, generous enough to hit a typical character/prop but tight enough that a shot
;; that clears past one target doesn't spuriously clip a second one behind it.
(def raycast-hit-radius 120)
(def raycast-max-range  6000)

;; --- import object: the kami:engine/* world over the atom ECS -----------------

(defn import-object [st]
  (let [bid #(js/BigInt %) n #(js/Number %)
        scene
        #js {:spawn (fn [ptr len]
                      (let [id (:next @st)]
                        (swap! st #(-> %
                                       (assoc-in [:ents id] {:tag (mem-str st ptr len) :x 0 :y 0 :z 0 :vx 0 :vy 0 :vz 0})
                                       (update :next inc)))
                        (bid id)))
             :despawn (fn [eid] (swap! st update :ents dissoc (n eid)) nil)
             :get-x (fn [eid] (or (:x (ent st eid)) 0))
             :get-y (fn [eid] (or (:y (ent st eid)) 0))
             :get-z (fn [eid] (or (:z (ent st eid)) 0))
             :set-position (fn [eid x y z]
                             (when (ent st eid)
                               (swap! st update-in [:ents (n eid)] assoc :x x :y y :z z)) nil)
             :get-vx (fn [eid] (or (:vx (ent st eid)) 0))
             :get-vy (fn [eid] (or (:vy (ent st eid)) 0))
             :get-vz (fn [eid] (or (:vz (ent st eid)) 0))
             :set-velocity (fn [eid vx vy vz]
                             (when (ent st eid)
                               (swap! st update-in [:ents (n eid)] assoc :vx vx :vy vy :vz vz)) nil)
             :get-rx (fn [_] 0) :get-ry (fn [_] 0) :get-rz (fn [_] 0) :get-rw (fn [_] 1)
             :set-rotation (fn [_ _ _ _ _] nil)
             :count-tagged (fn [ptr len]
                             (let [t (mem-str st ptr len)]
                               (bid (count (filter #(= (:tag (val %)) t) (:ents @st))))))
             :query-begin (fn [ptr len]
                            (let [t (mem-str st ptr len)
                                  ids (vec (keep (fn [[id e]] (when (= (:tag e) t) id)) (:ents @st)))
                                  h (:next-cur @st)]
                              (swap! st #(-> % (assoc-in [:cursors h] ids) (update :next-cur inc)))
                              (bid h)))
             :query-next (fn [handle]
                           (let [h (n handle) ids (get-in @st [:cursors h])]
                             (if (seq ids)
                               (do (swap! st assoc-in [:cursors h] (subvec ids 1)) (bid (first ids)))
                               (bid -1))))
             :nearest (fn [ptr len x y maxd]
                        (let [t (mem-str st ptr len)
                              best (->> (:ents @st)
                                        (filter (fn [[_ e]] (= (:tag e) t)))
                                        (map (fn [[id e]] [id (js/Math.hypot (- (:x e) x) (- (:y e) y))]))
                                        (filter (fn [[_ d]] (<= d maxd)))
                                        (sort-by second) ffirst)]
                          (bid (or best -1))))
             :move-toward (fn [eid target speed]
                            (let [e (ent st eid) tg (ent st (n target))]
                              (when (and e tg)
                                (let [dx (- (:x tg) (:x e)) dy (- (:y tg) (:y e)) d (js/Math.hypot dx dy)]
                                  (when (> d 1e-4)
                                    (swap! st update-in [:ents (n eid)] assoc
                                           :vx (* (/ dx d) speed) :vy (* (/ dy d) speed)))))) nil)}
        random #js {:int (fn [bound]
                           (let [s (bit-and (+ (* 1103515245 (:rng @st)) 12345) 0x7fffffff)]
                             (swap! st assoc :rng s)
                             (bid (if (pos? (n bound)) (mod s (n bound)) 0))))}
        physics #js {;; ADR-2607122400: apply-impulse — declared in the WASM ABI since
                     ;; ADR-2607121900 (kotoba.engine-clj.ast
                     ;; :host-import/physics-apply-impulse, module
                     ;; "kami:engine/physics@1.0.0" field "apply-impulse", i64 eid + 3×f32
                     ;; in / void out — mirrors `:set-velocity`'s [eid vx vy vz] shape), but
                     ;; left a hardcoded no-op until now — a compiled guest calling
                     ;; `(apply-impulse! eid ix iy iz)` linked and ran without erroring, but
                     ;; never actually moved anything. Closes the gap ADR-2607122200
                     ;; documented as open. iz is dropped (unused/must-be-0) before
                     ;; reaching the portable `apply-impulse!` below — physics-2d is
                     ;; XY-plane only. See `apply-impulse!`'s docstring above for the
                     ;; impulse-momentum relation and no-op behavior for non-rigid-body
                     ;; entities.
                     :apply-impulse (fn [eid ix iy _iz] (apply-impulse! st (n eid) ix iy))
                     ;; ADR-2607121900: raycast — declared in the WASM ABI
                     ;; (kotoba.engine-clj.ast :host-import/physics-raycast, module
                     ;; "kami:engine/physics@1.0.0" field "raycast", 6×f32 in / i64 out)
                     ;; since it was first wired, but never implemented host-side until
                     ;; now — a guest calling it got a WebAssembly.instantiate LinkError.
                     ;; Nearest entity hit along the ray from (ox,oy,oz) toward the
                     ;; (normalized) direction (dx,dy,dz), or -1. Ray-vs-sphere against
                     ;; every entity (see raycast-hit-radius/-max-range above) — the same
                     ;; O(n) full-ECS-scan idiom `:nearest` already uses below, just
                     ;; along a ray instead of within a radius of a point. Unlike
                     ;; `:nearest`, this is untargeted (no tag filter in the ABI) — it
                     ;; can return a "structure"/scenery hit too, which is the *correct*
                     ;; behavior for a hitscan weapon (walls should block shots). A
                     ;; caller wanting "did I hit a bot specifically" cross-checks the
                     ;; returned id against `nearest-tagged "bot" ...`; wanting to
                     ;; exclude itself compares the id against its own (the ABI has no
                     ;; exclude-self param to spend one of its 6 f32 slots on).
                     :raycast
                     (fn [ox oy oz dx dy dz]
                       (let [len (js/Math.hypot dx dy dz)
                             [ndx ndy ndz] (if (< len 1e-6) [0 0 1] [(/ dx len) (/ dy len) (/ dz len)])
                             best (->> (:ents @st)
                                       (keep (fn [[id e]]
                                               (let [aex (- (:x e) ox) aey (- (:y e) oy) aez (- (:z e) oz)
                                                     t (+ (* aex ndx) (* aey ndy) (* aez ndz))]
                                                 (when (and (>= t 0) (<= t raycast-max-range))
                                                   (let [px (+ ox (* ndx t)) py (+ oy (* ndy t)) pz (+ oz (* ndz t))
                                                         perp (js/Math.hypot (- (:x e) px) (- (:y e) py) (- (:z e) pz))]
                                                     (when (<= perp raycast-hit-radius) [id t]))))))
                                       (sort-by second) ffirst)]
                         (bid (or best -1))))
                     ;; declared in the ABI (:host-import/physics-apply-force) but not
                     ;; needed by any capability this ADR adds — left a no-op, same as
                     ;; :apply-impulse above, rather than guessed-at without a caller.
                     :apply-force (fn [_ _ _ _] nil)}
        input #js {:key-down    (fn [ptr len] (if (contains? (:keys @st) (mem-str st ptr len)) 1 0))
                   :key-pressed (fn [ptr len] (if (contains? (:keys @st) (mem-str st ptr len)) 1 0))
                   :axis        (fn [ptr len] (get (:axes @st) (mem-str st ptr len) 0.0))
                   ;; live pointer in 0..1 surface coordinates — kami.input's `:on-pointer`
                   ;; is what fills `:pointer`; hosts that never wire one keep reading the
                   ;; 0.0/0.0 these two returned unconditionally before.
                   :pointer-x   (fn [] (or (get-in @st [:pointer :x]) 0.0))
                   :pointer-y   (fn [] (or (get-in @st [:pointer :y]) 0.0))}
        render #js {:draw-mesh (fn [_ _ _ _ _] nil) :spawn-particle (fn [_ _ _ _ _] nil)
                    :draw-line (fn [_ _ _ _ _ _ _ _] nil)}
        audio  #js {:play (fn [_ _] nil) :stop (fn [_ _] nil) :play-at (fn [_ _ _ _ _] nil)}
        time   #js {:tick (fn [] (bid (:tick @st))) :elapsed-ms (fn [] (bid (* 16 (:tick @st))))}]
    (doto (js-obj)
      (aset "kami:engine/scene@1.0.0" scene)
      (aset "kami:engine/random@1.0.0" random)
      (aset "kami:engine/physics@1.0.0" physics)
      (aset "kami:engine/input@1.0.0" input)
      (aset "kami:engine/render@1.0.0" render)
      (aset "kami:engine/audio@1.0.0" audio)
      (aset "kami:engine/time@1.0.0" time))))

;; --- run a compiled game module ---------------------------------------------

(defn instantiate! [st wasm-bytes]
  (-> (js/WebAssembly.instantiate wasm-bytes (import-object st))
      (.then (fn [res]
               (let [inst (.-instance res) mdl (.-module res) exps (.-exports inst)]
                 (swap! st assoc :mem (aget exps "memory"))
                 (let [names (->> (js/WebAssembly.Module.exports mdl)
                                  (map #(.-name %)) (filter #(str/ends-with? % "-tick")) vec)]
                   (when-let [init (aget exps "init")] (init))
                   {:instance inst :exports exps :systems names :state st}))))))

(defn- resolve-collisions!
  "Push apart overlapping entities whose layers (tags) collide, per the EDN collision
   config (kami.physics). Layer = entity tag; the matrix decides who separates from whom.
   `skip-ids` (rigid-body-2d entities) are excluded from this ad-hoc layer-separation
   pass — physics-2d already resolves their collisions via impulse + positional
   correction in `step-rigid-bodies!`, so running both would double-resolve them."
  [state cfg skip-ids]
  (let [ents (:ents @state)
        pts (into [] (comp (remove (fn [[id _]] (contains? skip-ids id)))
                            (map (fn [[id e]] {:id id :layer (keyword (:tag e)) :x (:x e) :y (:y e)})))
                   ents)
        deltas (phys/separate cfg pts)]
    (when (seq deltas)
      (swap! state update :ents
             (fn [es]
               (reduce (fn [m [id [dx dy]]]
                         (if (get m id)
                           (-> m (update-in [id :x] + dx) (update-in [id :y] + dy))
                           m))
                       es deltas))))))

(defn- support-top
  "Side-scroller ground/platform support: the highest solid top under x that a *falling*
   (vy<=0) entity crosses from above (prevy→ny). solids: [[x0 x1 ytop …] …] (extra slots —
   thickness/colour — are the renderer's). One-way: you pass UP through a platform, land on
   top. Returns the y to rest on, or nil (airborne / over a pit)."
  [solids x prevy ny vy]
  (when (and solids (<= vy 0.0))
    (reduce (fn [best s]
              (let [x0 (nth s 0) x1 (nth s 1) yt (nth s 2)]
                (if (and (>= x x0) (<= x x1) (>= prevy (- yt 1.0)) (<= ny yt)
                         (or (nil? best) (> yt best)))
                  yt best)))
            nil solids)))

(defn tick!
  "Run each *-tick system (dt ms as i64/BigInt) in export order, integrate velocities into
   positions, step rigid-body-2d entities through the shared physics contract, then
   resolve EDN-configured layer collisions (host physics) for everything else.

   Optional 2D platformer physics (when the state holds a :platformer config — set by the
   host app from the scene EDN): entities whose tag is in :tags fall under :gravity (capped
   at :terminal), and land on :solids (ground + one-way platforms). This keeps the *guest*
   pure-constant (it only sets jump/float velocities + reads positions; gravity & collision
   live here, since the compiled guest can't do f32 arithmetic). No config → unchanged.

   Optional rigid-body-2d physics (when any entity has a component via `attach-rigid-body!`
   or the state holds a `:rigid-body-2d` config): those ids are excluded from the ad-hoc
   gravity/platformer/plain-integration pass below (only :z still integrates ad-hoc — z is
   an orthogonal axis physics-2d never touches) and from `resolve-collisions!`'s layer
   push-apart, then fully driven by `step-rigid-bodies!` — real impulse resolution through
   `kotoba.physics.contract/step` + `physics-2d.backend/backend`, not a second ad-hoc path."
  [{:keys [exports systems state cfg]} dt-ms]
  (let [dt (js/BigInt dt-ms) dts (/ dt-ms 1000.0)
        pf     (:platformer @state)
        g      (if pf (or (:gravity pf) 0.0) 0.0)
        term   (if pf (or (:terminal pf) -1e9) -1e9)
        gtags  (if pf (set (:tags pf)) #{})
        solids (when pf (:solids pf))
        rb-ids (rigid-body-ids state)]
    (doseq [s systems] ((aget exports s) dt))
    (swap! state update :tick inc)
    (swap! state update :ents
           (fn [ents]
             (persistent!
               (reduce-kv
                 (fn [m id e]
                   (let [nx (+ (:x e) (* (:vx e) dts))
                         nz (+ (:z e) (* (:vz e) dts))]
                     (cond
                       ;; rigid-body-2d owns :x/:y/:vx/:vy fully (step-rigid-bodies!,
                       ;; below); only :z still integrates ad-hoc here.
                       (contains? rb-ids id)
                       (assoc! m id (assoc e :z nz))

                       (contains? gtags (:tag e))
                       (let [vy    (max (- (:vy e) (* g dts)) term)   ;; host gravity
                             prevy (:y e)
                             ny    (+ prevy (* vy dts))
                             sup   (support-top solids nx prevy ny vy)]
                         (if sup
                           (assoc! m id (assoc e :x nx :z nz :y sup :vy 0.0 :grounded true))
                           (assoc! m id (assoc e :x nx :z nz :y ny :vy vy :grounded false))))

                       :else
                       (assoc! m id (assoc e :x nx :z nz :y (+ (:y e) (* (:vy e) dts)))))))
                 (transient {}) ents))))
    (step-rigid-bodies! state dt-ms)
    (resolve-collisions! state (or cfg phys/default-layers) rb-ids)))

(defn snapshot
  "Current entities as [{:id :tag :pos [x y z]} …]."
  [st]
  (mapv (fn [[id e]] (cond-> {:id id :tag (:tag e) :pos [(:x e) (:y e) (:z e)]}
                       (some? (:yaw e)) (assoc :yaw (:yaw e))))
        (:ents @st)))

(defn globals
  "Read the game's exported `defatom` cells (mutable WASM globals) as a {name → number} map —
   the host's window into lives/score/etc. without off-map marker entities. Empty if the game
   declares none (or on any read error — the HUD then falls back to marker counts)."
  [{:keys [exports]}]
  (let [out (atom {})]
    (try
      (when exports
        (doseq [k (array-seq (js/Object.keys exports))]
          (let [e (aget exports k)]
            (when (instance? js/WebAssembly.Global e)
              (swap! out assoc k (js/Number (.-value e)))))))
      (catch :default _ nil))
    @out))

     )

   :clj
   (do
     (defn import-object
       [_st]
       (throw (ex-info "kotoba.host/import-object is a browser ClojureScript WASM host"
                       {:namespace 'kotoba.host :platform :clj})))

     (defn instantiate!
       [_st _wasm-bytes]
       (throw (ex-info "kotoba.host/instantiate! is a browser ClojureScript WASM host"
                       {:namespace 'kotoba.host :platform :clj})))

     (defn tick!
       [_runtime _dt-ms]
       (throw (ex-info "kotoba.host/tick! is a browser ClojureScript WASM host"
                       {:namespace 'kotoba.host :platform :clj})))

     (defn snapshot
       "Current entities as [{:id :tag :pos [x y z]} ...]."
       [st]
       (mapv (fn [[id e]] {:id id :tag (:tag e) :pos [(:x e) (:y e) (:z e)]}) (:ents @st)))

     (defn globals
       [_runtime]
       {})))
