# kotoba-lang/device

[![CI](https://github.com/kotoba-lang/device/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/device/actions/workflows/ci.yml)

**Device capability interfaces** (bluetooth / wifi / display / geolocation /
camera / motion / audio-io / ble-scan / wifi-info) as **EDN + a discover
protocol**, with **host-injected drivers**. The
core kotoba principle — a component touches only what it was granted — applies
*especially* to hardware. `device` does **not** wrap OS APIs; it defines device
surfaces as `wit` capability tokens and a `discover`/`describe` protocol, so
`aiueos`'s `:aiueos/device` + `aiueos:host` gate can grant or deny each surface.
Consumes [`wit`](https://github.com/kotoba-lang/wit) (capability tokens) +
[`coll`](https://github.com/kotoba-lang/coll) (shaping). No third-party deps;
`.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why (not a finder)

deno/rust/go/ts have `deno.bluetooth` / `bluetooth` crates / `bluetooth`
packages — direct OS wrappers. kotoba cannot: a capability-confined cell must
not touch hardware unless granted. So `device` is a **capability layer**, not a
finder: each device surface (`device:bluetooth`, `device:wifi`,
`device:display`, `device:geolocation`, `device:camera`, `device:motion`,
`device:audio-io`, `device:ble-scan`, `device:wifi-info`) is a `wit` capability
token; `discover` enumerates granted surfaces; `describe` reports a surface's
schema; the **driver** (the actual BT/Wi-Fi/monitor call) is host-injected
behind the `IDevice` protocol. `aiueos`'s broker decides grants/denials — this
lib is the vocabulary it reasons over.

## Current surface

`kotoba.lang.device`:

- `surfaces` — the canonical device-surface registry (bluetooth/wifi/display/
  geolocation/camera/motion/audio-io/ble-scan/wifi-info) as `wit` capability
  tokens with effects
- `discover` — given a `wit` policy, enumerate granted device surfaces
- `describe` — return a surface's schema (methods, params, effects)
- `IDevice` protocol — host-injected driver (`scan`/`read`/`write`/`subscribe`)
- `mock-device` — in-memory driver for tests / OSS standalone
- `make-device-manager` — policy + driver registry → gated device access
- `sensing-host-driver-refs` / `sensing-host-driver-ref` — EDN-only pointers
  (no code dependency) from `motion`/`audio-io`/`ble-scan`/`wifi-info` to the
  kotoba-core-contracts capability id (234–237) and
  [`kotoba.sensing-host`](https://github.com/kotoba-lang/kotoba/blob/main/src/kotoba/sensing_host.cljc)
  fn a caller should use as that surface's `IDevice` driver
  (ADR-2607140600 Phase 3a — the indoor floorplan-lab's device-capability
  bridge)

## Install

```clojure
io.github.kotoba-lang/device {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.device :as dev]
         '[kotoba.lang.wit :as wit])

(let [pol (-> (wit/policy) (wit/grant "device:bluetooth") (wit/grant "device:geolocation"))
      mgr (dev/make-device-manager pol {:bluetooth (dev/mock-device)} {}) ]
  (dev/discover mgr)            ;=> (:bluetooth :geolocation)
  (dev/call mgr :bluetooth :scan {}))  ;=> capability-gated scan result
```

## Verify

```sh
kbb -M:test
```
