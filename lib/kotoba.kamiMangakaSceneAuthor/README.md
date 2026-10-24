# kami-mangaka-scene-author

The **clj/EDN authoring tier** over the Rust `kami-mangaka-scene` 3D facade
(ADR-2605141200 / ADR-2606282100). clj is the brain; the Rust facade
(`kami-vrm` + `kami-scene-graph` + `kami-render` + `kami-postfx`) is the GPU arm.

You author a `MangakaScene` as plain Clojure data and project it to the exact
JSON-LD that the Rust `MangakaScene::from_jsonld` reads — or to the
`com.etzhayyim.mangaka.composeScene3d` XRPC payload driven by the
`lg_mangaka.compose_scene_3d` Pregel graph. **Pure data: no GPU, no VRM bytes.**

This is the `kami-live` / `kami-engine-sdk-clj` pattern (scene-as-EDN) applied to
the mangaka 3D facade, and the 3D sibling of `kami-mangaka-render-clj` (2D panels).

## API

```clojure
(require '[kami.mangaka.scene :as s])

(-> (s/scene)
    (s/add-character {:id 0 :rkey "nei" :expression "joy"   ; emotion word → Expression
                      :pose-label "action.reach"            ; lexicon preset label
                      :root-xform (s/transform [0 0 0])})
    (s/set-camera (s/camera {:eye [0 1.4 3] :target [0 1.4 0]
                             :shot "Closeup" :dof (s/dof 3.0 1.8)}))
    (s/set-lights s/three-point)                            ; key+fill+rim presets
    (s/set-environment (s/environment {:biome "water-city" :weather "clear" :seed 42}))
    s/->json)            ; → JSON string for the Rust facade / composeScene3d XRPC
```

Faithful to the Rust public types (`lib.rs`): `Transform` / `CameraSpec` /
`LightSpec` / `EnvironmentSpec` and the `ShotGrammar` / `LightRole` /
`Expression` / `FxKind` enums (variant names verbatim). glam `Vec3` ↔ `[x y z]`,
`Quat` ↔ `[x y z w]`. The three-point light preset values mirror
`LightSpec::three_point_*`.

## Test

`src/` and `test/` are `.cljc`. One suite, two runtimes — the JVM is the last
runtime in this workspace's order, not the only one.

```bash
kbb -M:test                                  # JVM
kbb --backend sci --classpath src:test test/run_portable.cljk  # nbb — no JVM, no build step
```

Run the nbb one from somewhere that is not this directory too; a suite run only
from the repo root cannot detect a working-directory assumption:

```bash
cd /tmp && kbb --backend sci --classpath ~/…/repo/src:~/…/repo/test ~/…/repo/test/run_portable.cljk
```

Both print `Ran 15 tests containing 70 assertions. 0 failures, 0 errors.`
`deps.edn` has no `:local/root` sibling dependencies to break, and the nbb path
has no third-party dependency at all — `json.data-json` is the `:clj` branch
of `->json` only.

### One divergence, on purpose

`->json` emits `"fov_deg":35.0` on the JVM and `"fov_deg":35` under
ClojureScript, because ClojureScript has no distinct double type — `1.0` and `1`
are one `js/Number`. Both are the same JSON number and both deserialize into the
Rust `f64` fields, so the consumer is unaffected; anything that hashes the TEXT
is. `json-text-differs-between-runtimes-on-whole-doubles` asserts it in both
directions.

## Prove the suite can fail

```bash
kbb --backend sci tools/check-mutations.cljk   # pre-flight: each :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # 9 mutations against the JVM half
```

Expect `8 killed, 1 survived`. The survivor is deliberate and documented in
`tools/mutations.edn`: this harness drives `kbb -M:test`, so a mutation in
the `:cljs` branch of `->json` is invisible to it. That branch is covered by
`test/run_portable.cljk` instead, and the header records the measurement.

## Provenance

Split out of `kotoba-lang/kami-engine`'s
[`kami-mangaka-scene-author/`](https://github.com/kotoba-lang/kami-engine/tree/main/kami-mangaka-scene-author)
subtree into its own standalone repo, following the same pattern already used
for the sibling `kami-mangaka-genko-clj` -> `kotoba-lang/kami-genko` split. The
source in `kami-engine` was live, current Clojure — never part of the deleted
Rust workspace (PR #82) — so this is a copy-out, not a restore.
