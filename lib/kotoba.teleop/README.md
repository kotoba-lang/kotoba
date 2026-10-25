# kotoba-teleop

[![CI](https://github.com/kotoba-lang/teleop/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/teleop/actions/workflows/ci.yml)

**The governed bridge between a game-controller input device and a
robot's safety-gated actuation contract, in pure Clojure.** The third of
a 3-repo design: [`kotoba-lang/robotics`](https://github.com/kotoba-lang/robotics)
(the generic mission/action/governor contract every `cloud-itonami-*`
open business depends on) and
[`kotoba-lang/com-sony-dualsense`](https://github.com/kotoba-lang/com-sony-dualsense)
(pure HID decode for the Sony DualSense controller) are the two sibling
libraries this one composes; `kotoba-lang/org-ros` supplies the
ROS 2/rosbridge shapes a teleop bridge needs to talk to a live robot.

This library is **policy and mapping only**: it decides *what to propose*
(a `:move` action shaped from controller input) and *when to stop*
(deadman release, e-stop chord) — it never drives motors and never opens
a socket or reads a device itself. A host loop is responsible for both:
reading the physical controller (e.g. via `hid4java`, handing raw report
bytes to `kotoba.dualsense.input`) and opening the rosbridge/DDS
transport (handing `kotoba.teleop.ros`'s ops and `kotoba.ros.msgs`'
encoded bytes to an actual WebSocket). No network, no I/O here. Portable
`.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | green |
| Device I/O | none (host loop's responsibility) |
| Network I/O | none (host loop's responsibility) |
| Controllers supported | Sony DualSense (`kotoba.teleop.dualsense`) |

## Contract

```clojure
(require '[kotoba.robotics :as rob]
         '[kotoba.teleop :as teleop]
         '[kotoba.teleop.dualsense :as ds]
         '[kotoba.teleop.governor :as gov]
         '[kotoba.teleop.ros :as tros]
         '[kotoba.dualsense.input :as input]
         '[kotoba.ros.msgs :as msgs])

;; 1. host loop reads a raw HID report and decodes it (device I/O lives
;;    entirely in the host loop + kotoba.dualsense.input)
(def decoded (input/decode-usb-report raw-report-bytes))

;; 2. this library maps it to the generic, controller-agnostic axis-state
(def axis-state (ds/decoded->axis-state decoded))

;; 3. one pure fold per input frame: emits a move-action or a safety-stop
(def state0 (teleop/initial-state "M1" :speed-mode :normal))
(def result (teleop/step state0 axis-state 0.016))
(:emit result)     ; => [{:action/kind :move :action/safety :medium ...}]

;; 4. the governor/operator gates every proposed action -- never this library
(rob/gate (first (:emit result)) #{:none :low :medium})
;; => {:gate/decision :permit ...}

;; 5. turbo mode always requires human sign-off, even if :high is allowed
(def turbo-result (teleop/step (teleop/initial-state "M1" :speed-mode :turbo) axis-state 0.016))
(rob/gate (first (:emit turbo-result)) #{:high})
;; => {:gate/decision :require-sign-off ...}   ;; never :permit

;; 6. host loop turns a move-action's twist into wire bytes + a rosbridge op
(def twist (get-in (first (:emit result)) [:action/params :twist]))
(msgs/encode-twist twist)             ; => CDR byte vector (host sends over its socket)
(tros/cmd-vel-publish-op twist)       ; => {:op "publish" :topic "/cmd_vel" :msg twist}

;; teleop-specific mission/action helpers (mirrors kotoba.giemon.governor)
(gov/teleop-mission "M1" "robot-1" "warehouse patrol")
(gov/teleop-action "A1" "M1" :move :speed-mode :crawl)   ; :action/safety :low
```

## Why turbo mode requires sign-off, and why deadman/e-stop bypass the gate

Two safety decisions are the interesting part of this design:

- **Turbo mode is deliberately gated behind human sign-off.**
  `kotoba.teleop/speed-modes`' `:turbo` entry carries `:action/safety
  :high`. `kotoba.robotics/gate` always routes `:high` (and
  `:safety-critical`) actions to `:require-sign-off`, *even when* `:high`
  is in the operator's allowed safety-class set — sign-off is a separate
  human-in-the-loop stage from the gate's allow/deny decision. So a
  turbo-mode move action can never reach hardware without a human
  approving it first, no matter how permissive the deployment's allowed
  set is. This is the actual safety mechanism for turbo mode (2x
  linear/angular rate), not an oversight.

- **The deadman switch and e-stop chord bypass the gate entirely.** A
  stop must never wait on a permission check — by the time an operator
  needs one, asking a governor for permission first is exactly the
  failure mode a safety-stop exists to avoid. `kotoba.teleop/step`
  therefore builds both stops with `kotoba.robotics/safety-stop` directly
  and emits them unconditionally:
  - Releasing the **deadman** (default: `:l2` held past `0.5` — a
    hold-to-drive control, default chord unrelated) produces a stop with
    reason **`:operator`**, not `:e-stop`: the operator didn't hit an
    emergency control, they simply stopped asserting "drive". Modeling
    this as a distinct, ordinary, expected stop (rather than an
    emergency one) keeps audit logs honest about what actually happened.
  - Holding the **e-stop chord** (default `#{:ps :options}`, a
    deliberate two-button combo unlikely to be hit by accident) produces
    a stop with reason **`:e-stop`**, taking priority over every other
    check.

  This mirrors the design of `com-etzhayyim-tazuna`'s independently-built
  teleop-safety reasoner
  (`orgs/etzhayyim/com-etzhayyim-tazuna/methods/teleop_safety.cljc`:
  `ALWAYS-PERMITTED #{"halt" "estop" "handback"}`) — halt/estop-class
  commands are never gated or signed there either, for the same reason.
  tazuna is cited here as design rationale only; this library does not
  depend on or modify it.

## Controller-agnostic core

`kotoba.teleop` works over a generic axis-state shape:

```clojure
{:left-stick [<x -1..1> <y -1..1>] :right-stick [<x -1..1> <y -1..1>]
 :l2 <0..1> :r2 <0..1> :buttons #{...keywords...} :dpad <keyword>}
```

`kotoba.teleop.dualsense/decoded->axis-state` is the *only* namespace
that knows about a specific controller brand (Sony DualSense, via
`kotoba.dualsense.input`). A future Xbox/generic-HID adapter would add
its own `decoded->axis-state` analogue and reuse `kotoba.teleop`
unchanged.

## `->twist` mapping

`kotoba.teleop/->twist` follows the standard differential-drive teleop
convention: the left stick's Y axis drives `linear.x` (forward/back), the
right stick's X axis drives `angular.z` (turn rate), both scaled by the
active speed mode; `linear.y`/`linear.z`/`angular.x`/`angular.y` stay
`0.0` since a differential-drive base can't strafe or fly.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
kbb -M:lint
```

CI checks out this repo plus its 3 direct sibling `kotoba-lang`
dependencies (`robotics`, `org-ros`, `com-sony-dualsense`) *and* the 2
further `:local/root` deps `robotics` itself needs (`html`, `css`, for
its operator-console/export namespaces) into sibling directories so the
whole `:local/root` chain resolves — see `.github/workflows/ci.yml`.
