;; KAMI Waves — gameplay authored in the kami-clj subset, showcasing the expanded forms
;; (-> · clamp · dotimes · case · even? · max). The Rust host compiles this to WASM and drives
;; init + systems; it holds none of this logic (ADR-0036/0038). Visual profile lives in scene.edn.

(def base-period  18)
(def max-burst    6)
(def kill-range   (f32 240.0))
(def spawn-radius (f32 500.0))

(defn player []
  (nearest-tagged "player" (f32 0.0) (f32 0.0) (f32 1000000.0)))

;; difficulty ramps with time, clamped — threaded for readability (-> + clamp)
(defn burst-size []
  (-> (tick-n) (quot 600) inc (clamp 1 max-burst)))

(defn init []
  (let [p (spawn-entity "player")]
    (set-position! p (f32 0.0) (f32 0.0) (f32 0.0))))

(defsystem control [dt]
  (let [p (player)]
    (when (not= p -1)
      (set-velocity! p (axis "MoveX") (axis "MoveY") (f32 0.0)))))

;; spawn a wave burst (dotimes); even waves use cardinal slots, odd waves diagonal (even? + case)
(defsystem spawn [dt]
  (when (zero? (mod (tick-n) base-period))
    (let [wave (quot (tick-n) base-period)]
      (dotimes [k (burst-size)]
        (let [e (spawn-entity "enemy")
              slot (mod (+ k wave) 4)]
          (if (even? wave)
            (case slot
              0 (set-position! e spawn-radius (f32 0.0) (f32 0.0))
              1 (set-position! e (f32 -500.0) (f32 0.0) (f32 0.0))
              2 (set-position! e (f32 0.0) spawn-radius (f32 0.0))
              (set-position! e (f32 0.0) (f32 -500.0) (f32 0.0)))
            (case slot
              0 (set-position! e (f32 360.0) (f32 360.0) (f32 0.0))
              1 (set-position! e (f32 -360.0) (f32 360.0) (f32 0.0))
              2 (set-position! e (f32 360.0) (f32 -360.0) (f32 0.0))
              (set-position! e (f32 -360.0) (f32 -360.0) (f32 0.0)))))))))

(defsystem ai [dt]
  (let [p (player)]
    (when (not= p -1)
      (doseq-entities [e "enemy"]
        (move-toward! e p (f32 90.0))))))

;; auto-fire rate eases as difficulty rises (max keeps a floor); clears the nearest enemy in range
(defsystem weapon [dt]
  (when (zero? (mod (tick-n) (max 8 (- 20 (burst-size)))))
    (let [p (player)]
      (when (not= p -1)
        (let [hit (nearest-tagged "enemy" (get-x p) (get-y p) kill-range)]
          (when (not= hit -1) (despawn-entity hit)))))))
