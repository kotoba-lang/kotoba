(ns input
  "KAMI Input — unified input system (keyboard, mouse, touch, gamepad,
  gesture) domain interpreter, plus multi-panel focus routing. Restored
  from the legacy kami-engine/kami-input Rust crate (deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root). Ledger class `:port-to-CLJC-domain-interpreter`
  (90-docs/migration/clj-wgsl-ledger.edn) — native event capture
  (keyboard/mouse/touch/gamepad) stays host-side; this namespace owns
  the platform-agnostic action mapping, gesture detection, and focus
  routing logic that consumes those raw events.

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. A
  single flat namespace (the original was one flat `lib.rs`).")

(def actions
  #{:move-up :move-down :move-left :move-right
    :zoom-in :zoom-out :pan-start :pan-end :pan-move
    :primary :secondary :cancel :confirm
    :jump :sprint :interact :attack
    :pause :reset :menu :fullscreen})

(def touch-phases #{:start :move :end :cancel})

;; Device is `:keyboard`/`:mouse`/`:touch`/`:stylus`/`[:gamepad pad-index]`.

(defn stylus-data
  ([] (stylus-data 0.0 0.0 0.0 0.0 0))
  ([pressure tilt-x tilt-y tangential-pressure twist]
   {:pressure pressure :tilt-x tilt-x :tilt-y tilt-y
    :tangential-pressure tangential-pressure :twist twist}))

;; ── Gesture detection ──────────────────────────

(defn gesture-state
  "A fresh gesture-detection state."
  []
  {:touches [] :pinch-distance nil :pinch-delta 0.0 :swipe nil :tap-count 0})

(defn- touch-point [id start current phase] {:id id :start start :current current :phase phase})

(defn- vec2-sub [[ax ay] [bx by]] [(- ax bx) (- ay by)])
(defn- vec2-length [[x y]] (Math/sqrt (+ (* x x) (* y y))))
(defn- vec2-normalize [[x y]] (let [l (vec2-length [x y])] (if (zero? l) [0.0 0.0] [(/ x l) (/ y l)])))

(defn- detect-pinch [state]
  (let [touches (:touches state)]
    (if (= 2 (count touches))
      (let [d (vec2-length (vec2-sub (:current (nth touches 0)) (:current (nth touches 1))))
            prev (:pinch-distance state)]
        (assoc state
               :pinch-delta (if prev (- d prev) (:pinch-delta state))
               :pinch-distance d))
      state)))

(defn process
  "Process a `[:touch {:phase :id :x :y}]` event and update gesture
  `state`. Non-touch events are ignored (matches the original's
  Touch-only match arm)."
  [state event]
  (if (not= (:type event) :touch)
    state
    (let [{:keys [phase id x y]} event
          pos [x y]]
      (case phase
        :start
        (-> state
            (update :touches conj (touch-point id pos pos phase))
            (assoc :tap-count 0))

        :move
        (-> state
            (update :touches (fn [ts] (mapv (fn [t] (if (= (:id t) id) (assoc t :current pos :phase phase) t)) ts)))
            detect-pinch)

        (:end :cancel)
        (let [t (first (filter #(= (:id %) id) (:touches state)))
              state (if t
                      (let [dist (vec2-length (vec2-sub (:current t) (:start t)))]
                        (cond
                          (< dist 10.0) (update state :tap-count inc)
                          (> dist 30.0) (assoc state :swipe (vec2-normalize (vec2-sub (:current t) (:start t))))
                          :else state))
                      state)]
          (-> state
              (update :touches (fn [ts] (vec (remove #(= (:id %) id) ts))))
              (assoc :pinch-distance nil)))))))

;; ── Input map (physical → abstract action) ──────

(defn input-map [bindings] {:bindings (vec bindings)})

(defn default-fps-map
  "Default WASD + arrow + gamepad mapping."
  []
  (input-map
   [["KeyW" :move-up] ["ArrowUp" :move-up]
    ["KeyS" :move-down] ["ArrowDown" :move-down]
    ["KeyA" :move-left] ["ArrowLeft" :move-left]
    ["KeyD" :move-right] ["ArrowRight" :move-right]
    ["Space" :jump] ["ShiftLeft" :sprint] ["KeyE" :interact] ["Escape" :pause]]))

(defn default-graph-map
  "Graph viewer mapping."
  []
  (input-map
   [["KeyW" :move-up] ["ArrowUp" :move-up]
    ["KeyS" :move-down] ["ArrowDown" :move-down]
    ["KeyA" :move-left] ["ArrowLeft" :move-left]
    ["KeyD" :move-right] ["ArrowRight" :move-right]
    ["Equal" :zoom-in] ["NumpadAdd" :zoom-in]
    ["Minus" :zoom-out] ["NumpadSubtract" :zoom-out]]))

(defn resolve-action
  "Resolve a physical `code` (e.g. \"KeyW\") to its bound action in `m`,
  or nil if unbound."
  [m code]
  (some (fn [[k a]] (when (= k code) a)) (:bindings m)))

;; ── Focus management ─────────────────────────────
;; Multi-panel/window focus routing for KAMI apps (OS, pptx, xlsx, maps).

(defn focus-manager
  "A fresh focus manager: no focus, empty modal stack, no global overlay."
  []
  {:focused nil :modal-stack [] :global-overlay false})

(defn set-focus [fm panel] (assoc fm :focused panel))

(defn clear-focus [fm panel] (if (= (:focused fm) panel) (assoc fm :focused nil) fm))

(defn push-modal
  "Push a modal onto the stack (captures input until popped)."
  [fm panel]
  (update fm :modal-stack conj panel))

(defn pop-modal
  "Pop the topmost modal. Returns `[popped-panel-or-nil fm']`."
  [fm]
  (if (seq (:modal-stack fm))
    [(peek (:modal-stack fm)) (update fm :modal-stack pop)]
    [nil fm]))

(defn set-global-overlay [fm active] (assoc fm :global-overlay active))

(defn resolve-focus
  "Resolve where an input event should be dispatched. Priority: global
  overlay > modal stack top > focused panel > `[:none]`."
  [fm]
  (cond
    (:global-overlay fm) [:global-overlay]
    (seq (:modal-stack fm)) [:modal (peek (:modal-stack fm))]
    (some? (:focused fm)) [:panel (:focused fm)]
    :else [:none]))

(defn focused-panel
  "The currently focused panel (ignoring modals/overlays)."
  [fm]
  (:focused fm))

(defn has-modal? [fm] (boolean (seq (:modal-stack fm))))
