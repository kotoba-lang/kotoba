# kami-engine-sdk-clj — KAMI Engine Clojure SDK (clj + Datomic + WebGPU)

> **One line.** Author KAMI scenes, ECS, and render pipelines in **Clojure /
> ClojureScript** with **Datomic** as the source of truth; the GPU work stays on
> the proven **`kami-render` (Rust / wgpu)** backend, reached over a small
> **render-IR** contract. clj is the brain, Rust is the GPU arm.

Status: **design + working core + GPU bridge** (2026-06-13). Verified slices:

- **clj contract layer** — scene → ECS → render-IR → KAMI columnar packing, WGSL
  emission, matrix math, sim/gpu orchestration via a mock backend. **16 tests /
  61 assertions, all green** (§12).
- **Datomic two-layer** — full round-trip against a *real datalevin store*
  (connect → tx → snapshot → ECS → render-IR → pack → commit, with ref resolution
  and persistence): `kbb -M:roundtrip` (`dev/roundtrip.cljk`).
- **clj ↔ Rust GPU bridge** — the Rust host `../kami-clj-host` decodes the *exact
  bytes* `kami.ipc/pack` emits (cross-language fixture `frame.bin`): **4 Rust
  tests green** (`cargo test -p kami-clj-host`). Its wasm-bindgen + wgpu GPU host
  (`KamiCljHost`) compiles clean for `wasm32-unknown-unknown`
  (`cargo check -p kami-clj-host --features host`).

What still needs a real browser/GPU to exercise end-to-end (cannot run headless):
the live `kami.backend.browser` ↔ `KamiCljHost` round-trip on a canvas. `kami.db`
as-of/history needs a time-travel store (datalevin has no as-of; §13). This file
is the正本 for the SDK's boundaries; it is the clj-side sibling of the engine's
`../ARCHITECTURE.md`.

---

## 1. Goal & non-goals

### Goal
- Build KAMI games/scenes **without writing Rust**. Scene graph, ECS, gameplay
  systems, render orchestration, and *shader authoring* are all Clojure.
- **Datomic is the world.** A scene is a set of datoms; an ECS component is an
  attribute; an entity is a Datomic entity. Editing is `transact`, history /
  undo is `as-of`, queries are Datalog.
- Reuse the battle-tested GPU layer (`kami-render`'s 7 scene pipelines, WGSL,
  bootstrap policy) unchanged. We do **not** re-implement wgpu in Clojure.

### Non-goals
- Not a wgpu re-implementation in clj/cljs. WebGPU is driven through
  `kami-render` (WASM in the browser).
- Not a replacement for `kami-clj` (the Rust *Clojure→WASM compiler*). That tool
  compiles per-entity scripts to guest WASM; this SDK keeps the **whole engine
  loop in a host Clojure runtime** and treats the GPU as a service. See §11.
- Not a new GPU bootstrap owner. `kami-render::bootstrap` remains the single
  owner of Backends + Limits policy (per `../ARCHITECTURE.md` Authority Rule 1).

---

## 2. Decision summary (the three forks)

| Fork | Decision | Consequence |
|---|---|---|
| **Render runtime** | **Keep the Rust backend.** GPU stays on `kami-render` (wgpu); clj+Datomic is the authoring / scene / ECS / render-IR layer. | Boundary = **render-IR over WIT/WASM**. "Not Rust" applies to *everything above the GPU* — the SDK, gameplay, scene model — not to the GPU driver itself. |
| **Datomic role** | **Two layers.** Datomic = edit/persist source of truth; projected to an in-memory ECS on load; committed back on save; `as-of` for undo / timeline. | Edit tools speak Datalog; the 60 fps tick speaks dense in-memory arrays. The two are reconciled at load/save boundaries, never per-frame. |
| **Deliverable** | **Design doc + skeleton.** This file + `deps.edn` + `src/kami/*` stubs. | Implementation can start immediately against fixed contracts. |

---

## 3. Layer topology

```
┌──────────────────────────────────────────────────────────────────────┐
│ L5  Game / authoring (your code)                                       │
│     scenes as Datomic tx-data · systems as pure fns over ECS snapshot  │
│     examples/hello_scene.cljk                                          │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L4  kami.scene  — Datomic schema (ECS-as-datoms) + scene graph         │
│     kami.db     — Datomic conn / transact / as-of / Datalog (JVM)      │
│     persist (source of truth)  ⇄  snapshot (transit, portable)         │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L3  kami.ecs    — in-memory archetype store (dense, tick-fast)         │
│     kami.sim    — fixed-step loop · system registry · commit-on-save   │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L2  kami.render — render-IR builder: Datalog/ECS query → draw-list     │
│     kami.wgsl-emit   — WGSL shader authored as clj data → WGSL string       │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L1  kami.ipc    — render-IR → KAMI columnar buffer (zero-copy)         │
│     kami.gpu    — IGpuBackend protocol + backends/{browser,host}       │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼  WIT: kami:engine/frame@1.0.0 (proposed, additive)
┌──────────────────────────────────────────────────────────────────────┐
│ L0  kami-render (Rust / wgpu)  — UNCHANGED GPU executor                │
│     bootstrap · scene_pipelines (Sky/Terrain/Veg/Char/Water/Voxel/     │
│     Particle/Atlas) · register-shader for clj-authored WGSL            │
└──────────────────────────────────────────────────────────────────────┘
```

The **only** new dependency `kami-render` takes on is an *additive* WIT
interface (`kami:engine/frame`, §8). Everything else in L0 is reused as-is.

---

## 4. Process / deployment topology

clj+Datomic and WebGPU live in different processes. Three roles, one shared
`.cljc` core:

```
   ┌─────────────────────────────┐        ┌──────────────────────────────┐
   │ AUTHORING / SERVER (JVM clj) │        │ RUNTIME (browser ClojureScript)│
   │  · Datomic (source of truth) │        │  · kami.ecs in-memory store    │
   │  · kami.db  Datalog queries  │ transit│  · kami.sim 60 fps tick        │
   │  · kami.scene/snapshot ──────┼───────▶│  · kami.render → render-IR     │
   │  · kami.wgsl-emit → WGSL strings  │ (HTTP/ │  · kami.ipc → columnar buffer  │
   │  · editor commits (tx-data) ◀┼─ WS)   │  · kami.gpu  ─────┐            │
   └─────────────────────────────┘        └────────────────────┼──────────┘
                                                                ▼ JS interop
                                                   ┌──────────────────────────┐
                                                   │ kami-render WASM (wgpu)   │
                                                   │  WebGPU → WebGL2 fallback │
                                                   └──────────────────────────┘
```

- **JVM Clojure** owns Datomic and the *edit/build* path. It never touches the GPU.
- **Browser ClojureScript** owns the *runtime* path: project snapshot → ECS, tick,
  build render-IR, push to `kami-render` WASM. This is where "WebGPU" actually runs.
- **`.cljc`** holds everything platform-neutral: the schema, render-IR shape,
  WGSL emitter, IPC column packing. JVM-only = `kami.db`; cljs-only =
  `kami.backend.browser`.

> Editor scenario (Datomic two-layer in action): the browser editor mutates the
> in-memory ECS for instant feedback, accumulates a tx-log, and on **save** sends
> tx-data over WS → `kami.db/transact!`. Undo = `kami.db/as-of` an earlier `t`
> re-snapshotted to the browser. The 60 fps loop never blocks on Datomic.

---

## 5. Datomic schema — ECS as datoms

The core idea: **a component is an attribute, an entity is a Datomic entity, an
archetype is the set of attributes present.** No separate ECS persistence format.

Attribute namespaces (declared as data in `kami.scene/schema`):

| Component | Attributes | Notes |
|---|---|---|
| Identity | `:kami/eid` (uuid, identity) · `:kami/name` (string) | stable across snapshots |
| Hierarchy | `:transform/parent` (ref) · `:transform/children` (derived) | scene DAG |
| Transform | `:transform/translation` `:transform/rotation` `:transform/scale` (tuple f32) | local TRS |
| Mesh | `:mesh/asset` (ref → asset) | |
| Material | `:material/asset` (ref) · `:material/params` (map, edn) | PBR params override |
| Camera | `:camera/fov` `:camera/near` `:camera/far` `:camera/active?` | |
| Light | `:light/kind` (enum) `:light/color` `:light/intensity` | dir/point/spot |
| Shader | `:shader/asset` (ref) → custom clj-authored WGSL | drives §8 register-shader |
| Tags / systems | `:script/systems` (ref many → system idents) | which systems run on this entity |
| Scene | `:scene/name` `:scene/root` (ref) `:scene/env` (map) | env = sky/fog/clear-color |

Assets are *content-addressed* entities (mirrors the Rust asset table keyed by id):

| Asset | Attributes |
|---|---|
| `:asset/id` (string, identity) · `:asset/kind` (`:mesh`/`:material`/`:texture`/`:shader`) · `:asset/uri` (B2/IPFS) · `:asset/sha256` · `:asset/inline` (optional edn for procedural assets) |

Example scene as tx-data:

```clojure
[{:kami/eid #uuid "…tree…" :kami/name "tree-01"
  :transform/translation [0.0 0.0 0.0]
  :transform/rotation    [0.0 0.0 0.0 1.0]
  :transform/scale       [1.0 1.0 1.0]
  :mesh/asset     [:asset/id "mesh/conifer"]
  :material/asset [:asset/id "mat/bark"]}
 {:kami/eid #uuid "…cam…" :kami/name "main-cam"
  :camera/fov 60.0 :camera/near 0.1 :camera/far 1000.0 :camera/active? true
  :transform/translation [0.0 2.0 8.0]}]
```

Time travel / undo is free: `(d/as-of db t)` gives the scene at tick `t`;
`(d/history db)` gives the full edit provenance (who placed which tree, when).

---

## 6. Two-layer model: Datomic ⇄ in-memory ECS

```
  Datomic (durable, Datalog)                in-memory ECS (kami.ecs)
  ─────────────────────────                 ───────────────────────────
  datoms, history, as-of            load    archetype tables, dense arrays
  edit tools, queries, undo  ──snapshot──▶  60 fps tick, systems, render-IR
                             ◀──commit────   (Float32Array / typed buffers)
```

- **`kami.scene/snapshot`** — Datalog-query the whole scene (or a sub-DAG) at a
  `t` and emit a portable **scene-snapshot** (transit/edn) the browser can load.
- **`kami.ecs/load-snapshot`** — project the snapshot into archetype tables:
  components grouped into columns so a system iterating "all (transform mesh)"
  walks contiguous memory. Transforms land directly in a `Float32Array` so §7→§9
  can hand them to the GPU with zero further copies.
- **`kami.ecs/->tx`** — diff the in-memory store against the loaded snapshot and
  emit Datomic tx-data; **`kami.db/transact!`** commits it. This is the save path.

The invariant: **Datomic is consulted at load/save boundaries only.** A frame
never queries Datomic. This keeps the tick deterministic and Datomic-latency-free,
while preserving Datomic as the single durable truth.

---

## 7. render-IR — the clj ↔ Rust contract

render-IR is a plain-data description of one frame. The renderer is **retained by
id, immediate by frame**: meshes/materials/shaders are uploaded once (keyed by
asset id), each frame submits a draw-list that *references* those ids plus an
instance buffer. `kami-render` is a "dumb" executor of this IR.

```clojure
{:frame/n        42
 :frame/clear    [0.94 0.92 0.84 1.0]            ; Nintendo cream #f0ead6 (default)
 :frame/camera   {:view #f32[16 …] :proj #f32[16 …]}
 :frame/passes
 [{:pass/id     :main
   :pass/target :swapchain
   :pass/draws
   [{:draw/pipeline :pbr                          ; built-in or registered shader id
     :draw/mesh     "mesh/conifer"                ; asset id (already uploaded)
     :draw/material "mat/bark"
     :draw/instances {:count 320                  ; ↓ becomes KAMI IPC columns (§9)
                      :model  #f32[…320×16…]      ; Dtype/Mat4 column
                      :tint   #f32[…320×4…]}}]}]}  ; Dtype/F32 stride 4
```

Design rules:
- **No per-object host call.** One `submit-frame` per frame replaces N
  `draw-mesh` calls of the legacy WIT (`../wit/kami-game/world.wit`). Instancing
  is the default, not an optimization.
- **Built-in pipelines** map to `kami-render::scene_pipelines` by keyword
  (`:sky :terrain :vegetation :character :water :voxel :particle :atlas :pbr`).
- **Custom pipelines** are `:draw/pipeline <shader-asset-id>`, registered once via
  §8 from `kami.wgsl-emit` output.
- render-IR is **serializable and diffable** — it's the natural record/replay and
  golden-test surface (snapshot a frame's IR, compare bytes).

---

## 8. WGSL as data + the additive WIT contract

### 8a. `kami.wgsl-emit` — shaders authored as Clojure data
A shader is a map; `kami.wgsl-emit/emit` produces a WGSL string. This keeps shader
authoring in clj (composable, testable) without re-implementing a GPU.

```clojure
{:wgsl/name "ripple"
 :wgsl/bindings [{:group 0 :binding 0 :var :uniform :name "u" :type :Globals}]
 :wgsl/structs  {:Globals [[:time :f32] [:mvp :mat4x4<f32>]]}
 :wgsl/vertex   {:in  [[:pos :vec3<f32>]] :out [[:clip :vec4<f32> :builtin/position]]
                 :body '[(set! clip (* u.mvp (vec4 pos 1.0)))]}
 :wgsl/fragment {:out [[:color :vec4<f32> 0]]
                 :body '[(set! color (vec4 0.3 0.6 1.0 1.0))]}}
```

`kami.wgsl-emit/emit` lowers the small s-expression body (`set!`, `*`, `vec4`,
swizzles, `if`, `let`) to WGSL. Start with a thin subset; expand as scenes need
it. Built-in pipelines need no WGSL — they reuse `kami-render`'s shipped shaders.

### 8b. `kami:engine/frame@1.0.0` (proposed, additive)
The legacy world (`../wit/kami-game/world.wit`) is per-call immediate-mode. This
SDK needs a frame-submit + resource-registration surface. Proposed `wit/kami-frame.wit`:

```wit
package kami:engine@1.0.0;
interface frame {
  // Upload-once, keyed by asset id. Idempotent on identical bytes.
  register-mesh:     func(id: string, vertices: list<f32>, indices: list<u32>) -> u32;
  register-material: func(id: string, params: list<f32>) -> u32;
  // clj-authored WGSL (kami.wgsl-emit/emit) → a pipeline id. layout is the bind-group plan.
  register-shader:   func(id: string, wgsl: string, layout: string) -> u32;
  // Tiny JSON draw-table + the KAMI IPC columnar buffer (§9). Zero-copy matrices.
  submit-frame:      func(meta: string, ir-ptr: u32, ir-len: u32);
}
world kami-clj-host { export frame; /* + legacy imports for input/time */ }
```

This interface is **implemented** in `../kami-clj-host` (`wit/kami-frame.wit` is
the spec; `host.rs::KamiCljHost` is the wasm-bindgen realization).

> **No engine-owner review needed.** `kami-clj-host` is a **separate additive
> workspace crate** that *consumes* `kami-render` (via `RenderContext` + its own
> wgpu pipeline) rather than modifying it. Per `../ARCHITECTURE.md`'s
> change-approval table, "new crate" needs no review — and bootstrap/Backends/
> `scene_pipelines` are untouched, so there is no `kami-app-{game}` impact note.
> The only engine-repo edits are additive: the `wit/kami-frame.wit` spec and one
> line in the workspace `members` list.

---

## 9. Transport — KAMI IPC columnar (zero-copy)

render-IR instance data is serialized to the existing **KAMI IPC columnar format**
(`../kami-core/src/ipc.rs` — `Column` / `Dtype` / `KamiFrame`). `Dtype` already
has `Mat4` and `Quat`, so an instance `model` array is one `Dtype::Mat4` column
that DMAs straight into a wgpu instance buffer — "all transitions zero-copy or
single memcpy" is the format's stated contract.

```
kami.render →  render-IR (edn)
kami.ipc    →  buffer: [Column{Mat4 camera×2}, Column{Mat4 instances×N}, …]  (KamiFrame)
            +  meta:   {n, clear, draws:[{pipeline, mesh, material, count}, …]}  (tiny JSON)
kami.gpu    →  KamiCljHost.submit_frame(JSON.stringify(meta), Uint8Array(buffer))
kami-clj-host → frame::decode(buffer) → camera view_proj + instance mat4s
            →  wgpu instance buffer + draw_indexed (per draw, resolving ids→handles)
```

The split is deliberate: the **heavy** per-instance matrices stay in the
zero-copy columnar buffer; only the **tiny** retained-by-id references (which
mesh/material/pipeline each column maps to) travel as JSON. The Rust decoder
(`../kami-clj-host/src/frame.rs`) is pure and unit-tested against the exact bytes
`kami.ipc/pack` emits — the cross-language contract anchor.

- **Browser**: columns are JS `Float32Array`/`Uint32Array` written into the
  `kami-render` WASM `memory` via the cabi allocator; `submit-frame` gets the
  base pointer. `kami.ipc` builds the 16-byte-aligned column headers.
- **Host (JVM)**: same headers in a `java.nio.ByteBuffer`; only used by an
  optional headless/server-render backend (out of scope for the chosen "browser +
  Rust backend" path, but the `IGpuBackend` protocol leaves room).

---

## 10. Namespace map / public API

| ns | platform | status | owns | key vars |
|---|---|---|---|---|
| `kami.scene` | cljc | ✅ impl | schema (data), scene graph, pure snapshot builder + validation | `schema` `add-entity` `tree` `valid?` `build-snapshot` |
| `kami.db` | clj (JVM) | ✅ impl (datalevin) | Datalog conn, transact, as-of, Datalog helpers, snapshot projection | `connect` `transact!` `db` `as-of` `q` `history` `snapshot` |
| `kami.ecs` | cljc | ✅ impl | in-memory archetype store, projection, dirty-diff | `world` `load-snapshot` `query` `add` `set-component` `remove-entity` `->tx` `mark-saved` |
| `kami.sim` | cljc | ✅ impl (RAF cljs) | fixed-step loop, system registry, save | `defsystem` `register!` `step` `commit!` `render-once` `run!` |
| `kami.render` | cljc | ✅ impl | render-IR builder from ECS (instancing + camera) | `frame` `camera-ir` `draws-for` `merge-instances` `nintendo-cream` |
| `kami.math` | cljc | ✅ impl | column-major 4×4 matrix math | `mul` `from-trs` `perspective` `invert-rigid` `identity4` |
| `kami.wgsl-emit` | cljc | ✅ impl | WGSL-as-data emitter (subset) | `emit` `emit-struct` `emit-stage` `builtin?` |
| `kami.ipc` | cljc | ✅ impl | render-IR → KAMI columnar buffer | `pack` `column` `dtype` `byte-len` |
| `kami.gpu` | cljc | ✅ impl | `IGpuBackend` protocol + frontend (`submit!`/`ensure-assets!`) | `IGpuBackend` `backend` `register-mesh!` `register-shader!` `submit!` `ensure-assets!` |
| `kami.backend.browser` | cljs | 🚧 stub | WASM/WebGPU backend via `kami-render` (needs §8b WIT) | `make` (impls IGpuBackend) |
| `kami.backend.host` | clj | 🚧 stub | optional headless backend (FFI/wasmtime) | `make` |

Public entry (browser): `kami.sim/run!` with a `{:snapshot … :backend … :systems …}`
map. Public entry (authoring): `kami.db/transact!` + `kami.db/snapshot`. The pure
snapshot constructor `kami.scene/build-snapshot` lets you build/test snapshots
with no DB at all.

---

## 11. Relationship to existing code

| Existing | Relationship |
|---|---|
| `../kami-clj` (Rust: Clojure→WASM compiler) | **Complement, not replace.** `kami-clj` compiles *per-entity scripts* to guest WASM running under `kami-script-runtime`. This SDK keeps the *whole engine loop* in a host clj runtime and uses the GPU as a service. A `kami-clj`-compiled `defsystem` could later be registered into `kami.sim` as a hot-path system; both target `kami:engine`. |
| `../kami-render` (Rust/wgpu) | **Reused unchanged.** `kami-clj-host` bootstraps through `RenderContext::for_web_surface` (the sanctioned single owner). |
| `../kami-clj-host` (Rust, **new**) | The concrete `kami:engine/frame` host: `frame.rs` (pure KAMI decoder, cross-language tested) + `host.rs` (wasm-bindgen `KamiCljHost` + wgpu instanced pass). Additive workspace crate — per `../ARCHITECTURE.md` change-approval, a new crate needs no engine-owner review. |
| `../kami-engine-sdk` (empty submodule, was TS/Svelte) | This is its clj counterpart. The TS SDK targets `kami-web`/`kami-app` wasm exports; this targets the same engine via render-IR. They can coexist (TS for DOM UI, clj for scene/logic). |
| `../kami-core/src/ipc.rs` (KAMI IPC) | **The transport** (§9). clj writes the columns the Rust format already reads. |
| `root/` (clj + Datalog substrate) | Datomic conventions, deps.edn style, transit transport, and the AT/IPFS/B2 asset URIs come from here. Assets in `:asset/uri` resolve through the same B2/IPFS layer. |

---

## 12. Build & run flow

```bash
# 1. JVM authoring (Datomic source of truth, datalevin by default)
kbb -M:dev                       # REPL
#   (require '[kami.db :as db] '[kami.scene :as scene])
#   (def conn (db/connect "/tmp/kami-db"))     ; datalevin dir
#   @(db/transact! conn my-scene-tx)
#   (db/snapshot (db/db conn))                 ; → transit served to browser

# 2. Build the Rust GPU host (clj↔wgpu bridge) for the browser
cd ../kami-clj-host
wasm-pack build --target web --features host   # → pkg/kami_clj_host.js + _bg.wasm

# 3. Browser runtime (ClojureScript → kami-clj-host WASM → kami-render → WebGPU)
cd ../kami-engine-sdk-clj
kbb -M:shadow watch app          # shadow-cljs build :app
#   import KamiCljHost from kami-clj-host pkg, then:
#   (go (kami.sim/run! {:canvas "c" :snapshot snap
#                       :backend (<! (browser/make {:canvas "c"})) :systems [...]}))

# ── Verification (all runnable headless) ──────────────────────────────────
# clj contract layer — 16 tests / 61 assertions
kbb -Sdeps '{:paths ["src" "test"]}' \
  -M -e "(require '[clojure.test :as t] 'kami.contract-test 'kami.runtime-test) \
         (t/run-tests 'kami.contract-test 'kami.runtime-test)"
# real-datalevin round-trip (connect→tx→snapshot→ecs→render-IR→pack→commit)
kbb -M:roundtrip
# regenerate the cross-language fixture after a format change
kbb -Sdeps '{:paths ["src" "dev"]}' -M -m gen-fixture
# Rust decoder cross-language contract — 4 tests
( cd .. && cargo test -p kami-clj-host --target aarch64-apple-darwin )
# Rust GPU host compiles for wasm
( cd .. && cargo check -p kami-clj-host --features host )
```

---

## 13. ADRs & open questions

**ADR-CLJ-01 — GPU stays Rust, clj is the brain.** Re-implementing wgpu in
clj/cljs duplicates `kami-render`'s bootstrap, 7 pipelines, and WGSL with no
WebGL2-fallback parity. Decision: keep `kami-render`; bridge with render-IR. The
"not Rust" requirement is satisfied above the GPU line (scene, ECS, gameplay,
shader authoring are clj).

**ADR-CLJ-02 — Datomic = ECS source of truth, projected for the tick.** Per-frame
Datalog can't hit 60 fps; pure in-memory ECS loses history/undo. Decision: two
layers reconciled at load/save (§6). Datomic gives free undo (`as-of`) and edit
provenance (`history`); the dense ECS gives frame-rate.

**ADR-CLJ-03 — retained-by-id, immediate-by-frame render-IR.** Replaces N
per-object host calls with one columnar `submit-frame`; instancing by default;
IR is serializable for record/replay/golden tests (§7).

**Open questions**
1. Datomic flavor — Cloud / On-Prem (Peer) / **Datahike or datalevin** as an
   OSS, blockchain-friendly Datalog store given `root/`'s "no Datomic" platform
   note? The schema (§5) and `kami.db` API are Datalog-portable; pick at impl.
2. WGSL subset scope for `kami.wgsl-emit` — how much of WGSL to cover before falling
   back to raw WGSL strings.
3. Snapshot granularity — whole-scene vs streaming sub-DAGs (for open-world,
   align with `kami-pipelines` chunk streaming).
4. Where `kami-clj`-compiled hot systems plug into `kami.sim` (guest WASM vs host).

---

## 14. Prohibitions inherited from KAMI Engine
(see `../AGENTS.md` — they apply to clj-authored scenes too)
- **No Canvas 2D.** Rendering is wgpu via `kami-render` only.
- **No bespoke renderer.** `kami-render` pipelines + clj-authored WGSL registered
  through §8 — nothing else.
- **Nintendo style.** Default clear color is cream `#f0ead6` (§7); no dark theme.
- **No audio files.** Sound is Web Audio synthesis (`kami-ui-sdk/kami-sound.js`).
