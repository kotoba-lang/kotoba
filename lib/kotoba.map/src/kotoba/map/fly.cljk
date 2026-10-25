(ns kotoba.map.fly
  "Fly-to camera animation easing.

  Ported 1:1 from the fly-animation block of `KamiMap::frame` in
  `kami-map/src/lib.rs` (Rust, kotoba-lang/kami-engine), per ADR-2607010930
  (clj-wgsl migration Phase 4). Pure state-transition function — the caller
  (an actor/UI event loop) owns the animation-frame side effects (calling
  this once per `dt-ms` tick and re-rendering); this namespace only computes
  the eased center/zoom for one step.")

(defn ease-smoothstep
  "Cubic smoothstep: `t*t*(3-2t)`, matching the Rust source's easing curve."
  [t]
  (* t t (- 3.0 (* 2.0 t))))

(defn step
  "Advance a fly-to animation by `dt-ms`. `fly` is
  `{:start-center [lng lat] :target-center [lng lat] :start-zoom
    :target-zoom :duration-ms :elapsed-ms}`. Returns
  `{:center [lng lat] :zoom :elapsed-ms :done?}` — when `:done?` is true the
  caller should drop the fly-target (matching `self.fly_target = None`)."
  [{:keys [start-center target-center start-zoom target-zoom duration-ms elapsed-ms]} dt-ms]
  (let [elapsed' (+ elapsed-ms dt-ms)
        t (min 1.0 (/ elapsed' duration-ms))
        ease (ease-smoothstep t)
        [slng slat] start-center
        [tlng tlat] target-center]
    {:center [(+ slng (* (- tlng slng) ease))
              (+ slat (* (- tlat slat) ease))]
     :zoom (+ start-zoom (* (- target-zoom start-zoom) ease))
     :elapsed-ms elapsed'
     :done? (>= t 1.0)}))

(defn fly-target
  "Construct a fly-to target from the current viewport to `[lng lat]` at
  `zoom`, matching `KamiMap::fly_to`."
  [current-center current-zoom lng lat zoom duration-ms]
  {:start-center current-center
   :target-center [lng lat]
   :start-zoom current-zoom
   :target-zoom zoom
   :duration-ms duration-ms
   :elapsed-ms 0.0})
