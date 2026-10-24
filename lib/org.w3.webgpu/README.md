# kotoba-lang/org-w3-webgpu

Raw **W3C WebGPU** JS API — a thin ClojureScript wrapper, one function per
spec call, factored out of `kotoba-lang/webgpu` per **ADR-2607051400**
(`90-docs/adr/2607051400-kami-engine-webgpu-sdk-consolidation.md`,
`com-junkawasaki/root`).

Same naming/split pattern as `org-khronos-glb` / `org-khronos-gltf` /
`org-materialx` / `org-openusd`: an external standards body's spec gets its
own narrow-scope binding repo, and the kami-engine-specific EDN domain
vocabulary that consumes it lives one level up (here, in `kami-webgpu`).

## Why this repo exists

`kotoba-lang/webgpu` (née `kami-webgpu`) is "declarative WebGPU from EDN —
hiccup for the GPU": a render-IR/render-graph vocabulary plus the executor
that walks it. That executor calls the raw browser WebGPU API directly
(`navigator.gpu.requestAdapter`, `device.createBuffer`, `.beginRenderPass`,
...), interleaved with the EDN-interpretation and matrix-math code.

This repo is the other half: **just the raw spec surface**, with zero
render-graph/scene/material opinions. `webgpu` depends on this instead of
calling `navigator.gpu`/`GPUDevice`/... inline — mirroring how `kami-engine`
depends on `org-materialx` for MaterialX vocabulary instead of re-parsing
`.mtlx` XML itself.

**Scope is deliberately narrow: 1:1 spec bindings only.** No render graph, no
scene EDN, no material/shader authoring vocabulary — those stay in
`kami-webgpu`.

## API

`w3.webgpu` — one function per spec call, kebab-cased
(`requestAdapter` → `request-adapter!`, `createRenderPipeline` →
`create-render-pipeline!`, ...). Descriptors are plain JS objects
(`#js {...}`) built by the caller with the spec's own camelCase keys — this
wrapper does not translate Clojure maps into descriptors (WebGPU's
multi-word camelCase keys like `depthWriteEnabled`/`shaderLocation` don't
round-trip through a kebab-case map without a translation layer, and that
layer is deliberately `kami-webgpu`'s job, not this repo's).

```clj
(require '[w3.webgpu :as gpu])

(-> (gpu/request-adapter!)
    (.then (fn [adapter] (gpu/request-device! adapter)))
    (.then (fn [device]
             (let [buf (gpu/create-buffer! device
                         #js {:size 64 :usage (bit-or (gpu/buffer-usage :vertex)
                                                       (gpu/buffer-usage :copy-dst))})]
               (gpu/write-buffer! (.-queue device) buf (js/Float32Array. 16))))))
```

Covered so far: adapter/device request, canvas context (`get-context!`/
`configure-context!`), buffer/texture/sampler/shader-module/pipeline/
bind-group creation, command encoding + render-pass recording
(`set-pipeline!`/`set-bind-group!`/`set-vertex-buffer!`/`set-index-buffer!`/
`draw-indexed!`/`end-pass!`/`finish!`/`submit!`), reusable render-bundle
recording/execution (`create-render-bundle-encoder!`/
`finish-render-bundle!`/`execute-bundles!`), and the
non-indexed `draw!` call used by fullscreen post-processing triangles, plus the
`buffer-usage`/`texture-usage` flag-constant helpers.

## Status

**Scaffold (Phase 1 of ADR-2607051400).** The wrapper surface above covers
every raw WebGPU call currently made by `kotoba-lang/webgpu`'s executor
(`src/kami/webgpu.cljs`); Phase 2 rewires that executor to call through this
repo instead of `navigator.gpu`/`GPUDevice`/... directly (`:local/root`
dependency, no behavior change intended — a pure extraction).

## Develop

Browser-only (no JVM WebGPU implementation exists), so there is no `clojure
-M:test` suite here — correctness is pinned by `kotoba-lang/webgpu`'s own
visual/golden-frame tests once Phase 2 wires it through this repo.
