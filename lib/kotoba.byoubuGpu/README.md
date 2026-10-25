# byoubu-gpu

**Tier 2: a [`byoubu`](https://github.com/kotoba-lang/byoubu) backdrop as a live
WebGPU scene.**

```clojure
(require '[byoubu-gpu.core :as gpu])

(gpu/mount! canvas :purple-desert)
;; => Promise of {:tier :gpu :ctx … :stop! …}
;;              or {:tier :poster :reason "navigator.gpu unavailable"}
```

This is the opt-in tier. `byoubu` and `byoubu-ui` deliberately never reach the
render stack — a page that wants a plate and legible text must not inherit
`sky` / `terrain` / `postfx` / `webgpu` and, through them, the compiler. This
repo is where an app opts *into* the GPU, so the dependency lives here and
nowhere upstream.

## Not a second renderer

`kami.webgpu/init!` takes `{:graph <EDN>}`, and its frame loop runs the graph's
`:passes` in order. The engine's own default graph already contains fullscreen
pipelines (`:atmosphere`, `:bloom`, `:ssao`) that draw three vertices with no
mesh. A backdrop is exactly that shape, so `byoubu-gpu.graph/render-graph`
returns **data handed to the canonical executor**:

```clojure
{:shaders   {:byoubu "<WGSL>"}
 :uniforms  {:byoubu {:size 192}}
 :pipelines {:byoubu {:shader :byoubu :fullscreen true :color :screen
                      :binds [{:uniform :byoubu}]}}
 :passes    [{:pipeline :byoubu :color :screen :clear [0 0 0]}]}
```

The one thing the executor lacked was a way to bind a **caller-supplied**
uniform: `build-bind` recognised exactly `:uniform`, `:atmosphere-uniform`,
`:ssao-uniform` and `:style-uniform`, all engine-owned buffers of fixed size.
So `{:uniform <name>}` binds, a `:uniforms` graph key and `write-uniform!` were
added to `kotoba-lang/webgpu` — a general capability, because the alternative
is every domain package reaching past the executor to the raw W3C binding and
growing its own renderer.

## The shader is data

`byoubu-gpu.shader/wgsl` builds the program with `kami.wgsl`, the workspace's
WGSL-as-data SSoT, from the `:byoubu/scene` spec. Structure constants are baked
at generation time — `:ridge-count` is known, so the ridge loop is unrolled
into `ridge0…ridgeN` functions rather than becoming a WGSL `for` over a
uniform. Colours stay in the uniform so a theme can move them without a
recompile.

Because the shader, the uniform packing and the graph are all `.cljc` with no
browser dependency, they are unit-tested on the JVM and nbb **without a GPU**:
that the WGSL declares what the CPU packs, that a field added to the struct
without a packer throws instead of writing zeroes, that the graph speaks the
executor's actual pass vocabulary, and that all three byoubu tiers derive the
horizon from the same camera pitch.

The noise is the same *construction* as `terrain.noise` — hash-based value
noise (deliberately not gradient/Perlin, same patent reasoning), cosine
interpolation, octaves at lacunarity 2 / persistence 0.45 — but not bit
identical: reproducing i32 wrapping semantics in WGSL would be a second
implementation to keep in sync for no visible gain. The poster and the live
scene read as the same landscape without pretending to be the same pixels.

## Fallback

`mount!` resolves to `{:tier :poster :reason …}` when WebGPU is unavailable,
and does **not** fall back to WebGL 2.0. The engine's WebGL path runs its own
GLSL, pre-transpiled from WGSL by naga at build time (`kami.webgl.glsl` is a
generated file), so arbitrary WGSL cannot reach it without adding that
transpile step to this repo. A caller that gets `:poster` should leave
`byoubu-ui`'s plate in place — the T1 still over the T0 gradients, which is a
complete backdrop rather than a blank canvas.

## Tests

```bash
kbb --backend sci bin/test.cljk      # ClojureScript
kbb -M:test        # JVM
```

Browser build (through the workspace resource governor, which serialises heavy
builds across all sessions):

```bash
node ../../../scripts/resource-guard.mjs run build -- amu compile --target wasm32-browser demo
amu compile --target wasm32-browser demo    # http://localhost:8793
```

See `docs/adr/0001-byoubu-gpu.md`.
