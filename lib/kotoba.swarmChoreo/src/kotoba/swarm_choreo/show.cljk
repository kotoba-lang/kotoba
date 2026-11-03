(ns kotoba.swarm-choreo.show
  "The ingested show plan: a precomputed, per-performer 3D trajectory.

  A show is *authored in advance* by an external tool (e.g. Skybrush
  Studio, or any tool that emits per-performer position/time waypoints) —
  this namespace deliberately does not build a choreography-design UI (no
  Blender-equivalent). It only models the plan once it exists, so
  `kotoba.swarm-choreo.validate` can check it offline and
  `kotoba.swarm-choreo.gate` can run its lifecycle under
  `kotoba-lang/robotics`' governor contract (ADR-2607011000).

  This is deliberately generic across `kotoba-lang/kami-autodrive`'s
  vehicle classes (`autodrive.classes/vehicle-classes`) — `:drone` is the
  flagship use case (a light show), but `:car`/`:ship`/`:aircraft`
  formation choreography reuse the same shape unchanged.

  Positions are full 3D (`{:x :y :z}`, metres) — unlike
  `autodrive.types/pose2`, which is ground-projected (no altitude), a show
  performer's altitude is exactly the point of a choreography. `yaw` keeps
  `autodrive.types`' planar heading convention (radians, CCW from +x); a
  show does not model roll/pitch (see `kotoba.swarm-choreo.ros`'s
  yaw-only-orientation note).

  Pure data in, pure data out: no network, no I/O, no clock. Portable
  `.cljc`.")

;; ---------------------------------------------------------------------------
;; Waypoint — one scheduled 3D setpoint
;; ---------------------------------------------------------------------------

(defn waypoint
  "One scheduled setpoint on a performer's trajectory: `t` seconds since
  show start, `pos` a `{:x :y :z}` map (metres), `yaw` radians (CCW from
  +x)."
  [t pos yaw]
  {:waypoint/t t :waypoint/pos pos :waypoint/yaw yaw})

;; ---------------------------------------------------------------------------
;; Performer — one vehicle's full trajectory
;; ---------------------------------------------------------------------------

(defn performer
  "One show performer: `id`, vehicle `class` (a
  `autodrive.classes/vehicle-classes` keyword), a `home` position (a
  `{:x :y :z}` map — where the vehicle starts/returns to), and
  `trajectory` — a seq of `waypoint`s, stored sorted ascending by
  `:waypoint/t` regardless of input order."
  [id class home trajectory]
  {:performer/id id
   :performer/class class
   :performer/home home
   :performer/trajectory (vec (sort-by :waypoint/t trajectory))})

;; ---------------------------------------------------------------------------
;; Show — the full plan
;; ---------------------------------------------------------------------------

(defn show
  "A full show: `id`, a seq of `performer`s, an optional `:geofence` (a
  vertical-cylinder shape — see `kotoba.swarm-choreo.validate`) and
  `:abort-conditions` (host-defined EDN, opaque to this library — e.g.
  wind/battery thresholds a real operator checks before arming)."
  [id performers & {:keys [geofence abort-conditions]}]
  {:show/id id
   :show/performers (vec performers)
   :show/geofence geofence
   :show/abort-conditions abort-conditions})

(defn duration
  "The show's total duration: the latest waypoint time across every
  performer, or `0.0` for a show with no waypoints."
  [s]
  (reduce max 0.0
          (for [p (:show/performers s)
                w (:performer/trajectory p)]
            (:waypoint/t w))))
