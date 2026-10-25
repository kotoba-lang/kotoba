# Testing

The `.cljc` domain interpreters (`kami.fsm`, `kami.physics`, `kami.netsync`, `kami.level`,
`kami.webgpu.ir`) are the **same source** that runs on the browser and JVM
surfaces. Repository-local tests focus on the CLJ/EDN contract:

| Surface | How it runs the interpreters | Test command |
|---|---|---|
| **web** | CLJS → WebGPU / DOM (`kami.webgpu`, `kami.ui`, …) | in-browser (isekai.network) |
| **JVM** | `kbb -M:test` loads the `.cljc` directly | `kbb -M:test` |

## Commands

```bash
kbb -M:test                              # all namespaces on the test path
kbb -M:test -n vertex-layout-test        # one namespace
kbb -M:test -r '^(?!playwright).*-test$' # everything that needs no browser
```

**This used to say `kbb -M:test` / `kbb -M:verify`, and neither exists here** — there is
no `bb.edn` in this repo, and `bb` is retired as a script host workspace-wide
(ADR-2607173000). The `:test` alias in `deps.edn` is also what the murakumo
fleet's `:jvm-test` gate requires, so wiring it is what makes this repo gateable
at all; the GitHub Actions workflow the old text pointed at was removed with
every other one (ADR-2607300900).

## Known-red namespaces (as of 2026-08-06)

Two fail for reasons predating this alias — they went unnoticed precisely
because nothing could run them:

| Namespace | State |
|---|---|
| `compute-golden-test` | wants `kami.cartpole-math`, but `kotoba-lang/cartpole-math` now ships `kotoba/cartpole_math.kotoba` — the namespace it requires no longer exists |
| `pipeline-specs-test` | shells to `kbb scripts/gen_pipeline_specs.cljk`, which fails at its `require` of `kami.pipelines`: `bb` does not resolve this repo's `deps.edn` (see the note in `nbb.edn`). Same root cause as the stale `kbb -M:test` above |
| `cascade-shadow-test` | skips itself when `naga` is not installed (0 assertions) |

Everything else is green:

```bash
kbb -M:test -r '^(?!playwright|compute-golden|pipeline-specs).*-test$'
kbb -M:test -n playwright-vertex-layout-test   # real WebGPU, needs Chrome
```

`atmosphere-graph-test` was a third: it asserted a hardcoded count of HDR graphs
and went red when a third one was added *correctly*. It now asserts the property
instead. Because these namespaces `throw` on failure, one red namespace aborts
every namespace after it — a full-suite run is only meaningful once they are
addressed.

## What's asserted

- **fsm** `advance` — transitions fire on matching events; identity otherwise
- **physics** `collides?` (symmetric) + `separate` (overlap → deltas; non-colliding → none)
- **netsync** `snapshot` (synced fields only, idempotent) + `interp` (lerp/snap, t-endpoints)
- **level** `zone-radius` (monotonic, floors at `:min-radius`) + `in-zone?` + `spawn-points`
- **camera** `rig->camera` (distance/azimuth/height → eye/target)
- **ir** `render-ir` / `valid?`
