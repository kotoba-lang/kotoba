;; KAMI Survivors — gameplay, in the kami-clj subset.
;;
;; This file IS the game's behaviour. The Rust host (kami-clj-play) compiles it
;; to WASM at startup and drives init + systems; it contains none of this logic
;; itself — Rust is only the GPU arm (ADR-0036). The numeric knobs here are the
;; gameplay tuning; the *visual* profile (colours/sizes) lives in scene.edn,
;; which Datomic/datalevin owns.
;;
;; Guest arithmetic is integer-only, so positions use absolute f32 constants and
;; the host keeps the player inside the arena (see scene.edn :world/arena).

(def max-alive     120)
(def spawn-period  14)
(def fire-period   16)
(def enemy-speed   (f32 95.0))
(def weapon-range  (f32 260.0))
(def contact-range (f32 20.0))
(def spawn-radius  (f32 520.0))

(defn player []
  (nearest-tagged "player" (f32 0.0) (f32 0.0) (f32 1000000.0)))

(defn init []
  (let [p (spawn-entity "player")]
    (set-position! p (f32 0.0) (f32 0.0) (f32 0.0))))

;; movement: host feeds analog axes (already scaled to px/s) into velocity.
(defsystem control [dt]
  (let [p (player)]
    (when (not= p -1)
      (set-velocity! p (axis "MoveX") (axis "MoveY") (f32 0.0)))))

;; wave spawn: capped + tick-gated, on a ring around the origin.
(defsystem spawn [dt]
  (when (< (count-tagged "enemy") max-alive)
    (when (zero? (mod (tick-n) spawn-period))
      (let [r (rand-int 4)
            e (spawn-entity "enemy")]
        (cond
          (= r 0) (set-position! e spawn-radius (f32 0.0)    (f32 0.0))
          (= r 1) (set-position! e (f32 -520.0) (f32 0.0)    (f32 0.0))
          (= r 2) (set-position! e (f32 0.0)    spawn-radius (f32 0.0))
          :else   (set-position! e (f32 0.0)    (f32 -520.0) (f32 0.0)))))))

;; AI: every enemy walks toward the player.
(defsystem ai [dt]
  (let [p (player)]
    (when (not= p -1)
      (doseq-entities [e "enemy"]
        (move-toward! e p enemy-speed)))))

;; auto-fire: each shot removes the nearest enemy within range.
(defsystem weapon [dt]
  (when (zero? (mod (tick-n) fire-period))
    (let [p (player)]
      (when (not= p -1)
        (let [hit (nearest-tagged "enemy" (get-x p) (get-y p) weapon-range)]
          (when (not= hit -1)
            (despawn-entity hit)))))))

;; contact: an enemy that reaches the player is consumed.
(defsystem contact [dt]
  (let [p (player)]
    (when (not= p -1)
      (let [touch (nearest-tagged "enemy" (get-x p) (get-y p) contact-range)]
        (when (not= touch -1)
          (despawn-entity touch))))))
