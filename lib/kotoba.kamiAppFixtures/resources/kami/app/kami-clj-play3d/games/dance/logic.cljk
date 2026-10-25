;; KAMI VRM Dance — gameplay glue in the kami-clj subset.
;;
;; The *choreography* is data, not code: `scene.edn` → `kami_live::scene::DanceScene`
;; → a `LiveShow` the host ticks each frame (beat grid + setlist + performer pose),
;; binding the VRM avatar (kami-vrm / run_embed_vrm) to the `:dance/avatar` entity.
;; So this guest owns only the *interactive* bits: the performer entity the host
;; attaches the rig to, plus an audience ring whose members the host renders and
;; (optionally) makes cheer on drops. Guest arithmetic is integer-only → absolute
;; f32 constants. Ground is the (x, y) plane; the host renders world (x, 0, y).

(def fans       16)            ;; audience ring size
(def ring       (f32 600.0))   ;; ring radius around the stage (ground units)

;; the performer the host binds the VRM rig + LiveShow pose to.
(defn performer []
  (nearest-tagged "performer" (f32 0.0) (f32 0.0) (f32 9000000.0)))

(defn init []
  ;; centre-stage performer at the origin (matches :dance/avatar :home).
  (set-position! (spawn-entity "performer") (f32 0.0) (f32 0.0) (f32 0.0)))

;; fill the audience ring on the opening bars, one fan per spawn tick.
(defsystem seat-audience [dt]
  (when (< (count-tagged "fan") fans)
    (when (zero? (mod (tick-n) 6))
      (let [r (rand-int 4)
            e (spawn-entity "fan")]
        (cond
          (= r 0) (set-position! e ring          (f32 0.0)   (f32 0.0))
          (= r 1) (set-position! e (f32 -600.0)   (f32 0.0)   (f32 0.0))
          (= r 2) (set-position! e (f32 0.0)      ring        (f32 0.0))
          :else   (set-position! e (f32 0.0)      (f32 -600.0)(f32 0.0)))))))

;; the camera target follows the performer; the host owns the orbit + dance pose
;; (LiveShow.snapshot().performer_pose) and the beat-synced lighting / crowd.
(defsystem follow-performer [dt]
  (let [p (performer)]
    (when (not= p -1)
      (set-velocity! p (f32 0.0) (f32 0.0) (f32 0.0)))))
