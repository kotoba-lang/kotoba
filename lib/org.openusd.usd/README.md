# kotoba-lang/org-openusd

(renamed from `kotoba-lang/usd` 2026-07-05 — reverse-domain naming for an
external-spec-name repo, openusd.org, same ADR-2607041500 rename precedent
as `org-khronos-glb`/`org-khronos-gltf`/`org-materialx`.)

Kotoba DSL package for `kotoba.usd`.

The implementation lives in `usd.core`; `kotoba.usd` is provided as a compatibility facade.

## What this is (and isn't)

A pure kotoba-clj/wasm, zero-dependency **USDA (ASCII) text** reader/writer — "hiccup for scenes".
A USD prim hierarchy is EDN you fork and diff like the rest of the kotoba.\* world:

```clojure
(usd.core/usda {:defaultPrim "hello" :upAxis :Y}
  [:def "Xform" :hello {:kind "component"}
   [:def "Sphere" :world
    [:attr "double" :radius 2]
    [:attr "color3f[]" :primvars:displayColor [[1 0 0]]]]])
;; => "#usda 1.0\n(\n    defaultPrim = \"hello\"\n    upAxis = \"Y\"\n)\n\ndef Xform \"hello\" ( ...
```

**Scope (ADR-0048 §4, "Relationship to ADR-2605261800"): `usd.core` itself is ASCII-text only.**
The parser/emitter read and write the `.usda` text subset — `def`/`over`/`class` prim blocks
(nested), typed attribute and `rel` relationship statements, `variantSet` blocks, comments, and
scalar/tuple/array values. It deliberately does **not** implement binary `.usdc`/`.usdz` packages,
a Hydra render delegate, or full composition (references/payloads/sublayers/relocates as their own
statements) natively — that larger, real USD-runtime effort is reserved to `kami-usd`
(tinyusdz-via-Emscripten) / `kami-usd-native` (gated Rust fallback) in `com-junkawasaki/root`
(ADR-2605261800), which this repo does not duplicate. If/when that lands, this repo's ASCII
round-trip logic is meant to be reused inside it as the fast/simple case, not thrown away.

**Binary `.usdc`/`.usdz` files ARE readable/writable, via `usd.usdc-bridge` (ADR-2607101525 M3)** —
not a native crate-format implementation, but a thin oracle bridge (`tools/usd_oracle.py`, the same
`pxr`/`usd-core` this repo already uses to validate itself) that converts binary <-> ASCII text
and hands the text side to `usd.core`'s own real parser/emitter. See "Test" below for the oracle
setup this needs (JVM-only, `.clj` not `.cljc`).

## Emitter → Parser symmetry

`usd.core/usda`/`prim` (EDN → USDA text) and `usd.core/parse`/`parse-prim` (USDA text → EDN) are
inverses over the same shape: `[spec type? name meta? & body]`, where `body` mixes `[:attr type
name value]`, `[:rel name value]`, `[:variant-set name {variant [body…]}]`, and nested prims. Both
directions are exercised by golden + round-trip tests in `test/usd/core_test.cljk`, including a
hand-written real-world `.usda` snippet the parser was never generator-fitted against.

```clojure
(require '[kotoba.usd :as u])
(let [src (u/usda {} [:def "Sphere" :world [:attr "double" :radius 2]])]
  (u/parse src))
;; => {:opts {}, :prims [[:def "Sphere" :world [:attr "double" :radius 2]]]}
```

### Parser: known gaps (read before assuming exact round-trip equality)

None of these lose *structure* — they collapse a distinction real USDA text itself does not carry,
or they are deliberately out of this ADR's scope:

- **Token vs. string values are indistinguishable in USDA text.** `val*` renders both a Clojure
  keyword and a Clojure string the same way (a quoted string), so `parse` always returns a plain
  string for a scalar value — never a keyword. `{:upAxis :Y}` round-trips to `{:upAxis "Y"}`, not
  back to `{:upAxis :Y}`. Prim/attribute/relationship **names**, and `[:asset ..]`/`[:path
  ..]`/`[:array ..]`-tagged values, are unambiguous and round-trip exactly (they have a distinct
  lexical marker: quotes-after-a-keyword position, `@…@`, `<…>`, or bracket-vs-paren shape).
- **`uniform`/`custom`/`varying` attribute qualifiers** are folded into the returned type string
  (e.g. `"uniform token[]"`) rather than a separate EDN field — this still round-trips losslessly
  as text through `attr`, it's just not a distinct slot today.
- **List-edit operators other than `prepend`** (`add`/`delete`/`append`/`reorder`) are recognized
  and discarded, not reproduced — this library's own emitter only ever produces `prepend`.
- **Attribute-level metadata blocks** (e.g. `(interpolation = "vertex")` after a value) are
  recognized and skipped — there is no EDN slot for per-attribute metadata yet.
- **Out of scope, and raise a clear error rather than mis-parsing silently:** `timeSamples`
  (animated/time-sampled values) and composition arcs written as their own body-level statements
  (`references = …` / `payload = …` / `subLayers = […]` / `relocates = …` outside a prim's metadata
  parens). A `variantSet` block, or a `prepend`-style composition-arc key *inside* a prim's `( … )`
  metadata block (exactly what this repo's own `prim`/`usda` emit), are supported. Binary
  `.usdc`/`.usdz` is not out of scope for the *repo* — see `usd.usdc-bridge` above — it is
  specifically out of scope for `usd.core`'s own native parser/emitter, which stay ASCII-only.

## Binary support: `usd.usdc-bridge`

```clojure
(require '[usd.usdc-bridge :as bridge])

(bridge/write-usdc! {:defaultPrim "hello"}
  [[:def "Sphere" :hello [:attr "double" :radius 2]]]
  "/tmp/scene.usdc")

(bridge/read-usdc "/tmp/scene.usdc")
;; => {:opts {:defaultPrim "hello"}, :prims [[:def "Sphere" :hello [:attr "double" :radius 2]]]}
```

Requires the same oracle setup as `usd.oracle-test` (`pip install -r tools/requirements.txt`, or
`USD_ORACLE_PYTHON` pointed at an interpreter with `pxr`). `oracle-available?` reports whether one
is on hand before you call `read-usdc`/`write-usdc!`.

## Coordinate-space vocabulary for future `UsdSkel`-adjacent work (ADR-0048 §1)

This repo doesn't implement `UsdSkel` parsing/skinning — that's out of scope here too — but as the
USD format library in this org, it's the right place to pin the **vocabulary** any future
`UsdSkel`-adjacent kotoba-clj code (`character`, `vrm`, `mesher`, `skeleton`, …) should reuse,
rather than each library inventing its own space names.

OpenUSD's `UsdSkel` schema (see
[openusd.org/dev/api/_usd_skel__schemas.html](https://openusd.org/dev/api/_usd_skel__schemas.html))
distinguishes three coordinate spaces a skinned mesh's points pass through:

- **Bind pose / `geomBindTransform`** — a per-skinned-primitive transform, authored on the
  `UsdSkelBindingAPI`, that maps the mesh's *bind-time* local points into the space of the skeleton
  the mesh is bound to. This is the "where was the mesh sitting, relative to the skeleton, at the
  moment it was rigged" transform — it is what lets skinning math treat the mesh and the skeleton's
  joints as living in one consistent frame before any deformation is applied.
- **Joint-local rest pose** — each joint's `restTransforms` (on `UsdSkelSkeleton`/`UsdSkelAnimation`)
  is expressed **relative to its parent joint**, not the world — the classic bind-pose skeleton
  hierarchy, unaffected by whatever object the skeleton happens to be parented under in the stage.
- **World-space `bindTransforms`** — the *skeleton's* per-joint transforms at bind time, but
  resolved all the way out to world space (i.e., joint-local rest pose composed up through the
  joint hierarchy and the skeleton's own stage-level xform). This is the space `geomBindTransform`
  and the joint bind transforms must agree in for `UsdSkel`'s skinning equation to be correct.

**This org's ADR-0048 tagged-point convention reuses these exact names, not USD's runtime**:
`{:space :world :xyz [x y z]}` / `{:space :head-local :xyz [x y z]}` / `{:space :bind-pose :xyz [x y
z]}`. Any future `UsdSkel`-adjacent EDN in this repo (or `character`/`vrm`/`skeleton`) should tag
points with one of these three `:space` values rather than inventing new names — `:bind-pose`
corresponds to `geomBindTransform`'s frame, `:head-local` (or any other `*-local` space) corresponds
to a joint-local rest pose expressed relative to its own parent joint, and `:world` corresponds to
resolved `bindTransforms`. This is a naming/documentation decision only; this repo's parser/emitter
above do not read or write `UsdSkel` prims.

## Test

```sh
kbb -M:test
```

`test/usd/core_test.cljk` is self-referential (string/EDN comparisons against this repo's own
emitter and parser). `test/usd/oracle_test.cljk` (ADR-2607101525 D3/D4) additionally validates
against the real Pixar reference implementation — `tools/usd_oracle.py`, a thin driver around the
`pxr` Python bindings (`pip install -r tools/requirements.txt`), shelled out to from JVM-only
tests. Set `USD_ORACLE_PYTHON` to point at a specific interpreter, or install into whatever
`python3` resolves to; CI (`.github/workflows/ci.yml`) installs it automatically. Without a
`pxr`-importable interpreter available, the oracle tests skip (with a printed reason) rather than
silently passing 0 assertions.
