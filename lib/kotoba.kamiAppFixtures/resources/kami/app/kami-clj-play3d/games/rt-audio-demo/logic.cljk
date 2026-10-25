;; KAMI RT + binaural-audio demo — exercises the new host imports end-to-end:
;;   (rt-enable! "gi")              → the frame is traced with the kami.rt "gi"
;;                                    recipe (WGSL ray-query / per-platform RT).
;;   (set-listener! x y z fx fy fz) → the binaural listener pose for kami.binaural
;;                                    (HRTF ITD/ILD spatialization of audio).
;;
;; The host renders the ground (x, y) plane as world (x, 0, y) and owns the
;; camera + RT/audio executors; this file owns the *game*: spawn a player, turn
;; ray tracing on once, and each tick park the binaural listener on the player
;; (facing -z so +x is the right ear) and emit a spatialized footstep.

(def step-every 20)            ;; ticks between footsteps

(defn player []
  (nearest-tagged "player" (f32 0.0) (f32 0.0) (f32 9000000.0)))

(defn init []
  ;; one-shot: switch this frame to the ray-traced "gi" recipe.
  (rt-enable! "gi")
  (set-position! (spawn-entity "player") (f32 0.0) (f32 0.0) (f32 0.0)))

;; the binaural listener tracks the player every tick.
(defsystem listen [dt]
  (let [p (player)]
    (when (not= p -1)
      (set-listener! (get-x p) (get-y p) (get-z p)
                     (f32 0.0) (f32 0.0) (f32 -1.0)))))

;; periodic footstep, spatialized at the player's world position.
(defsystem footstep [dt]
  (when (zero? (mod (tick-n) step-every))
    (let [p (player)]
      (when (not= p -1)
        (play-sound-at "step" (get-x p) (get-y p) (get-z p))))))
