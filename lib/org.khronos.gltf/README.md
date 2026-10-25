# kotoba-lang/org-khronos-gltf

(renamed from `kotoba-lang/gltf` 2026-07-05 — reverse-domain naming for an
external-spec-name repo, khronos.org, same ADR-2607041500 rename precedent
as `org-khronos-glb`/`org-openusd`/`org-materialx`.)

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-gltf` Rust crate
(`kotoba-lang/kami-engine`, deleted in PR #82 "Remove Rust workspace from kami-engine")
as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

`kami-gltf/src/lib.rs` (161 lines) was a minimal binary glTF 2.0 (`.glb`) *exporter*:
given a `LoadedMesh` (interleaved `[pos3 norm3 uv2]` × N float vertices + u32 indices)
and a flat RGBA base color, it wrote out a self-contained, 4-byte-aligned `.glb` byte
buffer (JSON chunk + BIN chunk), with no external glTF/JSON crate dependency. Despite
the crate name suggesting a *loader*, there was no parsing/loading logic in the file —
this port is faithful to that (there was nothing else to port).

`src/gltf.cljk` ports every function 1:1 as pure CLJC data + functions:

- `u32->le-bytes` / `le-bytes->u32` / `f32->le-bytes` — little-endian byte codecs
  (the only platform-divergent piece, isolated behind `#?(:clj ... :cljs ...)`)
- `compute-bounds` — min/max position bounds over the interleaved vertex buffer
- `build-gltf-json` — the glTF JSON chunk shape (asset/scene/nodes/meshes/materials/
  accessors/bufferViews/buffers), matching the original `serde_json::json!` literal
- `->json` — minimal hand-rolled JSON serializer (no external JSON dependency, mirrors
  the original's zero-dependency stance)
- `export-glb-byte-seq` — pure, portable core: mesh + color -> vector of byte ints
- `export-glb` — wraps the above into the platform's native byte buffer (`byte[]` on
  the JVM, `js/Uint8Array` in ClojureScript)

## GLB container framing (ADR-0048 §5)

The actual binary GLB container assembly (12-byte header + JSON chunk + BIN chunk,
padding, chunk-type magic numbers) used to be hand-rolled here — but the exact same
format was *also* independently hand-rolled (read-only) in `kotoba-lang/vrm`'s
`vrm.glb`, a real duplicated-implementation risk (ADR-0048 §5,
`kotoba-lang/kami-engine`). `export-glb-byte-seq` now delegates that framing to
**`kotoba-lang/glb`** (`:local/root "../glb"`, the single canonical GLB codec both
repos depend on) via `glb/write-glb-raw` — this namespace still builds the
glTF-JSON shape and serializes it (`build-gltf-json`/`->json`) and still owns mesh
vertex/index byte encoding; `glb` only frames already-serialized bytes into chunks.
`u32->le-bytes`/`le-bytes->u32`/`string->byte-seq`/`pad-len`/`glb-magic`/
`glb-version`/`json-chunk-type`/`bin-chunk-type` are now re-exports of `glb`'s
canonical definitions (call-site compatible, no behavior change).

## Tests

`test/gltf_test.cljk` — 7 tests / 17 assertions, 0 failures:

- `glb-header-valid` — ported 1:1 from the original's `#[test] fn glb_header_valid`
- `namespace-loads` — smoke test
- `export-glb-byte-seq-migration-regression` — pins the exact byte count for a real
  mesh fixture and independently re-parses the export via `kotoba-lang/glb`'s own
  `parse-glb`, proving the ADR-0048 §5 migration to a shared GLB codec didn't
  silently change output
- plus coverage for the JSON chunk tag, bounds computation, byte round-tripping,
  and JSON serialization shapes

## Develop

```bash
kbb -M:test
```
