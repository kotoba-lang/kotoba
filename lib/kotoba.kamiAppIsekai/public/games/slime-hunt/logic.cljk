;; スライムハント (Slime Hunt) — real-time dodge/collect arena, guest logic.
;; WASM-compiled via kotoba.engine-clj (same technique as gftdcojp/network-isekai's "drive"
;; game — see that repo's public/games/gftd/drive/logic.cljc, which this follows almost
;; verbatim in SHAPE): fixed-coordinate entities, defsystems reading key-pressed?/
;; nearest-tagged, and drive's EXACT win/lose mechanic — 3 "life" markers; a "picked" marker
;; per pickup; the harness's generic tag-count convention fires game-over at 0 "player" and
;; victory at scene :flow :victory :when-picked "picked" markers.
;;
;; f32 comparisons are deliberately AVOIDED in guest code here (only `=`/`not=` on i64
;; ids/counts/atom-vals) — matching drive's own practice exactly: every distance/geometry
;; decision goes through a HOST primitive (`nearest-tagged` for proximity, `move-toward!` for
;; AI seek velocity) which does its float math host-side (kami.host, ClojureScript), never in
;; the guest sandbox.

(def zero            (f32 0.0))
(def player-run      (f32 300.0))   ;; kami.isekai.status/compute-stats-derived (see scene.edn)
(def neg-player-run  (f32 -300.0))
(def slime-speed     (f32 90.0))    ;; deliberately slower than the player — dodgeable
(def far             (f32 999000.0))  ;; HUD/off-map marker parking spot (counted, never drawn)

(def pickup-range    (f32 90.0))
(def hit-range        (f32 90.0))
(def wake-range      (f32 300.0))   ;; a slime only gives chase once the player is this close
(def invuln-ticks 45)   ;; ~0.75s grace after a hit @60fps — plain int, defatom domain only

;; ---- arena layout at FIXED coordinates (no spawn-ahead maths) ----
;; 8 orbs on a r=450 ring (45° apart); 3 slimes on a r=700 ring (120° apart, angle-offset from
;; every orb so a player who sticks to the orb ring stays outside wake-range on a clean lap —
;; straying toward a slime (or lingering near the one orb that happens to sit inside its wake
;; bubble) is what wakes it. Coordinates are precomputed cos/sin*radius, not guest-side trig.
(def start-x (f32 0.0)) (def start-y (f32 0.0))

(def o0x (f32 450.0))    (def o0y (f32 0.0))
(def o1x (f32 318.2))    (def o1y (f32 318.2))
(def o2x (f32 0.0))      (def o2y (f32 450.0))
(def o3x (f32 -318.2))   (def o3y (f32 318.2))
(def o4x (f32 -450.0))   (def o4y (f32 0.0))
(def o5x (f32 -318.2))   (def o5y (f32 -318.2))
(def o6x (f32 0.0))      (def o6y (f32 -450.0))
(def o7x (f32 318.2))    (def o7y (f32 -318.2))

(def s0x (f32 606.2))    (def s0y (f32 350.0))    ;; slime-green @ 30°, r=700
(def s1x (f32 -606.2))   (def s1y (f32 350.0))    ;; slime-fire  @ 150°, r=700
(def s2x (f32 0.0))      (def s2y (f32 -700.0))   ;; slime-ice   @ 270°, r=700

(defatom invuln 0)   ;; ticks remaining of post-hit invulnerability (private cooldown)

(defn player [] (nearest-tagged "player" zero zero far))

(defn at! [tag x y] (set-position! (spawn-entity tag) x y zero))
(defn mark! [tag] (set-position! (spawn-entity tag) far far zero))

(defn init []
  (at! "player" start-x start-y)
  (mark! "life") (mark! "life") (mark! "life")
  (at! "orb" o0x o0y) (at! "orb" o1x o1y) (at! "orb" o2x o2y) (at! "orb" o3x o3y)
  (at! "orb" o4x o4y) (at! "orb" o5x o5y) (at! "orb" o6x o6y) (at! "orb" o7x o7y)
  (at! "slime-green" s0x s0y)
  (at! "slime-fire"  s1x s1y)
  (at! "slime-ice"   s2x s2y))

;; MOVE — the key picks the direction, a precomputed f32 constant the speed (the guest can't
;; multiply f32 by an analog axis), same kami pattern drive's own drive-tick uses.
(defsystem move [dt]
  (let [p (player)]
    (when (not= p -1)
      (let [vx (cond (= 1 (key-pressed? "right")) player-run
                     (= 1 (key-pressed? "left"))   neg-player-run
                     :else zero)
            vy (cond (= 1 (key-pressed? "up"))     player-run
                     (= 1 (key-pressed? "down"))   neg-player-run
                     :else zero)]
        (set-velocity! p vx vy zero)))))

;; PICKUPS — touch a kotodama orb: despawn it, +1 "picked" (drive's exact victory mechanic —
;; the harness fires victory at scene :flow :victory :when-picked).
(defsystem pickups [dt]
  (doseq-entities [o "orb"]
    (let [near (nearest-tagged "player" (get-x o) (get-y o) pickup-range)]
      (when (not= near -1)
        (despawn-entity o)
        (mark! "picked")))))

;; INVULN — the post-hit grace window counts down every tick.
(defsystem invuln-tick [dt]
  (when (> (atom-val invuln) 0)
    (set-atom! invuln (- (atom-val invuln) 1))))

;; ENEMY AI + DAMAGE — one defsystem per slime variant (kami.host's ECS keys one tag per
;; entity, so nearest-tagged/doseq-entities address a single tag at a time — three near-
;; identical copies, not a loop over a tag list). Each tick, per slime: wake (host-computed
;; nearest-tagged "player" from THIS slime's own position, within wake-range) and chase
;; (host-computed move-toward!), else stay put — a dozing slime you can walk past outside
;; wake-range, a hunting one once you're close. Separately: if not on cooldown and the player
;; ends up within hit-range of this tag, take a "life" (drive's exact mechanic), start the
;; cooldown, and knock the player back to the spawn point (breathing room + prevents one
;; lingering overlap from draining every life in a single tick — the same role drive's
;; despawn-the-cone-on-hit plays there, adapted for enemies that persist).
(defsystem slime-green-ai [dt]
  (doseq-entities [s "slime-green"]
    (let [near (nearest-tagged "player" (get-x s) (get-y s) wake-range)]
      (if (not= near -1)
        (move-toward! s near slime-speed)
        (set-velocity! s zero zero zero))))
  (when (= 0 (atom-val invuln))
    (let [p (player)]
      (when (not= p -1)
        (let [hit (nearest-tagged "slime-green" (get-x p) (get-y p) hit-range)]
          (when (not= hit -1)
            (let [lf (nearest-tagged "life" far far far)]
              (when (not= lf -1) (despawn-entity lf)))
            (set-atom! invuln invuln-ticks)
            (set-position! p start-x start-y zero)
            (set-velocity! p zero zero zero)
            (when (= 0 (count-tagged "life")) (despawn-entity p))))))))

(defsystem slime-fire-ai [dt]
  (doseq-entities [s "slime-fire"]
    (let [near (nearest-tagged "player" (get-x s) (get-y s) wake-range)]
      (if (not= near -1)
        (move-toward! s near slime-speed)
        (set-velocity! s zero zero zero))))
  (when (= 0 (atom-val invuln))
    (let [p (player)]
      (when (not= p -1)
        (let [hit (nearest-tagged "slime-fire" (get-x p) (get-y p) hit-range)]
          (when (not= hit -1)
            (let [lf (nearest-tagged "life" far far far)]
              (when (not= lf -1) (despawn-entity lf)))
            (set-atom! invuln invuln-ticks)
            (set-position! p start-x start-y zero)
            (set-velocity! p zero zero zero)
            (when (= 0 (count-tagged "life")) (despawn-entity p))))))))

(defsystem slime-ice-ai [dt]
  (doseq-entities [s "slime-ice"]
    (let [near (nearest-tagged "player" (get-x s) (get-y s) wake-range)]
      (if (not= near -1)
        (move-toward! s near slime-speed)
        (set-velocity! s zero zero zero))))
  (when (= 0 (atom-val invuln))
    (let [p (player)]
      (when (not= p -1)
        (let [hit (nearest-tagged "slime-ice" (get-x p) (get-y p) hit-range)]
          (when (not= hit -1)
            (let [lf (nearest-tagged "life" far far far)]
              (when (not= lf -1) (despawn-entity lf)))
            (set-atom! invuln invuln-ticks)
            (set-position! p start-x start-y zero)
            (set-velocity! p zero zero zero)
            (when (= 0 (count-tagged "life")) (despawn-entity p))))))))
