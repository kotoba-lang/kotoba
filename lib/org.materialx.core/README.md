# kotoba-lang/org-materialx

(renamed from `kotoba-lang/materialx` 2026-07-05 — reverse-domain naming for
an external-spec-name repo, materialx.org, same ADR-2607041500 rename
precedent as `org-khronos-glb`/`org-khronos-gltf`/`org-openusd`.)

MaterialX XML builders — plus (ADR-0048 §4, `com-junkawasaki/root`) a real standard
node-definition table, a dependency-free `.mtlx` XML parser, and a bridge to
kami-engine's EDN render-IR `:materials` vocabulary (ADR-0044).

Namespaces:

- `materialx.core`
- `kotoba.materialx`

## What's in here

- `materialx` / `value` — the original hiccup-based `<materialx>` document emitter (unchanged).
- `node-defs` — a curated table of real MaterialX standard nodedefs (port names / types /
  defaults copied from AcademySoftwareFoundation/MaterialX's own `libraries/bxdf/
  standard_surface.mtlx` + `libraries/stdlib/stdlib_defs.mtlx`), scoped to a game-engine PBR
  pipeline: `ND_standard_surface_surfaceshader` (the full real ~40-input uber-shader),
  `ND_image_{float,color3,vector3}`, `ND_normalmap_float`, `ND_{multiply,add,mix}_
  {float,color3,vector3}` (+ `ND_multiply_color3FA`), `ND_position_vector3`, `ND_normal_vector3`,
  `ND_texcoord_vector2`. Not the full spec — see the ADR for the "not covered" list
  (color4/vector2/vector4/matrix/integer overload variants, most non-PBR nodegroups, binary/USD
  composition).
- `parse-xml` — a small dependency-free XML→hiccup parser (elements/attributes/comments/the
  `<?xml?>` decl; no CDATA/namespaces/DOCTYPE), `xml.core/xml`'s missing inverse.
- `materialx->node-graph` / `node-graph->materialx` — a `.mtlx` XML document ⇄ an EDN node-graph
  (nodes keyed by name, `:type` resolved against `node-defs` when recognized — unrecognized nodes
  like `<tiledimage>`/`<place2d>` still parse structurally as a raw passthrough, never silently
  dropped).
- `materialx-node-graph->render-ir-material` / `render-ir-material->materialx-node-graph` — bridge
  to the ADR-0044 render-IR `:materials` vocabulary, **`:model :pbr` only**. VRM MToon has no
  MaterialX standard-node equivalent; the inverse function throws rather than faking one.

## Test

```sh
kbb -M:test
```
