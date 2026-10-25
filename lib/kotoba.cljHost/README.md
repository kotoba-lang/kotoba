# clj-host

Pure `.cljc` decoder for the KAMI columnar render-IR frame format — the
clj-authored replacement for the retired Rust crate `kami-clj-host`
(`kami-engine/kami-clj-host`, deleted from the working tree, uncommitted,
as part of the clj-wgsl migration, ADR-2607010930 Phase 4).

`kami.ipc/pack` (kami-engine-sdk-clj) emits a little-endian columnar
buffer that a host renderer decodes into a camera + per-draw instance
matrices. This repo owns the decode side of that contract as portable
`.cljc`: `java.nio.ByteBuffer` on JVM, `js/DataView` on ClojureScript, via
`#?(:clj :cljs)` reader conditionals — pure, no network/IO beyond
byte-buffer parsing, no GPU dependency.

## Binary format

Little-endian throughout. Two layout versions share the same frame/column
header shape; only the column *count and pairing* differ.

```text
[Frame header        16B]  magic 'KAMI' u32 | version u16 | ncols u16 |
                            frame_n u32 | pad u32
[Column header  16B x n]   dtype u8 | stride u8 | pad u16 | len u32 |
                            offset u32 | pad u32
[payload, 16B-aligned]     raw element bytes per column at its `offset`
```

- `magic` = `0x494D414B` (ASCII `"KAMI"` read little-endian).
- `version` = `1` (camera + one model-mat4 column per draw) or `2`
  (camera + a `[model mat4, tint f16x4]` column pair per draw).
- Column 0 is always the camera: 2 mat4s = `[view, proj]`.
- Columns 1..n are per-draw instance data, in the same order as the
  draw-table that travels alongside as JSON meta (not part of this
  binary buffer).
- Every column payload offset is 16-byte aligned (columns DMA into GPU
  buffers without realignment).

Dtype tags (element size in bytes): `f32`=0 (4B), `f16`=1 (2B), `u32`=2
(4B), `u16`=3 (2B), `u8`=4 (1B), `i16`=5 (2B), `mat4`=6 (64B), `quat`=7
(8B). An unknown tag is refused rather than silently dropped (a
producer/consumer version skew must be loud).

### Fixtures

`test/resources/fixtures/frame.bin` (v1, 304B) and `frame_v2.bin` (v2,
336B) are the exact bytes emitted by `kami.ipc/pack` for the
deterministic fixture scene (`kami-engine-sdk-clj` `dev/gen_fixture.clj`):
a camera at `z=+5` and two trees at `x=+-2`. `frame_v2.bin` is the same
scene packed with `(ipc/pack frame {:tint? true})`. These are the same
fixtures the original Rust crate's `#[cfg(test)]` module asserted against
— the cross-language contract anchor, carried over byte-for-byte. Tests
decode them directly and assert the expected decoded values (camera
translation, instance positions, tint) for parity with the retired Rust
decoder.

## Usage

```clojure
(require '[kotoba.clj-host.frame :as frame])

(let [{:keys [ok? value error data]} (frame/decode buf)]
  (if ok?
    (let [[view proj] (frame/camera buf value)]
      (doseq [[model tint] (frame/draws value)]
        (frame/mat4s buf model)              ; => vector of 16-float column-major mat4s
        (when tint (frame/f16x4s buf tint)))) ; => vector of [r g b a] (v2 only)
    (println error data)))
```

`buf` is a JVM `byte-array` on `:clj`, a `js/Uint8Array` on `:cljs`.
`decode` never throws on malformed input — every failure mode returns
`{:ok? false :error <keyword> :data {...}}` (`:too-short`, `:bad-magic`,
`:bad-version`, `:unknown-dtype`, `:column-out-of-bounds`), mirroring the
Rust `DecodeError` enum's variants.

## Namespaces

- `kotoba.clj-host` — module docstring / disposition notes.
- `kotoba.clj-host.frame` — the decoder (`decode`, `camera`,
  `draw-instances`, `draws`, `mat4s`, `f16x4s`, `f16->f32`,
  `element-size`, plus the `magic`/`version`/`dtype-*` constants).

## What was not ported

The Rust crate's `host` module (`host.rs`, `#[cfg(feature = "host")]`) —
a `wasm-bindgen` + `wgpu` browser GPU driver (`register_mesh` /
`register_material` / `register_shader` / `submit_frame`, WGSL pipeline
construction, depth/camera/material buffer management) — is **not**
ported. It is GPU orchestration bound to wgpu/WebGPU APIs that have no
meaningful `.cljc` equivalent (no portable Clojure WebGPU binding exists
today); only the pure, GPU-free decode logic (`frame.rs`) is domain logic
in the clj-wgsl migration's sense. Likewise the crate's browser smoke-test
demo (`demo/app.js`, `demo/index.html` — a real-WebGPU rendering proof
using precomputed clj-emitted fixtures) is not ported for the same
reason. If a clj/cljs GPU host is needed later, it belongs in a
kotoba-lang WebGPU-binding repo, downstream of this decoder, not in it.

## Run

```sh
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0. See `LICENSE`.
