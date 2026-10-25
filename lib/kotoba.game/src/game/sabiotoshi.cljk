(ns game.sabiotoshi
  "Sabi-Otoshi!! -- a 3D rust-restoration minigame, restored from the deleted
  kami-game Rust crate (kotoba-lang/kami-engine, PR #82) as zero-dependency
  portable CLJC (ADR-2607010930, com-junkawasaki/root).

  High-pressure-wash / wire-brush / sandpaper / chemical-solvent / polish /
  ultrasonic-clean vintage items back to shine. Items have 3D rust zones
  (some hidden until a disassembly step reveals them), a per-tool
  effectiveness matrix against 4 rust types (surface/deep/pitted/patina), a
  turntable camera for inspection, combo scoring, and CPC/UNSPSC product
  classification codes on both tools and items (this crate doubles as a
  product-catalog fixture generator).

  Ported 1:1 from `kami-game/src/sabiotoshi.rs`: the mutating
  `SabiotoshiGame` struct + `&mut self` methods become a plain state map
  plus pure functions returning the next state. `glam::Vec3` is a local
  `{:x :y :z}` duck-type (matching the sibling `game.ketsu` cluster-mate's
  convention, duplicated here so this file has zero intra-cluster
  dependency); `glam::Quat` is a local `{:x :y :z :w}` duck-type with only
  the identity and Y-axis-rotation constructors the original uses;
  `glam::Mat4` is a flat 16-element column-major vector, with
  `view-matrix` porting `Mat4::look_at_rh` by hand (not exercised by the
  original's tests, kept for 1:1 completeness). `InputState`
  (kami-game/src/input.rs, owned by another restoration cluster) is
  duck-typed as a plain map, same convention as `game.ketsu`. No platform
  divergence was needed (pure data/math), so no `#?(:clj/:cljs)`
  conditionals appear in this file.")

;; =============================================================================
;; Constants
;; =============================================================================

(def ^:private turntable-speed 0.8)
(def ^:private turntable-drag 0.95)
(def ^:private zoom-min 1.5)
(def ^:private zoom-max 6.0)
(def ^:private zoom-speed 0.3)
(def ^:private rust-removal-rate 0.016)

;; =============================================================================
;; Vec3 / Quat / Mat4 helpers
;; =============================================================================

(defn v3 ([] {:x 0.0 :y 0.0 :z 0.0}) ([x y z] {:x x :y y :z z}))
(def v3-zero (v3 0.0 0.0 0.0))
(def v3-one (v3 1.0 1.0 1.0))
(defn v3-add [a b] (v3 (+ (:x a) (:x b)) (+ (:y a) (:y b)) (+ (:z a) (:z b))))
(defn v3-sub [a b] (v3 (- (:x a) (:x b)) (- (:y a) (:y b)) (- (:z a) (:z b))))
(defn v3-scale [a s] (v3 (* (:x a) s) (* (:y a) s) (* (:z a) s)))
(defn v3-dot [a b] (+ (* (:x a) (:x b)) (* (:y a) (:y b)) (* (:z a) (:z b))))
(defn v3-cross [a b]
  (v3 (- (* (:y a) (:z b)) (* (:z a) (:y b)))
      (- (* (:z a) (:x b)) (* (:x a) (:z b)))
      (- (* (:x a) (:y b)) (* (:y a) (:x b)))))
(defn v3-length-squared [a] (v3-dot a a))
(defn v3-length [a] (Math/sqrt (v3-length-squared a)))
(defn v3-normalize [a]
  (let [len (v3-length a)]
    (if (zero? len) a (v3-scale a (/ 1.0 len)))))
(defn v3-lerp [a b t] (v3-add a (v3-scale (v3-sub b a) t)))
(defn v3-splat [s] (v3 s s s))

(def quat-identity {:x 0.0 :y 0.0 :z 0.0 :w 1.0})

(defn quat-from-rotation-y
  "Rotation of `angle` radians about the Y axis."
  [angle]
  (let [half (/ angle 2.0)]
    {:x 0.0 :y (Math/sin half) :z 0.0 :w (Math/cos half)}))

(defn mat4-look-at-rh
  "Port of `glam::Mat4::look_at_rh`. Returns a flat 16-element column-major
  vector of doubles. Not exercised by the original test suite; ported for
  1:1 completeness."
  [eye center up]
  (let [f (v3-normalize (v3-sub center eye))
        s (v3-normalize (v3-cross f up))
        u (v3-cross s f)]
    [(:x s) (:x u) (- (:x f)) 0.0
     (:y s) (:y u) (- (:y f)) 0.0
     (:z s) (:z u) (- (:z f)) 0.0
     (- (v3-dot s eye)) (- (v3-dot u eye)) (v3-dot f eye) 1.0]))

;; =============================================================================
;; Tool Types
;; =============================================================================

(def tool-kinds
  #{:pressure-washer :wire-brush :sandpaper :chemical-solvent :polishing-cloth :ultrasonic})

(defn tool-all [] [:pressure-washer :wire-brush :sandpaper :chemical-solvent :polishing-cloth :ultrasonic])

(def ^:private tool-name-table
  {:pressure-washer "Pressure Washer" :wire-brush "Wire Brush" :sandpaper "Sandpaper"
   :chemical-solvent "Chemical Solvent" :polishing-cloth "Polishing Cloth" :ultrasonic "Ultrasonic Cleaner"})

(def ^:private tool-name-ja-table
  {:pressure-washer "高圧洗浄機" :wire-brush "ワイヤーブラシ" :sandpaper "サンドペーパー"
   :chemical-solvent "錆取り液" :polishing-cloth "研磨クロス" :ultrasonic "超音波洗浄機"})

(defn tool-name [tool] (get tool-name-table tool))
(defn tool-name-ja [tool] (get tool-name-ja-table tool))

(def ^:private tool-effectiveness-table
  {:pressure-washer  {:surface 1.0 :deep 0.5 :pitted 0.2 :patina 0.8}
   :wire-brush       {:surface 0.6 :deep 1.0 :pitted 0.7 :patina 0.3}
   :sandpaper        {:surface 0.4 :deep 0.7 :pitted 1.0 :patina 0.5}
   :chemical-solvent {:surface 0.7 :deep 0.8 :pitted 0.8 :patina 1.0}
   :polishing-cloth  {:surface 0.9 :deep 0.1 :pitted 0.05 :patina 1.0}
   :ultrasonic       {:surface 0.9 :deep 0.9 :pitted 0.6 :patina 0.7}})

(defn tool-effectiveness [tool rust-type] (get-in tool-effectiveness-table [tool rust-type]))

(def ^:private tool-radius-table
  {:pressure-washer 0.3 :wire-brush 0.15 :sandpaper 0.12 :chemical-solvent 0.5 :polishing-cloth 0.2 :ultrasonic 1.0})

(defn tool-radius [tool] (get tool-radius-table tool))

(def ^:private tool-power-table
  {:pressure-washer 2.0 :wire-brush 3.0 :sandpaper 4.0 :chemical-solvent 1.5 :polishing-cloth 1.0 :ultrasonic 2.5})

(defn tool-power [tool] (get tool-power-table tool))

(def ^:private tool-cpc-code-table
  {:pressure-washer "44913" :wire-brush "42922" :sandpaper "42952"
   :chemical-solvent "34741" :polishing-cloth "26993" :ultrasonic "44914"})

(defn tool-cpc-code [tool] (get tool-cpc-code-table tool))

(def ^:private tool-unspsc-code-table
  {:pressure-washer "47131800" :wire-brush "27111700" :sandpaper "31191500"
   :chemical-solvent "47131600" :polishing-cloth "47131500" :ultrasonic "41113600"})

(defn tool-unspsc-code [tool] (get tool-unspsc-code-table tool))

(def ^:private tool-haptic-pattern-table
  {:pressure-washer 2 :wire-brush 1 :sandpaper 1 :chemical-solvent 0 :polishing-cloth 0 :ultrasonic 2})

(defn tool-haptic-pattern [tool] (get tool-haptic-pattern-table tool))

;; =============================================================================
;; Rust Types
;; =============================================================================

(def rust-types #{:surface :deep :pitted :patina})

(defn rust-type-color-rgb
  "[r g b] tint for a rust type at a given rust `level` (0.0-1.0)."
  [rust-type level]
  (let [t (min 1.0 (max 0.0 level))]
    (case rust-type
      :surface [(+ 0.65 (* t 0.25)) (+ 0.35 (* t 0.15)) (+ 0.1 (* t 0.05))]
      :deep    [(+ 0.5 (* t 0.35)) (+ 0.2 (* t 0.12)) (+ 0.05 (* t 0.05))]
      :pitted  [(+ 0.35 (* t 0.25)) (+ 0.12 (* t 0.08)) (+ 0.04 (* t 0.04))]
      :patina  [(+ 0.2 (* t 0.15)) (+ 0.45 (* t 0.2)) (+ 0.3 (* t 0.15))])))

;; =============================================================================
;; Rust Zone (3D)
;; =============================================================================

(defn rust-zone
  [{:keys [id center extent rust-type initial-level current-level nerf-grid-idx]}]
  {:id id :center center :extent extent :rust-type rust-type
   :initial-level initial-level :current-level current-level :nerf-grid-idx nerf-grid-idx})

(defn zone-clean? [zone] (<= (:current-level zone) 0.0))

(defn zone-contains-point?
  [zone local-point]
  (let [d (v3-sub local-point (:center zone))
        d (v3 (Math/abs (:x d)) (Math/abs (:y d)) (Math/abs (:z d)))]
    (and (<= (:x d) (:x (:extent zone)))
         (<= (:y d) (:y (:extent zone)))
         (<= (:z d) (:z (:extent zone))))))

;; =============================================================================
;; Disassembly
;; =============================================================================

(defn disassembly-step
  [{:keys [id name name-ja part-ids revealed-zones completed required-tool detach-offset]}]
  {:id id :name name :name-ja name-ja :part-ids (vec part-ids) :revealed-zones (vec revealed-zones)
   :completed (boolean completed) :required-tool required-tool :detach-offset detach-offset})

;; =============================================================================
;; Item Definition
;; =============================================================================

;; RestorableItem: {:id :name :name-ja :difficulty :base-score :perfect-bonus
;;                  :sdf-desc :entity-ids :zones :disassembly-steps
;;                  :cpc-code :unspsc-code :metal-color :metallic :roughness}

;; =============================================================================
;; Phase / Camera
;; =============================================================================

(def phases #{:title :inspecting :restoring :disassembling :item-clear :all-clear :timeout})

(defn turntable-camera-new []
  {:yaw 0.0 :pitch 0.3 :distance 3.0 :target v3-zero :yaw-velocity 0.0 :pitch-velocity 0.0})

(defn turntable-camera-update
  [cam drag-dx drag-dy zoom-delta dt]
  (let [yaw-vel (+ (:yaw-velocity cam) (* drag-dx turntable-speed))
        pitch-vel (+ (:pitch-velocity cam) (* drag-dy turntable-speed 0.5))
        yaw' (+ (:yaw cam) (* yaw-vel dt))
        pitch' (min 1.2 (max -1.2 (+ (:pitch cam) (* pitch-vel dt))))
        yaw-vel' (* yaw-vel turntable-drag)
        pitch-vel' (* pitch-vel turntable-drag)
        distance' (min zoom-max (max zoom-min (- (:distance cam) (* zoom-delta zoom-speed))))]
    (assoc cam :yaw yaw' :pitch pitch' :distance distance'
           :yaw-velocity yaw-vel' :pitch-velocity pitch-vel')))

(defn turntable-camera-eye-position
  [cam]
  (let [x (* (:distance cam) (Math/cos (:pitch cam)) (Math/sin (:yaw cam)))
        y (* (:distance cam) (Math/sin (:pitch cam)))
        z (* (:distance cam) (Math/cos (:pitch cam)) (Math/cos (:yaw cam)))]
    (v3-add (:target cam) (v3 x y z))))

(defn turntable-camera-view-matrix
  [cam]
  (mat4-look-at-rh (turntable-camera-eye-position cam) (:target cam) (v3 0.0 1.0 0.0)))

(defn turntable-camera-auto-rotate
  "Auto-rotate slowly when idle (for title / inspection)."
  [cam dt]
  (update cam :yaw + (* 0.3 dt)))

;; =============================================================================
;; Game State
;; =============================================================================

(defn new-game
  [items total-items]
  {:phase :title
   :tick 0
   :score 0
   :combo 0
   :max-combo 0
   :perfects 0
   :items-cleared 0
   :total-items total-items
   :time-remaining (+ 30.0 (* total-items 25.0))
   :camera (turntable-camera-new)
   :current-tool :pressure-washer
   :current-item-idx 0
   :items (vec items)
   :contact-point nil
   :is-applying-tool false
   :screen-shake 0.0
   :flash-color nil
   :message nil
   :haptic-request nil
   :sfx-request []
   :particle-request []
   :detaching-parts []
   :clear-timer 0.0})

(defn current-item [game] (get (:items game) (:current-item-idx game)))

(defn start-game
  [game]
  (-> game
      (assoc :phase :inspecting :score 0 :combo 0 :max-combo 0 :perfects 0
             :items-cleared 0 :current-item-idx 0 :camera (turntable-camera-new))
      (update :sfx-request conj "title_select")
      (assoc :haptic-request 1)
      (assoc :message ["Inspect the item -- rotate to find rust!" 3.0])))

(defn select-tool
  [game tool]
  (if (not= (:current-tool game) tool)
    (-> game (assoc :current-tool tool)
        (update :sfx-request conj "nozzle_switch")
        (assoc :haptic-request 0))
    game))

(defn begin-disassembly
  [game]
  (if (not (contains? #{:restoring :inspecting} (:phase game)))
    game
    (let [item (current-item game)]
      (if-not item
        game
        (let [steps (:disassembly-steps item)
              idx (first (keep-indexed (fn [i s] (when-not (:completed s) i)) steps))]
          (if (nil? idx)
            game
            (let [step (nth steps idx)]
              (if (and (:required-tool step) (not= (:required-tool step) (:current-tool game)))
                (-> game
                    (assoc :message [(str "Need " (tool-name (:required-tool step)) " for this step") 2.0])
                    (update :sfx-request conj "error"))
                (let [item-idx (:current-item-idx game)
                      new-parts (mapv (fn [pid] [pid v3-zero (:detach-offset step) 0.0]) (:part-ids step))]
                  (-> game
                      (assoc-in [:items item-idx :disassembly-steps idx :completed] true)
                      (assoc :phase :disassembling)
                      (update :detaching-parts into new-parts)
                      (update :sfx-request conj "rust_crack")
                      (assoc :haptic-request 2 :screen-shake 0.3)
                      (update :score + 50)
                      (assoc :message [(str (:name step) " -- disassembled!") 2.0])))))))))))

(defn- apply-tool
  "Apply the current tool at the current contact point (private -- called
  from `update-game` during :restoring)."
  [game dt]
  (let [contact (:contact-point game)
        item-idx (:current-item-idx game)
        item (get (:items game) item-idx)]
    (if (or (nil? contact) (nil? item))
      game
      (let [tool (:current-tool game)
            radius (tool-radius tool)
            power (tool-power tool)
            zones (:zones item)
            [game any-hit? zone-cleared?]
            (reduce
             (fn [[g hit? cleared?] zi]
               (let [zone (nth (:zones (get (:items g) item-idx)) zi)]
                 (if (zone-clean? zone)
                   [g hit? cleared?]
                   (let [dist (v3-length (v3-sub contact (:center zone)))]
                     (if (> dist (+ (v3-length (:extent zone)) radius))
                       [g hit? cleared?]
                       (let [effectiveness (tool-effectiveness tool (:rust-type zone))
                             removal (* power effectiveness rust-removal-rate dt 60.0)
                             prev (:current-level zone)
                             new-level (max 0.0 (- prev removal))
                             g (assoc-in g [:items item-idx :zones zi :current-level] new-level)]
                         (if (and (> prev 0.0) (<= new-level 0.0))
                           (let [combo' (inc (:combo g))
                                 max-combo' (max (:max-combo g) combo')
                                 pts (+ 10 (* (min combo' 12) 5))
                                 g (-> g
                                       (assoc :combo combo' :max-combo max-combo')
                                       (update :score + pts)
                                       (update :sfx-request conj "zone_clear")
                                       (update :sfx-request conj (str "combo_ding_" (min combo' 12)))
                                       (assoc :haptic-request 3 :screen-shake 0.2)
                                       (update :particle-request conj [(:center zone) 12 [1.0 0.96 0.88]]))]
                             [g true true])
                           [g true cleared?])))))))
             [game false false]
             (range (count zones)))
            game (if any-hit?
                   (let [g game
                         g (if (zero? (mod (:tick g) 3)) (update g :sfx-request conj "spray_loop") g)
                         g (if (zero? (mod (:tick g) 8)) (assoc g :haptic-request (tool-haptic-pattern tool)) g)]
                     g)
                   game)
            item' (get (:items game) item-idx)
            all-clean? (every? zone-clean? (:zones item'))]
        (if (and all-clean? zone-cleared?)
          (let [perfect? (>= (:combo game) (count (:zones item')))
                game (-> game
                         (update :score + (+ (:base-score item') (if perfect? (:perfect-bonus item') 0))))
                game (if perfect? (update game :perfects inc) game)
                game (update game :items-cleared inc)
                game (if (>= (:items-cleared game) (:total-items game))
                       (-> game (assoc :phase :all-clear)
                           (update :sfx-request conj "all_clear")
                           (assoc :haptic-request 3))
                       (-> game (assoc :phase :item-clear :clear-timer 0.0)
                           (update :sfx-request conj (if perfect? "perfect_finish" "item_complete"))
                           (assoc :haptic-request 2)))]
            (-> game
                (assoc :flash-color [1.0 1.0 0.8 0.25])
                (update :particle-request conj [v3-zero 30 [1.0 0.96 0.88]])))
          game)))))

(defn- handle-title [game input]
  (let [game (update game :camera turntable-camera-auto-rotate (/ 1.0 60.0))]
    (if (:interact input) (start-game game) game)))

(defn- handle-inspecting [game input dt]
  (let [game (-> game
                 (update :camera turntable-camera-update 0.0 0.0 0.0 dt)
                 (update :camera turntable-camera-auto-rotate (* dt 0.5)))
        game (if (:is-applying-tool game)
               (-> game (assoc :phase :restoring)
                   (assoc :message ["Restoring -- clean all rust zones!" 2.0]))
               game)]
    (if (:interact input) (begin-disassembly game) game)))

(defn- handle-restoring [game input dt]
  (let [time' (- (:time-remaining game) dt)]
    (if (<= time' 0.0)
      (-> game (assoc :time-remaining 0.0 :phase :timeout)
          (update :sfx-request conj "timeout")
          (assoc :haptic-request 2))
      (let [game (-> game (assoc :time-remaining time')
                     (update :camera turntable-camera-update 0.0 0.0 0.0 dt))
            game (if (:is-applying-tool game) (apply-tool game dt) game)
            game (if (:interact input) (begin-disassembly game) game)
            game (if (:forward input) (select-tool game :pressure-washer) game)]
        game))))

(defn- handle-disassembling [game dt]
  (let [game (update game :clear-timer + dt)
        parts (:detaching-parts game)
        parts' (mapv (fn [[id current target t]]
                        (let [t' (min 1.0 (+ t (* dt 2.0)))
                              ease (- 1.0 (Math/pow (- 1.0 t') 3))
                              current' (v3-lerp v3-zero target ease)]
                          [id current' target t']))
                      parts)
        done? (every? (fn [[_ _ _ t]] (>= t 1.0)) parts')]
    (if done?
      (-> game (assoc :detaching-parts []) (assoc :phase :restoring))
      (assoc game :detaching-parts parts'))))

(defn- handle-item-clear [game dt]
  (let [game (-> game (update :clear-timer + dt) (update :camera turntable-camera-auto-rotate dt))]
    (if (> (:clear-timer game) 2.5)
      (-> game (update :current-item-idx inc) (assoc :combo 0 :phase :inspecting :camera (turntable-camera-new)))
      game)))

(defn- handle-all-clear-timeout [game input dt]
  (let [game (update game :camera turntable-camera-auto-rotate (* dt 0.3))]
    (if (:interact input) (assoc game :phase :title) game)))

(defn update-game
  "Main game tick. `input` is `{:forward :backward :left :right :jump
  :interact :chat}` booleans (duck-typed InputState, matching `game.ketsu`).
  `dt` in seconds."
  [game input dt]
  (let [game (-> game
                 (update :tick inc)
                 (assoc :sfx-request [] :particle-request [] :haptic-request nil)
                 (update :screen-shake (fn [s] (if (pos? s) (max 0.0 (- s (* dt 4.0))) s)))
                 (update :message (fn [m] (when m (let [[msg t] m t' (- t dt)] (when (> t' 0.0) [msg t'])))))
                 (assoc :flash-color nil))]
    (case (:phase game)
      :title (handle-title game input)
      :inspecting (handle-inspecting game input dt)
      :restoring (handle-restoring game input dt)
      :disassembling (handle-disassembling game dt)
      :item-clear (handle-item-clear game dt)
      (:all-clear :timeout) (handle-all-clear-timeout game input dt))))

;; =============================================================================
;; Entity updates (renderer feed)
;; =============================================================================

(defn entity-positions
  [game]
  (let [item (current-item game)
        item-updates
        (when item
          (let [item-rot (quat-from-rotation-y (:yaw (:camera game)))]
            (for [eid (:entity-ids item)]
              (let [detach-pos (some (fn [[did current-pos _ _]] (when (= did eid) current-pos)) (:detaching-parts game))
                    detached-pos (some (fn [step] (when (and (:completed step)
                                                              (some #{eid} (:part-ids step))
                                                              (not= (:phase game) :disassembling))
                                                     (:detach-offset step)))
                                        (:disassembly-steps item))
                    pos (or detach-pos detached-pos v3-zero)]
                {:id eid :position pos :rotation item-rot :scale v3-one :visible true :rust-tint nil}))))
        zone-updates
        (when item
          (for [zone (:zones item) :when (> (:current-level zone) 0.0)]
            (let [rgb (rust-type-color-rgb (:rust-type zone) (:current-level zone))]
              {:id (str "rust_" (:id zone))
               :position (:center zone)
               :rotation (quat-from-rotation-y (:yaw (:camera game)))
               :scale (v3-scale (:extent zone) 2.0)
               :visible true
               :rust-tint [(nth rgb 0) (nth rgb 1) (nth rgb 2) (* (:current-level zone) 0.8)]})))
        cursor-update
        (when-let [cp (:contact-point game)]
          [{:id "tool_cursor" :position cp :rotation quat-identity
            :scale (v3-splat (* (tool-radius (:current-tool game)) 2.0))
            :visible (:is-applying-tool game) :rust-tint nil}])]
    (vec (concat item-updates zone-updates cursor-update))))

(defn grade
  "Letter grade ('S'/'A'/'B'/'C'/'D') from average score per item."
  [game]
  (let [avg (if (pos? (:total-items game)) (/ (double (:score game)) (:total-items game)) 0.0)
        avg-int (int avg)]
    (cond
      (>= avg-int 450) \S
      (>= avg-int 300) \A
      (>= avg-int 200) \B
      (>= avg-int 100) \C
      :else \D)))

;; =============================================================================
;; Item Catalog with CPC/UNSPSC
;; =============================================================================

(defn default-item-catalog
  "Build the default item catalog with CPC/UNSPSC product codes."
  []
  [{:id "wrench" :name "Vintage Wrench" :name-ja "ヴィンテージレンチ"
    :difficulty 1 :base-score 100 :perfect-bonus 50
    :sdf-desc "smooth_union(box(0.8,0.1,0.08), cylinder(0.15,0.3))"
    :entity-ids ["wrench_body" "wrench_jaw"]
    :zones [{:id "head" :center (v3 -0.3 0.0 0.0) :extent (v3 0.15 0.08 0.06) :rust-type :surface :initial-level 0.8 :current-level 0.8 :nerf-grid-idx nil}
            {:id "shaft" :center (v3 0.1 0.0 0.0) :extent (v3 0.25 0.04 0.04) :rust-type :surface :initial-level 0.4 :current-level 0.4 :nerf-grid-idx nil}
            {:id "handle" :center (v3 0.4 0.0 0.0) :extent (v3 0.12 0.06 0.06) :rust-type :surface :initial-level 0.3 :current-level 0.3 :nerf-grid-idx nil}]
    :disassembly-steps []
    :cpc-code "42322" :unspsc-code "27111700"
    :metal-color [0.7 0.7 0.72] :metallic 0.85 :roughness 0.35}

   {:id "skeleton_key" :name "Skeleton Key" :name-ja "アンティーク鍵"
    :difficulty 2 :base-score 200 :perfect-bonus 100
    :sdf-desc "union(torus(0.12,0.03), cylinder(0.02,0.4), box(0.08,0.06,0.02))"
    :entity-ids ["key_bow" "key_shaft" "key_bit"]
    :zones [{:id "bow" :center (v3 -0.2 0.0 0.0) :extent (v3 0.12 0.12 0.03) :rust-type :deep :initial-level 0.9 :current-level 0.9 :nerf-grid-idx 0}
            {:id "shaft" :center (v3 0.05 0.0 0.0) :extent (v3 0.18 0.02 0.02) :rust-type :surface :initial-level 0.5 :current-level 0.5 :nerf-grid-idx nil}
            {:id "bit" :center (v3 0.25 0.0 0.0) :extent (v3 0.08 0.06 0.02) :rust-type :pitted :initial-level 0.85 :current-level 0.85 :nerf-grid-idx 1}]
    :disassembly-steps []
    :cpc-code "42995" :unspsc-code "46171500"
    :metal-color [0.72 0.53 0.04] :metallic 0.9 :roughness 0.25}

   {:id "pocket_watch" :name "Pocket Watch" :name-ja "懐中時計"
    :difficulty 4 :base-score 500 :perfect-bonus 250
    :sdf-desc "smooth_union(cylinder(0.25,0.06), cylinder(0.03,0.04, translate(0,0.06,0)))"
    :entity-ids ["watch_case" "watch_face" "watch_crown" "watch_back"]
    :zones [{:id "case_front" :center (v3 0.0 0.03 0.0) :extent (v3 0.24 0.03 0.24) :rust-type :deep :initial-level 0.75 :current-level 0.75 :nerf-grid-idx 2}
            {:id "case_back" :center (v3 0.0 -0.03 0.0) :extent (v3 0.24 0.03 0.24) :rust-type :deep :initial-level 0.75 :current-level 0.75 :nerf-grid-idx 3}
            {:id "crown" :center (v3 0.0 0.08 0.0) :extent (v3 0.03 0.03 0.03) :rust-type :pitted :initial-level 0.9 :current-level 0.9 :nerf-grid-idx nil}
            {:id "face_hidden" :center (v3 0.0 0.01 0.0) :extent (v3 0.18 0.01 0.18) :rust-type :patina :initial-level 0.45 :current-level 0.45 :nerf-grid-idx nil}]
    :disassembly-steps [{:id "open_case" :name "Open Case Back" :name-ja "裏蓋を開ける"
                          :part-ids ["watch_back"] :revealed-zones ["face_hidden"]
                          :completed false :required-tool nil :detach-offset (v3 0.0 -0.4 0.0)}]
    :cpc-code "45121" :unspsc-code "54111600"
    :metal-color [0.75 0.75 0.78] :metallic 0.92 :roughness 0.15}

   {:id "katana_tsuba" :name "Katana Tsuba" :name-ja "刀の鍔"
    :difficulty 5 :base-score 600 :perfect-bonus 300
    :sdf-desc "difference(smooth_union(box(0.18,0.01,0.14), box(0.14,0.012,0.18)), box(0.02,0.02,0.06))"
    :entity-ids ["tsuba_body" "tsuba_rim" "tsuba_nakago"]
    :zones [{:id "face_a" :center (v3 -0.06 0.005 0.0) :extent (v3 0.08 0.006 0.12) :rust-type :surface :initial-level 0.65 :current-level 0.65 :nerf-grid-idx 4}
            {:id "face_b" :center (v3 0.06 0.005 0.0) :extent (v3 0.08 0.006 0.12) :rust-type :surface :initial-level 0.65 :current-level 0.65 :nerf-grid-idx 5}
            {:id "rim" :center v3-zero :extent (v3 0.18 0.01 0.14) :rust-type :deep :initial-level 0.8 :current-level 0.8 :nerf-grid-idx nil}
            {:id "nakago_ana" :center v3-zero :extent (v3 0.02 0.01 0.05) :rust-type :pitted :initial-level 0.95 :current-level 0.95 :nerf-grid-idx nil}
            {:id "engraving_hidden" :center (v3 -0.04 -0.005 0.03) :extent (v3 0.03 0.004 0.06) :rust-type :patina :initial-level 0.5 :current-level 0.5 :nerf-grid-idx nil}]
    :disassembly-steps [{:id "flip_tsuba" :name "Flip Tsuba" :name-ja "鍔を裏返す"
                          :part-ids [] :revealed-zones ["engraving_hidden"]
                          :completed false :required-tool nil :detach-offset v3-zero}]
    :cpc-code "42925" :unspsc-code "46181500"
    :metal-color [0.25 0.25 0.28] :metallic 0.95 :roughness 0.2}])
