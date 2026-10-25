(ns game.prediction
  "Client-side prediction + server reconciliation.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/prediction.rs`.
  Vec3 is represented as a plain 3-vector `[x y z]`.

  Client applies inputs immediately (predicted state). Server sends
  authoritative state at server tick. Client replays unconfirmed inputs
  from the last confirmed tick. Remote entities are interpolated between
  known states.")

(def ^:const buffer-size 128)
(def ^:const snap-threshold 5.0) ;; teleport if delta > threshold

;; -----------------------------------------------------------------------
;; Local Vec3 math (no hard dep on any other cluster's vector namespace).
;; -----------------------------------------------------------------------

(defn- v3-add [[x1 y1 z1] [x2 y2 z2]] [(+ x1 x2) (+ y1 y2) (+ z1 z2)])
(defn- v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn- v3-distance [[x1 y1 z1] [x2 y2 z2]]
  (Math/sqrt (+ (Math/pow (- x2 x1) 2) (Math/pow (- y2 y1) 2) (Math/pow (- z2 z1) 2))))
(defn- v3-lerp [[x1 y1 z1] [x2 y2 z2] a]
  [(+ x1 (* (- x2 x1) a)) (+ y1 (* (- y2 y1) a)) (+ z1 (* (- z2 z1) a))])
(defn- clamp [v lo hi] (max lo (min hi v)))

;; InputSnapshot: {:tick :input-velocity :predicted-position}
;; PredictionBuffer: {:buffer {tick-mod-N -> InputSnapshot} :last-confirmed-tick :last-confirmed-position}

(defn prediction-buffer-new
  []
  {:buffer {}
   :last-confirmed-tick 0
   :last-confirmed-position [0.0 0.0 0.0]})

(defn push
  "Record a local input + predicted position at `tick`. Returns updated buffer."
  [pbuf tick input-velocity predicted-position]
  (let [idx (mod tick buffer-size)]
    (assoc-in pbuf [:buffer idx]
              {:tick tick :input-velocity input-velocity :predicted-position predicted-position})))

(defn- predicted-at [pbuf tick]
  (let [idx (mod tick buffer-size)
        snap (get-in pbuf [:buffer idx])]
    (when (and snap (= (:tick snap) tick))
      (:predicted-position snap))))

(defn reconcile
  "Server confirmed state at `server-tick`. Reconcile the prediction buffer.
  Returns [corrected-position pbuf']."
  [pbuf server-tick server-position current-tick dt]
  (let [predicted (predicted-at pbuf server-tick)]
    (if (and predicted (> (v3-distance predicted server-position) snap-threshold))
      [server-position (assoc pbuf
                               :last-confirmed-tick server-tick
                               :last-confirmed-position server-position)]
      (let [pbuf' (assoc pbuf
                          :last-confirmed-tick server-tick
                          :last-confirmed-position server-position)
            pos (reduce
                 (fn [pos tick]
                   (let [idx (mod tick buffer-size)
                         snap (get-in pbuf' [:buffer idx])]
                     (if (and snap (= (:tick snap) tick))
                       (v3-add pos (v3-scale (:input-velocity snap) dt))
                       pos)))
                 server-position
                 (range (inc server-tick) (inc current-tick)))]
        [pos pbuf']))))

(defn last-confirmed-position [pbuf]
  (:last-confirmed-position pbuf))

;; RemoteInterpolation: {:prev-position :target-position :prev-tick :target-tick}

(defn remote-interpolation-new
  []
  {:prev-position [0.0 0.0 0.0]
   :target-position [0.0 0.0 0.0]
   :prev-tick 0
   :target-tick 0})

(defn push-state
  "Update remote interpolation state with a new server state at `tick`."
  [interp tick position]
  (assoc interp
         :prev-position (:target-position interp)
         :prev-tick (:target-tick interp)
         :target-position position
         :target-tick tick))

(defn interpolate
  "Interpolate between prev and target positions. `alpha` clamped to 0..1."
  [interp alpha]
  (v3-lerp (:prev-position interp) (:target-position interp) (clamp alpha 0.0 1.0)))
