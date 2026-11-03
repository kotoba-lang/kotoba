# swarm-choreo

[![CI](https://github.com/kotoba-lang/swarm-choreo/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/swarm-choreo/actions/workflows/ci.yml)

**Governed, precomputed multi-agent choreography — drone light shows are
the flagship use case.** A [kotoba-lang](https://github.com/kotoba-lang)
capability layered on `kotoba-lang/kami-autodrive` (vehicle dynamics),
`kotoba-lang/robotics` (the mission/action/governor contract,
ADR-2607011000), and `kotoba-lang/org-ros` (the ROS 2 wire layer,
ADR-2607052200), per ADR-2607052300.

A show is **authored in advance** by an external tool (e.g. Skybrush
Studio, or any tool emitting per-performer position/time waypoints) —
this library does not build a choreography-design UI. It ingests that
plan, validates it offline, and runs its lifecycle (arm / takeoff /
formation-change / land) through `kotoba-lang/robotics`' governor before
anything reaches hardware.

Deliberately generic across `kami-autodrive`'s vehicle classes
(`:car`/`:ship`/`:drone`/`:aircraft`) — `:drone` is the flagship use case,
but formation choreography for any class reuses the same code. No
network, no I/O, no choreography-design surface. Pure `.cljc`.

## Maturity

| | |
|---|---|
| Role | capability (show ingestion + offline validation + governed lifecycle + ROS 2 wire mapping) |
| Tests | round-trip/property coverage for every namespace |
| Runtime deps | `kami-autodrive`, `robotics`, `org-ros` (all `:local/root` siblings) |

## Why not extend `autodrive.fleet`?

`kami-autodrive`'s `autodrive.fleet` is a **reactive** per-tick
collision-avoidance simulator: each agent senses and yields to
higher-priority agents in real time. A light show is the opposite
problem — the whole timeline is authored in advance and only needs to be
validated offline and replayed on a governed schedule. `swarm-choreo`
does not modify `autodrive.fleet` (or `kami-autodrive`/`robotics`/
`org-ros` at all); it is a new, separate layer.

## Namespaces

- `kotoba.swarm-choreo.show` — the ingested plan: `waypoint` (3D position +
  yaw at a time), `performer` (a vehicle's full trajectory, auto-sorted by
  time), `show` (a full plan with an optional geofence and opaque
  `:abort-conditions`), `duration`.
- `kotoba.swarm-choreo.validate` — offline verification *before* a show is
  ever armed: whole-timeline pairwise minimum separation
  (`min-separation`/`separation-violations`, the `autodrive.fleet/
  min-separation` idea applied to a precomputed timeline), per-performer
  `speed-violations`/`accel-violations` against `autodrive.classes/
  limits`, and `geofence-violations` (a vertical-cylinder containment
  check — a **missing geofence is itself a validation failure**, not a
  silently unconstrained show). `validate` combines all four into
  `{:valid? bool :violations [...]}`.
- `kotoba.swarm-choreo.gate` — show-lifecycle actions on
  `kotoba-lang/robotics`' governor contract: `show-action` (arm/takeoff
  default to human-sign-off safety classes; formation-change/playback
  don't) and `abort-all` (bypasses the gate entirely — a stop must never
  wait on a permission check, same invariant as `teleop`'s e-stop).
- `kotoba.swarm-choreo.ros` — maps one performer's per-tick setpoint to
  `mavros/setpoint_position/local` (`geometry_msgs/msg/PoseStamped`), the
  real MAVROS topic a PX4/ArduPilot vehicle listens to for an
  offboard/guided position setpoint, via `org-ros`'s rosbridge codec.
- `kotoba.swarm-choreo.physics-check` — a stronger, slower check to run on
  segments `validate` already passed: does `kami-autodrive`'s *real*
  closed-loop `:drone` autopilot + multirotor plant actually reach a
  segment's target within its scheduled time budget (`horizontal-segment-
  feasible?`, `show-segments-feasible`), not just `validate`'s straight-
  line finite-difference approximation? `kami-autodrive`'s plant models no
  altitude channel at all, so vertical (climb/descent) rate is checked
  separately (`vertical-feasible?`) against swarm-choreo's own
  conservative assumption, not a `kami-autodrive` constant.

## Contract

```clojure
(require '[kotoba.swarm-choreo.show :as show]
         '[kotoba.swarm-choreo.validate :as validate]
         '[kotoba.swarm-choreo.gate :as gate]
         '[kotoba.swarm-choreo.ros :as sros])

(def p1 (show/performer "p1" :drone {:x 0.0 :y 0.0 :z 10.0}
                         [(show/waypoint 0.0 {:x 0.0 :y 0.0 :z 10.0} 0.0)
                          (show/waypoint 10.0 {:x 50.0 :y 0.0 :z 10.0} 0.0)]))
(def s (show/show "demo" [p1]
                   :geofence {:geofence/center-x 25.0 :geofence/center-y 0.0
                              :geofence/radius 60.0
                              :geofence/min-alt 0.0 :geofence/max-alt 120.0}))

(validate/validate s)
;; => {:valid? true :violations []}

(gate/show-action "A1" "M1" :takeoff)
;; => {:action/id "A1" ... :action/safety :high ...}   -- routes to :require-sign-off

(gate/abort-all "M1" :reason :e-stop)          ; bypasses the gate entirely

(sros/setpoint-advertise-op "uas1")
;; => {:op "advertise" :topic "/uas1/mavros/setpoint_position/local" ...}
```

## What this library does — and does not — do

Implements: show ingestion, offline pairwise-separation/speed/accel/
geofence validation, governor-gated lifecycle actions, and the
PoseStamped/MAVROS wire mapping.

Does **not** implement: a choreography-design tool (Blender plugin or
otherwise — authoring stays external), native DDS-RTPS transport or a
MAVROS/MAVLink bridge (a host process bridges `org-ros`'s rosbridge
messages to real hardware, exactly as already scoped for `teleop`), or
any integration into a specific product (`cloud-itonami-*` blueprint,
`com-etzhayyim-tazuna`, etc.) — generic capability only.

## Honest limits

Offline validation checks the *planned* timeline at a finite sampling
resolution, not reality: RTK GPS drift, wind, clock sync, and radio range
are invisible to a pure-data simulation, and two trajectories can in
principle pass closer than any sampled instant between two samples. A
real operator must still carry independent safety margins — this library
makes a show's plan checkable, not a real flight safe by itself.

`physics-check` closes part of that gap by running the real GNC stack
instead of a straight-line approximation, but it is still a horizontal-
only, single-performer, obstacle-free simulation — it does not check
inter-performer separation under real closed-loop dynamics (that stays
`validate`'s idealized-trajectory job), and it has no altitude dynamics
to check a climb rate against at all (that check is swarm-choreo's own
assumption, not `kami-autodrive`'s).

## License

Apache License 2.0.

## Test

```bash
kbb -M:lint
kbb -M:test
```
