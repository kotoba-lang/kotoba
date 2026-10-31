# kami-web

> **Authority (ADR-2607102200 addendum 12)**
>
> | layer | location | role |
> |---|---|---|
> | **CLJC SSoT** | this repo `src/kotoba/web/*` | portable math / render-IR shape / document layout |
> | **Static demos** | this repo `demos/` | graph.html, play.html, vendor UI JS |
> | **WebGPU executor** | `kotoba-lang/webgpu` | `kami.webgpu` browser draw |
> | **Game host surface** | `kotoba-lang/host` | `kami.host` / input / ui / audio |
> | **Engine SDK** | `kotoba-lang/kami-engine-sdk` | ECS / scene / render-IR authoring |
>
> Nested `kami-engine/kami-web` is a **shim** pointing here. Do not add new demos under the monorepo path.


## What's ported

| Namespace | Ported from | What |
|---|---|---|
| `kotoba.web.math` | `src/math_bindings.rs` | `glam`-backed matrix/vector math (`perspective`, `invert-mat4`, `view-projection`) + bilinear heightmap sampling |
| `kotoba.web.render-ir` | `src/entries/render_ir.rs` | The `{:globals :instances}` render-IR SHAPE (ADR-0002/ADR-0039): schema predicates, default-camera derivation, per-instance model matrix, unit-cube mesh data |
| `kotoba.web.document` | `src/document.rs` | PPTX slide → 2D draw-primitive layout: EMU↔px, hex-color parsing, per-shape geometry, selection-handle placement, slide-fit |
| `kotoba.web.entries` | `src/entries/{mod,quarry_walk}.rs`, `src/lib.rs` | Legacy `run_with_*` entry catalog (freeze/migration status) + `quarry_walk`'s extracted config and pure spawn-point search |

```clojure
(require '[kotoba.web.math :as math])
(math/view-projection 0.0 5.0 10.0  0.0 0.0 0.0  (/ Math/PI 3.0) 1.7778 0.5 4000.0)

(require '[kotoba.web.render-ir :as rir])
(rir/render-ir? {:globals {:sky {:horizon [0.5 0.6 0.8] :sun-dir [0 -1 0] :sun [1 1 1]}}
                  :instances [{:pos [0 0 0] :color [1 0 0]}]})

(require '[kotoba.web.document :as doc])
(doc/render-document-layer {:width (* 10 914400.0) :height (* 7.5 914400.0)
                             :shapes [{:id "s1" :type "rect" :x 0 :y 0 :w 914400.0 :h 914400.0 :fill "#0000FF"}]}
                            1000.0 800.0)
```

## What's left unported (adapter-only)

Everything that touches `wgpu` (device/surface/pipeline/buffer setup, WGSL
shader compilation, draw calls), the DOM (`web-sys` canvas/document/event
listeners), or other Rust crates' procedural generation
(`kami-terrain`/`kami-vegetation`/`kami-atmosphere` noise/mesh/weather
sims) stays in Rust — see each namespace's docstring, and
`kotoba.web/port-manifest` for a machine-readable summary.

## License

Apache License 2.0.
