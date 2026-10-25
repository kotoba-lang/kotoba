# org-ros

[![CI](https://github.com/kotoba-lang/org-ros/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ros/actions/workflows/ci.yml)

**ROS 2 (Robot Operating System 2) message and wire-format contracts in pure
Clojure.** A [kotoba-lang](https://github.com/kotoba-lang) `org-*` library:
the same pattern as `org-khronos-gltf` or `org-openid-oidc` — a small,
zero-dependency, portable `.cljc` implementation of an open standard, pure
data in, pure data out. `org-ros` is that pattern applied to ROS 2, and is
the message/wire-format layer underneath the `cloud-itonami` PS5 DualSense
teleop bridge and `kotoba-lang/swarm-choreo`'s governed swarm-choreography
bridge.

Models the real DDS-XTypes CDR wire format (alignment-aware, little-endian),
a handful of standard ROS 2 message shapes, the rosbridge v2 JSON-shaped
protocol, and QoS profile data. No network sockets, no device I/O, no
filesystem I/O.

## Maturity

| | |
|---|---|
| Role | contract (message/wire-format) |
| Tests | round-trip coverage for every primitive, message, and rosbridge op |
| Runtime deps | none |

## Contract

```clojure
(require '[kotoba.ros.cdr :as cdr]
         '[kotoba.ros.msgs :as msgs]
         '[kotoba.ros.rosbridge :as rb]
         '[kotoba.ros.qos :as qos])

;; CDR primitives: a buffer is a plain vector of ints 0-255, alignment-aware
(-> (cdr/writer) (cdr/write-u8 1) (cdr/write-u32 2) :bytes)
;; => [1 0 0 0 2 0 0 0]   -- 3 padding bytes so the u32 lands 4-aligned

;; A full ROS 2 message: EDN map -> CDR bytes (with encapsulation header) -> EDN map
(def twist {:linear {:x 0.5 :y 0.0 :z 0.0} :angular {:x 0.0 :y 0.0 :z 1.2}})
(= twist (msgs/decode-twist (msgs/encode-twist twist)))
;; => true

;; rosbridge v2 ops, as EDN maps (JSON/socket left to the caller)
(rb/advertise-op "/cmd_vel" rb/type-geometry-msgs-twist)
;; => {:op "advertise" :topic "/cmd_vel" :type "geometry_msgs/msg/Twist"}
(rb/publish-op "/cmd_vel" (msgs/decode-twist (msgs/encode-twist twist)))

;; QoS profile data
qos/sensor-data-qos
;; => {:reliability :best-effort :durability :volatile :history :keep-last :depth 5}
```

## What this library does — and does not — cover

This library implements **real ROS 2 message shapes, real CDR wire-format
encoding, and a rosbridge v2 JSON-shaped codec** — enough for a caller to
actually talk to a live ROS 2 system *today* via
[`rosbridge_suite`](https://github.com/RobotWebTools/rosbridge_suite) (send
`kotoba.ros.rosbridge` ops as JSON over a WebSocket, with
`kotoba.ros.msgs`-shaped EDN maps as the `:msg` payload), or to build a
native DDS transport later on top of the same message/CDR layer.

It does **not** implement native DDS-RTPS UDP discovery/pub-sub —
participant/endpoint discovery, reliability protocol, heartbeats/acknacks,
or any actual socket I/O. That is a substantial, stateful, network-facing
subsystem and is explicitly **out of scope for this version**. It is a
known, flagged follow-up (a native-DDS transport library built on top of
`kotoba.ros.cdr`/`kotoba.ros.msgs`), not a silent gap: today, a caller reaches
a live ROS 2 system either through `rosbridge_suite` (this library covers
the wire format on both sides of that bridge) or by pairing this library's
CDR/message layer with their own DDS-RTPS transport.

## Namespaces

- `kotoba.ros.cdr` — CDR (Common Data Representation) primitives: an
  alignment-aware, little-endian writer/reader over a plain vector of ints
  0-255 (deliberately not `java.nio.ByteBuffer`, to stay true `.cljc`), plus
  the 4-byte PLAIN_CDR little-endian encapsulation header every serialized
  ROS 2 message starts with.
- `kotoba.ros.msgs` — `builtin_interfaces/Time`, `std_msgs/Header`,
  `std_msgs/Bool`, `geometry_msgs/Vector3`, `geometry_msgs/Twist`,
  `geometry_msgs/TwistStamped`, `geometry_msgs/Point`,
  `geometry_msgs/Quaternion`, `geometry_msgs/Pose`,
  `geometry_msgs/PoseStamped`, `sensor_msgs/Joy` — EDN map shapes with
  `encode-*`/`decode-*` pairs that produce/consume full CDR bytes.
- `kotoba.ros.rosbridge` — pure constructor/parser functions for the
  rosbridge v2 ops a teleop bridge needs (`advertise`, `unadvertise`,
  `publish`, `subscribe`, `unsubscribe`), plus the ROS 2 `.../msg/...`
  type-string constants for this library's message shapes. Works at the EDN
  level only — no JSON parsing, no sockets.
- `kotoba.ros.qos` — QoS profile data
  (`{:reliability :durability :history :depth}`) plus the two presets a
  teleop bridge needs: `sensor-data-qos` and `default-qos`.

## Why

Every non-trivial ROS 2 integration in this codebase — starting with the
`cloud-itonami` PS5 DualSense teleop bridge — needs the *same* answer to
"what bytes does a `geometry_msgs/Twist` actually look like on the wire,
and what does a rosbridge `publish` op look like as data?" Hand-rolling CDR
alignment or the rosbridge op shapes per-caller is exactly the kind of
cross-cutting, standards-shaped problem this codebase's `org-*` libraries
exist to solve once, correctly, as pure data — so every downstream caller
(a teleop bridge, a test harness, a future native-DDS transport) shares one
audited implementation instead of three subtly different ones.

## License

Apache License 2.0.

## Test

```bash
kbb -M:lint
kbb -M:test
```
