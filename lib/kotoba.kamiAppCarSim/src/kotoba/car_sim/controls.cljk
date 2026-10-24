(ns kotoba.car-sim.controls
  "Pure control-signal interpretation, ported from `kami-app-car-sim`'s
  `on_update` frame handler (`src/lib.rs`). The Rust original reads raw
  numbers off `window.__carsim_*` JS globals and immediately applies them
  to a live `kami_vehicle::Vehicle`; that JS read and the vehicle mutation
  are both host-adapter/physics concerns out of scope for this port
  (ADR-2607010000). What's ported here is the PURE middle step — clamping
  and one-shot-command interpretation — so a host adapter only has to: (1)
  read the raw numbers from wherever its input source is, (2) call these
  functions, (3) apply the returned semantic command to a real vehicle.

  Pure data in, pure data out: no network, no I/O. Portable across
  JVM / ClojureScript / SCI / GraalVM."
  )

(defn clamp [v lo hi] (max lo (min hi v)))

(defn clamp-controls
  "Clamp raw `{:throttle :brake :handbrake :steer}` (any subset; missing
  keys default to 0.0) into vehicle-safe ranges: throttle/brake/handbrake
  in `[0, 1]`, steer in `[-1, 1]`. Mirrors the four `.clamp(..)` calls in
  `on_update`."
  [{:keys [throttle brake handbrake steer]
    :or {throttle 0.0 brake 0.0 handbrake 0.0 steer 0.0}}]
  {:throttle (clamp throttle 0.0 1.0)
   :brake (clamp brake 0.0 1.0)
   :handbrake (clamp handbrake 0.0 1.0)
   :steer (clamp steer -1.0 1.0)})

(defn resolve-gear-request
  "Given the vehicle's current `{:current-gear :shift-progress}` gearbox
  state and a raw `requested-gear` signal (0.0 = \"no request\", per the
  JS bridge convention), return the gearbox state to apply: unchanged when
  the request is 0 or already matches `current-gear`, otherwise the new
  gear with `:shift-progress` reset to 1.0 (mirrors the `if req != 0.0 ...
  if g != current_gear` branch in `on_update`)."
  [{:keys [current-gear] :as gearbox-state} requested-gear]
  (if (or (nil? requested-gear) (zero? requested-gear))
    gearbox-state
    (let [g (long requested-gear)]
      (if (= g current-gear)
        gearbox-state
        (assoc gearbox-state :current-gear g :shift-progress 1.0)))))

(defn interpret-detach-repair
  "Interpret the raw one-shot `__carsim_detach` / `__carsim_repair` signal
  numbers into a semantic command map, or `nil` when neither fires.
  `detach-req > 0` -> `{:command :detach :group detach-req}`.
  `repair-req == 999` -> `{:command :repair-all}` (the magic \"repair
  everything\" sentinel). `repair-req > 0` (and not 999) -> `{:command
  :repair-group :group repair-req}`. Detach takes priority when both fire
  in the same frame (mirrors `on_update`'s independent `if` order, where
  detach is checked first)."
  [detach-req repair-req]
  (let [detach (long (or detach-req 0))
        repair (long (or repair-req 0))]
    (cond
      (pos? detach) {:command :detach :group detach}
      (= repair 999) {:command :repair-all}
      (pos? repair) {:command :repair-group :group repair}
      :else nil)))
