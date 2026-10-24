# kotoba-web-modelb

[![CI](https://github.com/kotoba-lang/web-modelb/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/web-modelb/actions/workflows/ci.yml)

Pure-Clojure (`.cljc`) port of the portable parts of
[kotoba-lang/kami-engine](https://github.com/kotoba-lang/kami-engine)'s
`kami-web-modelb` Rust crate — part of ADR-2607010930 (clj-wgsl migration
Phase 4), which retires the Rust `kami-engine` workspace in favor of pure
Clojure "kotoba" authority repos.

`kami-web-modelb` ("Model B — brain-on-host") is documented as *"the VRM
dance running in-browser as a compiled-CLJ game (native LiveShow +
wasmi-driven dance logic.clj, wasm-in-wasm)"*. It is a **GPU bridge, not a
logic crate**: it composes a native `kami-live` LiveShow with a
wasmi-compiled `dance/logic.clj`, ticks both per frame, rasterises the
resulting render-IR on the CPU (`kami-webgpu-rs::render`), and blits the
pixels to a `<canvas>` via a minimal `wgpu` fullscreen-quad pipeline.
Almost none of that is portable: the compiled-CLJ execution runs *inside*
`kami-script-runtime`'s wasmi WASM-in-WASM sandbox (a Rust-only
capability), and the GPU blit is pure `wgpu` adapter glue.

## What's ported

| Namespace | Ported from | What |
|---|---|---|
| `kotoba.web-modelb.config` | `src/lib.rs`, `examples/render_png.rs` | Fixed dance-viewer camera preset, headless-verification canvas size, shipped-asset path references, `dt` (seconds) → `dt_ms` (integer ms) frame-timing conversion |

```clojure
(require '[kotoba.web-modelb.config :as config])
config/dance-camera        ;=> {:eye [0.0 1.5 4.2] :target [0.0 0.95 0.0]}
(config/dt->ms 0.016)      ;=> 16
```

The render-IR `WebDance::tick` returns is the **same** `{:globals
:instances}` shape [`kotoba-lang/kami-web`](https://github.com/kotoba-lang/kami-web)'s
`kotoba.web.render-ir` ports — see that repo for the schema/camera-math.

## What's left unported (adapter-only)

- `gpu.rs` in its entirety — `wgpu` surface + fullscreen-quad blit
  pipeline + WGSL shader.
- `WebDanceGpu`/`WebDance` — `wasm-bindgen` structs wrapping
  `kami_live::scene::DanceScene` + `KamiScriptRuntime` (wasmi
  WASM-in-WASM) + `hecs::World`.
- `examples/render_png.rs` — a host-only headless PNG verification tool,
  not portable logic.

See `kotoba.web-modelb/port-manifest` for a machine-readable summary.

## License

Apache License 2.0.
