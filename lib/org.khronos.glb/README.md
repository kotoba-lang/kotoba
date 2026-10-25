# kotoba-lang/org-khronos-glb

(renamed from `kotoba-lang/glb` 2026-07-05 — reverse-domain naming for an
external-spec-name repo, khronos.org, same ADR-2607041500 rename precedent
as `org-khronos-gltf`/`org-openusd`/`org-materialx`.)

Zero-dep portable `.cljc` — the binary **GLB container codec** (12-byte header
+ JSON chunk + BIN chunk), factored out of `kotoba-lang/gltf` and
`kotoba-lang/vrm` per **ADR-0048 §5** (`kotoba-lang/kami-engine`,
`90-docs/adr/0048-global-format-standards-kotoba-clj-wasm-no-rust.md`,
`com-junkawasaki/root`).

## Why this repo exists

The GLB binary container format was implemented **twice**, independently, in
two different repos:

- **write-only** inside `kotoba-lang/gltf` (`export-glb-byte-seq`/`export-glb`)
- **read-only** inside `kotoba-lang/vrm` (`vrm.glb/parse-glb`)

Both are the *same* format (`.vrm` is a glTF 2.0 extension, and glTF 2.0's
binary container **is** GLB) — a real duplicated-implementation risk, not two
different formats that happen to look similar. This repo is the single
canonical implementation; `gltf` and `vrm` both depend on it via
`:local/root` instead of maintaining their own half of the same codec.

**Scope is deliberately narrow: binary container framing only** — no
glTF-JSON schema knowledge (accessors, meshes, materials, ...) and no VRM
semantics (humanoid bones, spring bones, expressions, ...) live here. Those
stay in `kotoba-lang/gltf` and `kotoba-lang/vrm` respectively.

## API

Two tiers:

### Ergonomic tier (map in/out, auto JSON encode/decode)

```clj
(require '[glb])

;; :json may be a plain map (auto-encoded) or already-serialized bytes/string
(def bytes (glb/write-glb {:json {:asset {:version "2.0"}} :bin [1 2 3 4]}))

(glb/parse-glb bytes)
;; => {:json {:asset {:version "2.0"}}, :bin [1 2 3 4]}
```

- `(write-glb {:json <map-or-bytes-or-string> :bin <byte-seq-or-nil>}) -> byte-seq`
- `(parse-glb byte-seq) -> {:json <parsed-map> :bin <byte-seq-or-nil>}`

### Raw tier (bytes in/out, no JSON encode/decode)

For callers that already have serialized JSON bytes and only want chunk
framing, or that parse the JSON chunk with a different/domain-specific JSON
layer (e.g. `kotoba-lang/vrm`'s `vrm.glb` facade, which must keep returning
raw JSON bytes for its own downstream `vrm.json`/`vrm.parse` pipeline):

- `(write-glb-raw json-bytes bin-bytes) -> byte-seq`
- `(parse-glb-raw byte-seq) -> {:json raw-json-byte-seq :bin (nilable byte-seq)}`

### Supporting infrastructure

- `glb/u32->le-bytes` / `glb/le-bytes->u32` — little-endian u32 codec
- `glb/string->byte-seq` / `glb/byte-seq->string` — UTF-8 codec
- `glb/pad-len` — 4-byte alignment padding
- `glb/glb-magic` / `glb/glb-version` / `glb/chunk-type-json` / `glb/chunk-type-bin` — format constants
- `glb.json/parse` / `glb.json/->json` — minimal, dependency-free, **generic**
  JSON parser/serializer (not glTF/VRM-specific) that the ergonomic tier uses
  internally, and that either format library's own JSON layer can also reuse
  directly

Bytes are represented as a portable byte-int sequence (`(vec bytes)`, each
element 0-255) throughout, so this namespace stays platform-neutral — JVM
callers `byte-array` the result, ClojureScript callers `js/Uint8Array.` it.

## Round-trip guarantee

`(parse-glb (write-glb x))` recovers a structurally equivalent `x` — this is
the property the test suite exists to pin down (`test/glb_test.cljk`,
`round-trip-structural` + `round-trip-bin-padding-is-a-suffix`), not just
"doesn't throw."

## Consumers

- `kotoba-lang/gltf` (`gltf.cljc`'s `export-glb-byte-seq`) calls
  `glb/write-glb-raw` with its own already-serialized glTF JSON bytes —
  glTF-JSON *shape* building stays in `gltf`, only the header/chunk framing
  moved here.
- `kotoba-lang/vrm` (`vrm/glb.cljc`) is now a thin facade: `parse-glb`/
  `write-glb` delegate to `glb/parse-glb-raw`/`glb/write-glb-raw` so the rest
  of the `vrm` repo (which calls `vrm.glb/parse-glb`/`vrm.glb/write-glb`
  directly, and expects raw JSON bytes back — it JSON-decodes separately via
  its own `vrm.json`) needed zero call-site changes.

## Develop

```bash
kbb -M:test
```
