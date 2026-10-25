(ns game.ketsu
  "Goriketsu Dash!! -- a chase minigame, restored from the deleted kami-game
  Rust crate (kotoba-lang/kami-engine, PR #82) as zero-dependency portable
  CLJC (ADR-2607010930, com-junkawasaki/root).

  Slap the sleeping gorilla's butt to wake it, then flee through a forest of
  12 trees while bananas fall and you collect them, across 3 escalating
  waves (more bananas, golden bonus bananas, faster/ground-pounding
  gorilla). Features: sprint stamina, tree-hiding (safe radius), near-miss
  score bonus, banana-collection combo multiplier, and a peaceful
  alternative path (wait 30s without slapping -> the gorilla wakes
  peacefully instead of chasing you, true ending).

  Ported 1:1 from `kami-game/src/ketsu.rs`: the mutating `GoriketsuGame`
  struct + `&mut self` methods become a plain state map plus pure functions
  that return the next state (`update` takes `[game input dt]` and returns
  the updated game; there is no in-place mutation). `glam::Vec3` becomes a
  plain `{:x :y :z}` map with local vec-math helpers (only `x`/`z` are ever
  nonzero for gameplay positions here, but `y` is carried for parity with
  the original and used by `entity-positions` for render offsets).
  `InputState` (kami-game/src/input.rs, owned by another restoration
  cluster) is duck-typed here as a plain map with the same 6 boolean keys
  (`:forward :backward :left :right :jump :interact`; `:chat` is accepted
  but unused, matching the original). No platform divergence was needed
  (pure data/math), so no `#?(:clj/:cljs)` conditionals appear in this file.")

;; =============================================================================
;; Constants
;; =============================================================================

(def ^:private arena 30.0)
(def ^:private player-speed 5.0)
(def ^:private sprint-speed 8.5)
(def ^:private stamina-max 100.0)
(def ^:private stamina-drain 1.2)
(def ^:private stamina-regen 0.4)
(def ^:private stamina-rate-baseline 60.0)
(def ^:private slap-range 4.5)
(def ^:private catch-range 2.5)
(def ^:private near-miss-range 4.0)
(def ^:private tree-count 12)
(def ^:private tree-safe-radius 3.0)
(def ^:private banana-pickup-range 2.75)
(def ^:private hide-duration 3.0)
(def ^:private peace-wait 30.0)
(def ^:private max-catches-per-wave 5)

;; Wave configuration: banana count, golden count, gorilla speed range,
;; ground pound flag (ground-pound is carried for parity but unused by the
;; simulation logic below, matching the Rust original which also never
;; reads it after construction).
(def ^:private waves
  [{:bananas 4 :golden 0 :speed-min 4.0 :speed-max 5.2 :ground-pound false}
   {:bananas 6 :golden 1 :speed-min 4.6 :speed-max 6.5 :ground-pound true}
   {:bananas 5 :golden 1 :speed-min 5.0 :speed-max 7.1 :ground-pound true}])

(defn- wave-for [game]
  (nth waves (min (:wave game) (dec (count waves)))))

;; =============================================================================
;; Vec3 helpers (glam::Vec3 duck-type)
;; =============================================================================

(defn v3 ([] {:x 0.0 :y 0.0 :z 0.0}) ([x y z] {:x x :y y :z z}))
(def v3-zero (v3 0.0 0.0 0.0))
(defn v3-add [a b] (v3 (+ (:x a) (:x b)) (+ (:y a) (:y b)) (+ (:z a) (:z b))))
(defn v3-sub [a b] (v3 (- (:x a) (:x b)) (- (:y a) (:y b)) (- (:z a) (:z b))))
(defn v3-scale [a s] (v3 (* (:x a) s) (* (:y a) s) (* (:z a) s)))
(defn v3-length-squared [a] (+ (* (:x a) (:x a)) (* (:y a) (:y a)) (* (:z a) (:z a))))
(defn v3-length [a] (Math/sqrt (v3-length-squared a)))
(defn v3-distance [a b] (v3-length (v3-sub a b)))
(defn v3-normalize [a]
  (let [len (v3-length a)]
    (if (zero? len) a (v3-scale a (/ 1.0 len)))))
(defn v3-normalize-or-zero [a]
  (let [len (v3-length a)]
    (if (< len 1e-10) v3-zero (v3-scale a (/ 1.0 len)))))
(defn v3-clamp [a lo hi]
  (v3 (min (max (:x a) (:x lo)) (:x hi))
      (min (max (:y a) (:y lo)) (:y hi))
      (min (max (:z a) (:z lo)) (:z hi))))

;; =============================================================================
;; Types
;; =============================================================================

(def phases #{:title :sneak :alert :chase :rest :victory :peace-victory :game-over})
(def gorilla-states #{:sleeping :waking :waking-peace :chasing :friendly :resting :caught})

(defn tree [pos height] {:pos pos :height height :shake-timer 0.0})
(defn banana [pos golden? fall-height] {:pos pos :golden golden? :collected false :fall-height fall-height :grounded false})

;; =============================================================================
;; Snapshot (serializable, mirrors GoriketsuSnapshot)
;; =============================================================================

(defn snapshot
  "Renderer/UI-facing snapshot of the game state."
  [game]
  {:phase (name (:phase game))
   :tick (:tick game)
   :score (:score game)
   :hi-score (:hi-score game)
   :wave (:wave game)
   :bananas-needed (:bananas-needed game)
   :bananas-collected (:bananas-collected game)
   :stamina (:stamina game)
   :hiding (:hiding game)
   :peace-path (:peace-path game)
   :catches-taken (:catches-taken game)
   :catches-remaining (max 0 (- max-catches-per-wave (:catches-taken game)))
   :combo (:combo game)
   :player {:x (:x (:player-pos game)) :z (:z (:player-pos game))}
   :gorilla {:x (:x (:gorilla-pos game)) :z (:z (:gorilla-pos game))}
   :message (when-let [[msg _] (:message game)] msg)
   :bananas (mapv (fn [b] {:x (:x (:pos b)) :z (:z (:pos b)) :grounded (:grounded b)
                            :collected (:collected b) :golden (:golden b)})
                   (:bananas game))
   :trees (mapv (fn [t] {:x (:x (:pos t)) :z (:z (:pos t))}) (:trees game))})

;; =============================================================================
;; Game construction
;; =============================================================================

(defn new-game
  "Fresh Goriketsu game in the :sneak phase, gorilla asleep at origin."
  []
  (let [trees (vec (for [i (range tree-count)]
                      (let [angle (* (/ (double i) tree-count) (* 2.0 Math/PI))
                            r (+ 8.0 (mod (* i 1.7) 14.0))]
                        (tree (v3 (* (Math/cos angle) r) 0.0 (* (Math/sin angle) r))
                              (+ 4.0 (mod (* i 0.7) 3.0))))))]
    {:phase :sneak
     :tick 0
     :score 0
     :hi-score 0
     :wave 0
     :wave-rest-timer 0.0
     :player-pos (v3 0.0 0.0 -18.0)
     :player-vel v3-zero
     :stamina stamina-max
     :sprinting false
     :hiding false
     :hide-timer 0.0
     :catches-taken 0
     :gorilla-pos v3-zero
     :gorilla-vel v3-zero
     :gorilla-state :sleeping
     :anger 0.0
     :wake-timer 0.0
     :trees trees
     :bananas []
     :bananas-needed 0
     :bananas-collected 0
     :combo 0
     :combo-timer 0.0
     :near-miss-count 0
     :near-miss-cooldown 0.0
     :peace-timer 0.0
     :peace-path false
     :screen-shake 0.0
     :hit-stop-frames 0
     :flash-color nil
     :message nil}))

;; =============================================================================
;; Update
;; =============================================================================

(defn- update-hi-score [game]
  (if (> (:score game) (:hi-score game)) (assoc game :hi-score (:score game)) game))

(defn- spawn-bananas-from-trees [game]
  (let [wc (wave-for game)
        needed (+ (:bananas wc) (:golden wc))
        normal (for [i (range (:bananas wc))]
                 (let [t (nth (:trees game) (mod i (count (:trees game))))
                       offset (v3 (* (Math/sin (* i 7.3)) 3.0) 0.0 (* (Math/cos (* i 4.1)) 3.0))]
                   (banana (v3-add (:pos t) offset) false (+ 3.0 (mod (* i 0.5) 2.0)))))
        golden (for [i (range (:golden wc))]
                 (let [offset (v3 (* (Math/sin (* i 3.7)) 5.0) 0.0 (* (Math/cos (* i 2.3)) 5.0))]
                   (banana (v3-add (:gorilla-pos game) offset) true 4.0)))]
    (assoc game
           :bananas (vec (concat normal golden))
           :bananas-collected 0
           :bananas-needed needed)))

(defn- handle-rest-phase [game dt]
  (let [game (update game :wave-rest-timer - dt)]
    (if (<= (:wave-rest-timer game) 0.0)
      (let [wave' (inc (:wave game))]
        (if (>= wave' (count waves))
          (-> game (assoc :phase :victory)
              (update :score + (* 500 wave'))
              (assoc :screen-shake 1.0)
              (assoc :message ["MORI WA MODOTTA!" 5.0])
              update-hi-score)
          (-> game
              (assoc :wave wave')
              (assoc :gorilla-state :sleeping)
              (assoc :anger (* wave' 15.0))
              (assoc :gorilla-pos v3-zero)
              (assoc :gorilla-vel v3-zero)
              (assoc :phase :sneak)
              (assoc :message [(str "Wave " (inc wave')) 1.5]))))
      game)))

(defn- movement-dir [input]
  (let [dx (+ (if (:left input) -1.0 0.0) (if (:right input) 1.0 0.0))
        dz (+ (if (:forward input) -1.0 0.0) (if (:backward input) 1.0 0.0))
        d (v3 dx 0.0 dz)]
    (if (> (v3-length-squared d) 0.0) (v3-normalize d) d)))

(defn- apply-slap [game]
  (let [d (v3-distance (:player-pos game) (:gorilla-pos game))]
    (if (< d slap-range)
      (-> game
          (assoc :phase :alert :gorilla-state :waking :wake-timer 1.0 :anger 30.0)
          (update :score + 100)
          (assoc :screen-shake 1.2 :hit-stop-frames 6)
          (assoc :message ["BACHI!!" 1.5])
          spawn-bananas-from-trees
          (update :trees (fn [trees]
                            (mapv (fn [t] (if (< (v3-distance (:pos t) (:player-pos game)) 15.0)
                                            (assoc t :shake-timer 0.3) t))
                                  trees))))
      (assoc game :message ["Too far! Get closer!" 0.8]))))

(defn- update-gorilla-ai [game dt]
  (case (:gorilla-state game)
    :sleeping game

    :waking
    (let [game (update game :wake-timer - dt)]
      (if (<= (:wake-timer game) 0.0)
        (-> game (assoc :gorilla-state :chasing :phase :chase)
            (assoc :message ["NIGEROOOO!!" 1.0]))
        game))

    :waking-peace
    (let [game (update game :wake-timer - dt)]
      (if (<= (:wake-timer game) 0.0)
        (-> game (assoc :gorilla-state :friendly :phase :peace-victory)
            (update :score + 2000)
            (assoc :message ["tataku yori wakariaeta!" 5.0])
            update-hi-score)
        game))

    :chasing
    (let [wc (wave-for game)
          game (update game :anger (fn [a] (min 100.0 (+ a (* 0.08 dt 60.0)))))
          chase-speed (+ (:speed-min wc) (* (/ (:anger game) 100.0) (- (:speed-max wc) (:speed-min wc))))
          gorilla-vel (if (:hiding game)
                        (let [t (* (:tick game) 0.02)]
                          (v3-scale (v3 (Math/cos t) 0.0 (Math/sin t)) 2.0))
                        (let [to-player (v3-sub (:player-pos game) (:gorilla-pos game))
                              d (v3-length to-player)]
                          (if (> d 0.1)
                            (v3-scale to-player (/ chase-speed d))
                            (:gorilla-vel game))))
          gorilla-pos (v3-clamp (v3-add (:gorilla-pos game) (v3-scale gorilla-vel dt))
                                 (v3 (- arena) 0.0 (- arena)) (v3 arena 0.0 arena))
          game (assoc game :gorilla-vel gorilla-vel :gorilla-pos gorilla-pos)
          pd (v3-distance (:player-pos game) gorilla-pos)
          ;; Near-miss.
          game (if (and (< pd near-miss-range) (>= pd catch-range) (not (:hiding game))
                        (<= (:near-miss-cooldown game) 0.0))
                 (-> game
                     (update :near-miss-count inc)
                     (assoc :near-miss-cooldown 0.5)
                     (as-> g (update g :score + (* 25 (:near-miss-count g))))
                     (assoc :flash-color [1.0 0.0 0.0 0.15]))
                 game)
          ;; Catch / knockback.
          game (if (and (not (:hiding game)) (< pd catch-range))
                 (let [knockback (v3-scale (v3-normalize-or-zero (v3-sub (:player-pos game) gorilla-pos)) 20.0)
                       game (-> game
                                (assoc :player-vel knockback)
                                (update :player-pos v3-add (v3-scale knockback (* dt 3.0)))
                                (assoc :screen-shake 1.8 :hit-stop-frames 8)
                                (update :score #(max 0 (- % 50)))
                                (update :catches-taken inc)
                                (assoc :message ["FUKITOBASHI!!" 0.5]))]
                   (if (>= (:catches-taken game) max-catches-per-wave)
                     (-> game (assoc :phase :game-over :gorilla-state :caught :screen-shake 2.0)
                         (assoc :message ["TSUKAMATTA..." 5.0])
                         update-hi-score)
                     game))
                 game)]
      ;; Tree collision (gorilla).
      (update game :trees (fn [trees]
                             (mapv (fn [t] (if (< (v3-distance (:gorilla-pos game) (:pos t)) 3.0)
                                             (assoc t :shake-timer 0.3) t))
                                   trees))))

    game))

(defn update-game
  "Main game tick. `input` is `{:forward :backward :left :right :jump
  :interact :chat}` booleans (duck-typed InputState). `dt` in seconds
  (target 1/60)."
  [game input dt]
  (if (pos? (:hit-stop-frames game))
    (update game :hit-stop-frames dec)
    (let [game (-> game
                   (update :screen-shake (fn [s] (max 0.0 (- s (* dt 10.0)))))
                   (assoc :flash-color nil))]
      (case (:phase game)
        (:title :victory :peace-victory :game-over) game
        :rest (handle-rest-phase game dt)
        (let [game (-> game
                       (update :tick inc)
                       (update :message (fn [m] (when m
                                                   (let [[msg dur] m dur' (- dur dt)]
                                                     (when (> dur' 0.0) [msg dur'])))))
                       (as-> g (if (> (:combo-timer g) 0.0)
                                 (let [g (update g :combo-timer - dt)]
                                   (if (<= (:combo-timer g) 0.0) (assoc g :combo 0) g))
                                 g))
                       (as-> g (if (> (:near-miss-cooldown g) 0.0) (update g :near-miss-cooldown - dt) g)))

              ;; Player movement.
              dir (movement-dir input)
              sprinting (boolean (:jump input))
              stamina-step (* dt stamina-rate-baseline)
              [speed stamina'] (if (and sprinting (pos? (:stamina game)))
                                 [sprint-speed (max 0.0 (- (:stamina game) (* stamina-drain stamina-step)))]
                                 [player-speed (min stamina-max (+ (:stamina game) (* stamina-regen stamina-step)))])
              player-vel (v3-scale dir speed)
              player-pos (v3-clamp (v3-add (:player-pos game) (v3-scale player-vel dt))
                                    (v3 (- arena) 0.0 (- arena)) (v3 arena 0.0 arena))
              game (assoc game :sprinting sprinting :stamina stamina' :player-vel player-vel :player-pos player-pos)

              ;; Slap.
              game (if (and (:interact input) (= (:phase game) :sneak)) (apply-slap game) game)

              ;; Peaceful path.
              game (if (and (= (:phase game) :sneak) (not (:peace-path game)))
                     (let [game (update game :peace-timer + dt)]
                       (if (>= (:peace-timer game) peace-wait)
                         (-> game (assoc :peace-path true :gorilla-state :waking-peace :wake-timer 1.5)
                             (assoc :message ["gorira ga sotto me wo aketa..." 2.0]))
                         game))
                     game)

              ;; Tree collision / hiding.
              in-tree-cover? (and (= (:phase game) :chase)
                                   (some #(< (v3-distance (:player-pos game) (:pos %)) tree-safe-radius) (:trees game)))
              game (cond
                     in-tree-cover?
                     (-> game
                         (as-> g (if-not (:hiding g) (assoc g :hide-timer hide-duration) g))
                         (assoc :hiding true))
                     (:hiding game)
                     (let [game (update game :hide-timer - dt)]
                       (if (<= (:hide-timer game) 0.0) (assoc game :hiding false) game))
                     :else game)

              ;; Tree shake decay.
              game (update game :trees (fn [trees] (mapv (fn [t] (update t :shake-timer #(max 0.0 (- % dt)))) trees)))

              ;; Banana fall physics.
              game (update game :bananas
                           (fn [bananas]
                             (mapv (fn [b]
                                     (if (:grounded b)
                                       b
                                       (let [fh (- (:fall-height b) (* 9.81 dt))]
                                         (if (<= fh 0.0)
                                           (assoc b :fall-height 0.0 :grounded true)
                                           (assoc b :fall-height fh)))))
                                   bananas)))

              ;; Banana collection.
              [game collected-any?]
              (reduce (fn [[g any?] idx]
                        (let [b (nth (:bananas g) idx)]
                          (if (or (:collected b) (not (:grounded b)))
                            [g any?]
                            (if (< (v3-distance (:player-pos g) (:pos b)) banana-pickup-range)
                              (let [combo' (inc (:combo g))
                                    mult (if (:golden b) 3 1)
                                    bonus (* 10 combo' mult)]
                                [(-> g
                                     (assoc-in [:bananas idx :collected] true)
                                     (update :bananas-collected inc)
                                     (assoc :combo combo' :combo-timer 1.5)
                                     (update :score + bonus))
                                 true])
                              [g any?]))))
                      [game false]
                      (range (count (:bananas game))))

              ;; Gorilla AI.
              game (update-gorilla-ai game dt)

              ;; Wave clear check.
              game (if (and (= (:phase game) :chase) (>= (:bananas-collected game) (:bananas-needed game)))
                     (if (>= (:wave game) (dec (count waves)))
                       (-> game (assoc :phase :victory)
                           (update :score + (* 500 (inc (:wave game))))
                           (assoc :screen-shake 1.0)
                           (assoc :message ["MORI WA MODOTTA!" 5.0])
                           update-hi-score)
                       (-> game (assoc :phase :rest :wave-rest-timer 2.0 :gorilla-state :resting
                                       :gorilla-vel v3-zero :catches-taken 0 :screen-shake 0.6)
                           (assoc :message [(str "Wave " (inc (:wave game)) " CLEAR!") 1.5])))
                     game)]
          game)))))

;; =============================================================================
;; Entity updates (renderer feed)
;; =============================================================================

(defn entity-positions
  "Per-frame entity position/scale/visibility list for the renderer."
  [game]
  (let [player {:id "player" :position (v3-add (:player-pos game) (v3 0.0 0.8 0.0))
                :scale (v3 1.0 1.0 1.0)
                :visible (or (not (:hiding game)) (< (mod (:tick game) 10) 7))}
        gs (if (= (:gorilla-state game) :waking) 1.08 1.0)
        gorilla {:id "gorilla" :position (v3-add (:gorilla-pos game) (v3 0.0 1.4 0.0))
                 :scale (v3 gs gs gs) :visible true}
        butt-pulse (+ 0.3 (* (Math/abs (Math/sin (* (:tick game) 0.08))) 0.7))
        butt-scale (+ 1.0 (* butt-pulse 0.3))
        gorilla-butt {:id "gorilla-butt" :position (v3-add (:gorilla-pos game) (v3 0.0 1.0 -1.0))
                      :scale (v3 butt-scale butt-scale butt-scale) :visible true}
        trees (map-indexed
               (fn [i t]
                 (let [shake-offset (if (> (:shake-timer t) 0.0)
                                      (* (Math/sin (* (:tick game) 20.0)) (:shake-timer t) 0.5)
                                      0.0)]
                   {:id (str "tree-" i)
                    :position (v3-add (:pos t) (v3 shake-offset (* (:height t) 0.5) 0.0))
                    :scale (v3 1.0 1.0 1.0) :visible true}))
               (:trees game))
        bananas (->> (:bananas game)
                     (map-indexed vector)
                     (keep (fn [[i b]]
                             (when-not (:collected b)
                               (let [bob (if (:grounded b)
                                           (* (Math/sin (+ (* (:tick game) 0.08) i)) 0.15)
                                           0.0)]
                                 {:id (str "banana-" i)
                                  :position (v3-add (:pos b) (v3 0.0 (+ (:fall-height b) 0.3 bob) 0.0))
                                  :scale (if (:golden b) (v3 1.3 1.3 1.3) (v3 1.0 1.0 1.0))
                                  :visible true})))))]
    (vec (concat [player gorilla gorilla-butt] trees bananas))))
