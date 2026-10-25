# kotoba-pbrt (kami-rtx)

[![CI](https://github.com/kotoba-lang/pbrt/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/pbrt/actions/workflows/ci.yml)

Mitsuba 3 WebGPU backend bind — RTX Renderer API-compat layer. Safety-gated
`.kotoba` contract derived from the Rust `kami-pbrt` crate
(`kotoba-lang/kami-engine`), per ADR-2607010930 (clj-wgsl migration Phase 4).

**Status**: R1.0 path reservation (ADR-2605261800). No runtime code — in
either the original Rust crate or this port.

## Port scope

The Rust source (`kami-pbrt/src/lib.rs`) exports only status constants; there
was no domain logic to port. This library preserves those values through typed
getter functions compiled for restricted JavaScript and Wasm:

```clojure
(defn adr-value [] :string "ADR-2605261800")
(defn phase-value [] :string "R1.0-path-reservation")
```

## Unported (out of scope)

Nothing was skipped — the source crate had no runtime logic (renderer,
Dr.Jit bridge, wasm-bindgen surface) to port. When R1.2 (Mitsuba 3 Dr.Jit ->
WebGPU compute pipeline) lands upstream, the pure-data portions of that
integration (scene description, pipeline config) belong here; anything
GPU-bound (wgpu pipeline/device code) stays out per this migration's
kami-engine retirement policy (ADR-2607010930).

## Scope (R1.2 deliverable, per original ADR)

- Mitsuba 3 Dr.Jit → WebGPU compute pipeline (via upstream PR)
- Differentiable rendering (forward + reverse mode)
- Cornell box reference scene PSNR ≥ 35dB vs CUDA reference

## Non-goals

- Local Mitsuba 3 fork maintenance (ADR §D3)
- NVIDIA RTX SDK binary linking (ADR §N3)

## License

Apache License 2.0.
