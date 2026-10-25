# kotoba-lang/org-iso-6983

[![CI](https://github.com/kotoba-lang/org-iso-6983/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-iso-6983/actions/workflows/ci.yml)

**Renamed from `cnc` (2026-07-08):** `kotoba.cam.gcode`'s G/M-code
vocabulary (G00/G01/G02/G03/G21/G90/M03/M05/M06/M08/M09/M30, ...) is the
command set ISO 6983-1 (née RS274D/EIA RS-274, ISO-standardized 1980)
defines — the reverse-domain naming this monorepo uses for repos that
genuinely conform to a named external spec's format (same bar as
`org-iso-jpeg`/`org-iso-h264`/`org-iso-isobmff`). See ADR-2607084200.

**CNC machining (CAM) domain logic in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library:
G-code generation, toolpath (zigzag pocket / peck drill) simulation, cutting
tool library, workpiece stock definitions, and material presets.

No network, no I/O in the domain namespaces (`kotoba.cam.*`) — pure data and
functions only, `.cljc` portable across JVM / ClojureScript / SCI /
GraalVM/WASM.

## Origin

Ported from the Rust crate `kami-cam` (`kotoba-lang/kami-engine`), which was
deleted from the working tree during the Rust-engine retirement
([ADR-2607010000](../../../90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md))
**without ever being committed**. It is recoverable from git history:

```sh
cd orgs/kotoba-lang/kami-engine
git show HEAD:kami-cam/src/gcode.rs   # etc — HEAD still has the crate
```

This repo is that domain logic, ported so no information is lost.

**Naming note:** the crate is `kami-cam`, and its own `Cargo.toml`
description is unambiguous — "KAMI CAM — **C**omputer-**A**ided
**M**anufacturing: toolpath generation, G-code output, tool library, stock
definition, CNC post-processor" — so the code here is ported under the
`kotoba.cam` Clojure namespace. The GitHub repo is named `cnc` rather than
`cam` because `kotoba-lang/cam` already exists for an unrelated, seemingly
unintentional homonym: a concurrent effort (ADR-2607010930, "clj-wgsl
migration") registered that name for **camera** rigs
(follow/look-constraint/shake), also claiming restoration from a deleted
`kami-engine` Rust crate. That repo's `kami-cam` source recovery target does
not match what is actually in `kami-engine`'s git history under
`kami-cam/` (this crate — CNC machining, no camera code at all). Left
unresolved for the repo owner; not touched here per this migration's
"don't step on concurrent work" policy.

Renamed again 2026-07-08, `cnc` → `org-iso-6983` — see the note at the
top of this README and ADR-2607084200. The Clojure namespace stays
`kotoba.cam.*` (this rename is a GitHub repo name only, matching the
reverse-domain convention used for other real-spec-conforming repos in
this monorepo; it isn't a namespace rename).

## Namespaces

| Namespace | Rust source | Purpose |
|---|---|---|
| `kotoba.cam.vec3` | (`glam::DVec3`, external) | Minimal 3D vector value type + pure math (no external linalg dep) |
| `kotoba.cam.util` | (formatting internals of `gcode.rs`) | Portable fixed-point number formatting (Rust `{:.N}`/`{:0width}` equivalents) |
| `kotoba.cam.tool` | `src/tool.rs` | `Tool`, tool library (pure — `add`/`remove` return `[library' previous]`) |
| `kotoba.cam.stock` | `src/stock.rs` | `Stock`, `StockShape`, `CamMaterial` + presets |
| `kotoba.cam.toolpath` | `src/toolpath.rs` | `CamOperation`, `CamJob`, `generate-toolpath` (zigzag pocket, peck drill, single-pass raster face-mill, convex-polygon-offset contour) |
| `kotoba.cam.gcode` | `src/gcode.rs` | `generate-gcode` — segments + config → G-code text |
| `kotoba.cam` | `src/lib.rs` | Aggregator/docs namespace |

Geometry input is the minimal internal `kotoba.cam.vec3` (mirrors
`glam::DVec3`) rather than a shared CAD vector type, to avoid a circular
dependency on a CAD namespace — same rationale as the original crate.

## Usage

```clojure
(require '[kotoba.cam.tool :as tool]
         '[kotoba.cam.stock :as stock]
         '[kotoba.cam.toolpath :as toolpath]
         '[kotoba.cam.gcode :as gcode]
         '[kotoba.cam.vec3 :as vec3])

(let [[lib _] (tool/add (tool/empty-library)
                         {:id 1 :name "6mm 2-flute carbide" :tool-type :end-mill
                          :diameter 6.0 :flute-length 20.0 :overall-length 50.0
                          :flute-count 2 :corner-radius 0.0 :material :carbide
                          :coating "TiAlN"})
      s (stock/stock (stock/block 100.0 100.0 20.0) (stock/aluminum-6061))
      job (-> (toolpath/new-job s lib)
              (toolpath/add-operation
               {:op :pocket :tool-id 1 :depth 3.0 :stepover 3.0 :strategy :zigzag
                :feed-rate 800.0 :spindle-rpm 12000.0
                :pocket-min (vec3/v3 10.0 10.0 0.0)
                :pocket-max (vec3/v3 50.0 50.0 0.0)}))
      segments (toolpath/generate-toolpath job)]
  (gcode/generate-gcode segments gcode/default-config))
```

## Extracted config (EDN)

Material presets and the default G-code config are the crate's hardcoded
constant tables, now data:

- `resources/kotoba/cam/materials.edn` — density (g/cm^3) + Brinell hardness
  presets (`aluminum-6061`, `steel-1045`, `titanium-ti6al4v`, `abs-plastic`,
  `wood-oak`), ported verbatim from `CamMaterial::{aluminum_6061, ...}`.
- `resources/kotoba/cam/gcode-defaults.edn` — ported from
  `impl Default for GcodeConfig`.

`kotoba.cam.stock` / `kotoba.cam.gcode` keep a literal copy of these tables
rather than reading the resource files at namespace load — that keeps the
domain namespaces free of file IO and portable to cljs/wasm.
`test/kotoba/cam/materials_edn_test.cljk` (JVM-only, the one place allowed to
touch `clojure.java.io`) asserts the embedded literals and the `.edn` files
never drift apart.

## Tests

`test/kotoba/cam_test.cljk` ports the 5 test cases from the Rust crate's
`src/tests.rs` 1:1 (`tool-library-crud`, `gcode-header-footer-valid`,
`gcode-arc-output`, `pocket-toolpath-generates-segments`,
`material-presets`) as parity tests, plus new coverage (beyond the
original Rust scope) for `:face-mill` and `:contour`.

```sh
kbb -M:test
kbb -M:lint
```

## Intentionally unported

The Rust crate (`Cargo.toml`) declared `kami-eng-core` and
`kami-eng-render` as dependencies, but neither is actually referenced from
`gcode.rs` / `stock.rs` / `tool.rs` / `toolpath.rs` / `lib.rs` — this crate
had **no GPU/render/OS/wasm-bindgen bridge code** to begin with (confirmed
by grepping the recovered source for `kami_eng`/`wasm_bindgen`, no hits).
Everything in the crate is pure CAM domain logic and has been ported.

`:face-mill` (single-pass raster over the stock's top face, derived from
`(:stock job)` rather than a caller-specified region) and `:contour`
(offset-following a caller-supplied convex CCW polygon `:profile`,
`:side` :inside/:outside/:on-line) now generate real toolpaths — beyond
the original Rust crate's scope, which only stubbed every non-pocket/
drill op as a placeholder rapid move. `:contour` still falls back to that
same placeholder for a concave/self-intersecting profile (general polygon
offsetting needs self-intersection resolution this doesn't implement —
see `kotoba.cam.toolpath/convex-ccw?`).

Still not implemented (matches the Rust original, which only stubbed
these as placeholder rapid moves — no real geometry engine was ever wired
in):

- Real toolpath generation for `:surface-3d` (3D mesh height-field
  following) and `:turn` (2-axis polar lathe turning) — genuinely
  different algorithms/paradigms from raster facing or polygon offsetting,
  not attempted here (`PocketStrategy::Spiral`/`TrochoidalPeel` and all
  `SurfaceStrategy` variants are likewise unimplemented placeholders in the
  original).
- Any renderer/viewport integration (the original crate had none — toolpath
  visualization lived in `kami-eng-render`, a separate crate not part of
  `kami-cam`).

## Why

Toolpath and G-code generation is safety-relevant (a wrong feed rate or a
missing retract can crash a spindle into stock). Keeping it pure data +
pure functions makes it independently testable and auditable without a
running machine or a GPU — CAM output is exactly the kind of governed
`書込/作動` artifact this repo's actor pattern brings a `Governor` in front
of before it ever reaches a controller.

## License

Apache License 2.0.
