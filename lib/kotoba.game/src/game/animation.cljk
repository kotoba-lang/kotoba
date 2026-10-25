(ns game.animation
  "Restored from kami-game/src/animation.rs (kotoba-lang/kami-engine, deleted in PR #82),
  as part of the Rust→CLJC restoration (ADR-2607010930, com-junkawasaki/root).

  Nintendo-style animation system with smooth, bouncy, juicy motions. Supports
  bobbing, spinning, squash/stretch, wobble, pop-in, head bob, pulse glow, and
  a glitch preset. All state is plain CLJC data; `tick` is a pure function
  taking (clip, dt) and returning [clip' output] rather than mutating in place
  like the original `&mut self` Rust methods.")

(def PI #?(:clj Math/PI :cljs js/Math.PI))
(def TAU (* 2.0 PI))

(defn- sin [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- powf [b e] #?(:clj (Math/pow (double b) (double e)) :cljs (js/Math.pow b e)))

;; ---------------------------------------------------------------------------
;; Vec3 helpers (plain [x y z] vectors)
;; ---------------------------------------------------------------------------

(def vec3-zero [0.0 0.0 0.0])
(def vec3-one [1.0 1.0 1.0])

(defn vec3-splat [s] [s s s])

(defn vec3-add [a b]
  [(+ (a 0) (b 0)) (+ (a 1) (b 1)) (+ (a 2) (b 2))])

(defn vec3-mul [a b]
  [(* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))])

(defn vec3-length [[x y z]]
  #?(:clj (Math/sqrt (double (+ (* x x) (* y y) (* z z))))
     :cljs (js/Math.sqrt (+ (* x x) (* y y) (* z z)))))

;; ---------------------------------------------------------------------------
;; Quaternion helpers (plain [x y z w] vectors, matching glam::Quat layout)
;; ---------------------------------------------------------------------------

(def quat-identity [0.0 0.0 0.0 1.0])

(defn quat-from-rotation-y
  "Rotation of `angle` radians about the Y axis."
  [angle]
  (let [half (/ angle 2.0)]
    [0.0 (sin half) 0.0 #?(:clj (Math/cos (double half)) :cljs (js/Math.cos half))]))

(defn quat-mul
  "Hamilton product a*b, [x y z w] layout (matches glam::Quat Mul)."
  [[ax ay az aw] [bx by bz bw]]
  [(+ (* aw bx) (* ax bw) (* ay bz) (- (* az by)))
   (+ (* aw by) (- (* ax bz)) (* ay bw) (* az bx))
   (+ (* aw bz) (* ax by) (- (* ay bx)) (* az bw))
   (- (* aw bw) (* ax bx) (* ay by) (* az bz))])

(defn quat-to-axis-angle
  "Returns [axis angle-radians], mirroring glam::Quat::to_axis_angle for tests
  (only the angle component is exercised by the ported tests)."
  [[x y z w]]
  (let [w' (max -1.0 (min 1.0 w))
        angle (* 2.0 #?(:clj (Math/acos (double w')) :cljs (js/Math.acos w')))
        s (vec3-length [x y z])]
    (if (< s 1.0e-8)
      [[1.0 0.0 0.0] 0.0]
      [[(/ x s) (/ y s) (/ z s)] angle])))

;; ---------------------------------------------------------------------------
;; AnimationOutput
;; ---------------------------------------------------------------------------

(def default-output
  {:position-offset vec3-zero
   :rotation-offset quat-identity
   :scale-multiplier vec3-one})

(defn combine-output
  "Combine two outputs: additive position, multiplicative rotation, multiplicative scale."
  [a b]
  {:position-offset (vec3-add (:position-offset a) (:position-offset b))
   :rotation-offset (quat-mul (:rotation-offset a) (:rotation-offset b))
   :scale-multiplier (vec3-mul (:scale-multiplier a) (:scale-multiplier b))})

;; ---------------------------------------------------------------------------
;; AnimationClip: keyword-tagged maps, one per Rust enum variant.
;; ---------------------------------------------------------------------------

(def head-bob-phases #{:rise :hold :drop :wait})

(defn bobbing [amplitude frequency phase]
  {:type :bobbing :amplitude amplitude :frequency frequency :phase phase})

(defn spinning [speed angle]
  {:type :spinning :speed speed :angle angle})

(defn squash-stretch [squash-scale stretch-scale duration timer active]
  {:type :squash-stretch :squash-scale squash-scale :stretch-scale stretch-scale
   :duration duration :timer timer :active active})

(defn wobble [intensity speed phase]
  {:type :wobble :intensity intensity :speed speed :phase phase})

(defn pop-in [target-scale duration timer overshoot]
  {:type :pop-in :target-scale target-scale :duration duration :timer timer :overshoot overshoot})

(defn head-bob [rise-height rise-time hold-time drop-time wait-time timer phase]
  {:type :head-bob :rise-height rise-height :rise-time rise-time :hold-time hold-time
   :drop-time drop-time :wait-time wait-time :timer timer :phase phase})

(defn pulse-glow [min-scale max-scale speed phase]
  {:type :pulse-glow :min-scale min-scale :max-scale max-scale :speed speed :phase phase})

(defn glitch [interval timer intensity seed]
  {:type :glitch :interval interval :timer timer :intensity intensity :seed seed})

(defn- wrapping-mul-add-u32
  "u32 wrapping_mul then wrapping_add, matching Rust's wraparound semantics."
  [s]
  (bit-and (+ (bit-and (* s 1103515245) 0xFFFFFFFF) 12345) 0xFFFFFFFF))

(defn- clip-tick
  "Advance a single clip by dt seconds. Returns [clip' output]."
  [clip dt]
  (case (:type clip)
    :bobbing
    (let [phase' (+ (:phase clip) (* dt (:frequency clip) TAU))
          out (assoc default-output :position-offset [0.0 (* (:amplitude clip) (sin phase')) 0.0])]
      [(assoc clip :phase phase') out])

    :spinning
    (let [angle' (+ (:angle clip) (* dt (:speed clip)))
          out (assoc default-output :rotation-offset (quat-from-rotation-y angle'))]
      [(assoc clip :angle angle') out])

    :squash-stretch
    (if-not (:active clip)
      [clip default-output]
      (let [timer' (+ (:timer clip) dt)
            duration (:duration clip)]
        (if (>= timer' duration)
          [(assoc clip :active false :timer 0.0) default-output]
          (let [t (/ timer' duration)
                squash? (< t 0.5)
                ;; two independent half-cycle sine waves, one per phase, each
                ;; 0 at its own start and end -- NOT a single sin(t*PI) hump
                ;; that peaks (f=1) exactly at the squash/stretch handoff
                ;; (t=0.5). A single hump meant the blend factor was at its
                ;; MAXIMUM the instant the phase switched, so scale jumped
                ;; straight from the full squash extreme to the full stretch
                ;; extreme in one frame instead of relaxing through the
                ;; identity scale (1.0) in between.
                local-t (if squash? (* 2.0 t) (* 2.0 (- t 0.5)))
                f (sin (* local-t PI))
                [s0 s1 s2] (if squash?
                             (:squash-scale clip)
                             (:stretch-scale clip))
                scale [(+ 1.0 (* (- s0 1.0) f))
                       (+ 1.0 (* (- s1 1.0) f))
                       (+ 1.0 (* (- s2 1.0) f))]]
            [(assoc clip :timer timer') (assoc default-output :scale-multiplier scale)]))))

    :wobble
    (let [phase' (+ (:phase clip) (* dt (:speed clip) TAU))
          p phase'
          i (:intensity clip)
          scale [(+ 1.0 (* i (sin p)))
                 (+ 1.0 (* i (sin (+ (* p 1.3) 0.5))))
                 (+ 1.0 (* i (sin (+ (* p 0.7) 1.0))))]]
      [(assoc clip :phase phase') (assoc default-output :scale-multiplier scale)])

    :pop-in
    (let [timer' (+ (:timer clip) dt)
          duration (:duration clip)
          t (min 1.0 (/ timer' duration))
          overshoot (:overshoot clip)
          elastic (if (>= t 1.0)
                    1.0
                    (let [p 0.3
                          s (/ p 4.0)
                          t1 (- t 1.0)]
                      (+ (* overshoot (powf 2.0 (* -10.0 t))
                            (sin (/ (* (- t1 s) 2.0 PI) p)))
                         1.0)))
          [ts0 ts1 ts2] (:target-scale clip)
          scale [(* ts0 elastic) (* ts1 elastic) (* ts2 elastic)]]
      [(assoc clip :timer timer') (assoc default-output :scale-multiplier scale)])

    :head-bob
    (let [timer' (+ (:timer clip) dt)
          rise-height (:rise-height clip)]
      (case (:phase clip)
        :rise
        (if (>= timer' (:rise-time clip))
          [(assoc clip :timer 0.0 :phase :hold)
           (assoc default-output :position-offset [0.0 rise-height 0.0])]
          (let [t (/ timer' (:rise-time clip))]
            [(assoc clip :timer timer')
             (assoc default-output :position-offset [0.0 (* rise-height (sin (* t PI 0.5))) 0.0])]))

        :hold
        (let [out (assoc default-output :position-offset [0.0 rise-height 0.0])]
          (if (>= timer' (:hold-time clip))
            [(assoc clip :timer 0.0 :phase :drop) out]
            [(assoc clip :timer timer') out]))

        :drop
        (if (>= timer' (:drop-time clip))
          [(assoc clip :timer 0.0 :phase :wait) default-output]
          (let [t (- 1.0 (/ timer' (:drop-time clip)))]
            [(assoc clip :timer timer')
             (assoc default-output :position-offset [0.0 (* rise-height t) 0.0])]))

        :wait
        (if (>= timer' (:wait-time clip))
          [(assoc clip :timer 0.0 :phase :rise) default-output]
          [(assoc clip :timer timer') default-output])))

    :pulse-glow
    (let [phase' (+ (:phase clip) (* dt (:speed clip) TAU))
          t (+ (* (sin phase') 0.5) 0.5)
          s (+ (:min-scale clip) (* (- (:max-scale clip) (:min-scale clip)) t))]
      [(assoc clip :phase phase') (assoc default-output :scale-multiplier (vec3-splat s))])

    :glitch
    (let [timer' (+ (:timer clip) dt)
          interval (:interval clip)
          [timer'' seed'] (if (>= timer' interval)
                             [0.0 (wrapping-mul-add-u32 (:seed clip))]
                             [timer' (:seed clip)])
          intensity (:intensity clip)
          s seed'
          fx (* (- (/ (double (bit-and s 0xFF)) 255.0) 0.5) 2.0 intensity)
          fy (* (- (/ (double (bit-and (bit-shift-right s 8) 0xFF)) 255.0) 0.5) 2.0 intensity)
          fz (* (- (/ (double (bit-and (bit-shift-right s 16) 0xFF)) 255.0) 0.5) 2.0 intensity)]
      [(assoc clip :timer timer'' :seed seed')
       (assoc default-output :position-offset [fx fy fz])])))

;; ---------------------------------------------------------------------------
;; AnimationState: {:animations [clip ...]}
;; ---------------------------------------------------------------------------

(defn new-state [] {:animations []})

(defn with-clip [state clip]
  (update state :animations conj clip))

(defn tick
  "Advance all animations by dt and combine outputs. Returns [state' output]."
  [state dt]
  (loop [clips (:animations state)
         acc []
         result default-output]
    (if (empty? clips)
      [(assoc state :animations acc) result]
      (let [[clip' out] (clip-tick (first clips) dt)]
        (recur (rest clips) (conj acc clip') (combine-output result out))))))

(defn trigger-squash-stretch
  "Activate any SquashStretch clips (for landing/bouncing triggers)."
  [state]
  (update state :animations
          (fn [clips]
            (mapv (fn [c]
                    (if (= (:type c) :squash-stretch)
                      (assoc c :active true :timer 0.0)
                      c))
                  clips))))

;; ---------------------------------------------------------------------------
;; Preset factories
;; ---------------------------------------------------------------------------

(defn skibidi-idle []
  {:animations [(head-bob 2.0 1.0 0.5 0.5 2.0 0.0 :wait)
                (spinning 3.0 0.0)]})

(defn grimace-wobble []
  {:animations [(wobble 0.05 2.0 0.0)
                (bobbing 0.2 0.5 0.0)]})

(defn item-pickup []
  {:animations [(bobbing 0.3 1.5 0.0)
                (spinning 2.0 0.0)
                (pulse-glow 0.9 1.1 2.0 0.0)]})

(defn sigma-idle [] {:animations []})

(defn ohio-glitch []
  {:animations [(glitch 0.1 0.0 0.15 42)]})

(defn pop-spawn []
  {:animations [(pop-in [1.0 1.0 1.0] 0.3 0.0 1.3)]})

(defn nintendo-bounce []
  {:animations [(squash-stretch [1.3 0.7 1.3] [0.85 1.2 0.85] 0.4 0.0 false)]})

;; Emote presets (gftd:kami/emote animation-preset mapping)

(defn emote-wave []
  {:animations [(bobbing 0.15 2.0 0.0)
                (spinning 0.5 0.0)]})

(defn emote-dance []
  {:animations [(bobbing 0.4 3.0 0.0)
                (spinning 4.0 0.0)
                (wobble 0.06 3.0 0.0)]})

(defn emote-taunt []
  {:animations [(pop-in [1.2 1.2 1.2] 0.2 0.0 1.5)
                (glitch 0.08 0.0 0.1 77)]})

(defn emote-celebrate []
  {:animations [(pop-in [1.3 1.3 1.3] 0.3 0.0 1.4)
                (spinning 6.0 0.0)
                (pulse-glow 0.85 1.15 3.0 0.0)]})

(defn emote-sad []
  {:animations [(bobbing 0.05 0.3 0.0)
                (pulse-glow 0.85 0.95 0.5 0.0)]})

(defn emote-rage []
  {:animations [(glitch 0.05 0.0 0.25 99)
                (squash-stretch [1.4 0.6 1.4] [0.7 1.4 0.7] 0.2 0.0 true)]})

(defn from-emote-preset
  "Create emote AnimationState from a WIT animation-preset string."
  [preset]
  (case preset
    "idle" (sigma-idle)
    "bobbing" (with-clip (new-state) (bobbing 0.3 1.0 0.0))
    "spinning" (with-clip (new-state) (spinning 3.0 0.0))
    "wobble" (grimace-wobble)
    "pop-in" (pop-spawn)
    "pulse-glow" (with-clip (new-state) (pulse-glow 0.8 1.2 2.0 0.0))
    "glitch" (ohio-glitch)
    "head-bob" (skibidi-idle)
    "squash-stretch" (nintendo-bounce)
    "wave" (emote-wave)
    "dance" (emote-dance)
    "taunt" (emote-taunt)
    "celebrate" (emote-celebrate)
    "sad" (emote-sad)
    "rage" (emote-rage)
    (new-state)))
