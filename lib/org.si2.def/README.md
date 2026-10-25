# kotoba-lang/org-si2-def

Zero-dep portable `.cljc` implementation of a simplified subset of DEF
(Design Exchange Format), published by Si2 (Silicon Integration
Initiative, si2.org) — the companion format to LEF
(`kotoba-lang/org-si2-lef`): LEF describes reusable standard-cell/IP
physical abstracts, DEF describes an actual placed-and-routed design
instance. Part of the kotoba-lang EDA standards-substrate reverse-domain
naming initiative (ADR-2607072500, `com-junkawasaki/root`). Kept as a
separate repo from LEF, mirroring the `org-khronos-gltf`/`org-khronos-glb`
companion-pair precedent.

Namespace root is `def-format` (not `def`) to avoid colliding with the
Clojure special form.

| Namespace | Purpose |
|---|---|
| `def-format.design` | top-level DESIGN/UNITS/DIEAREA model + area computation |
| `def-format.component` | COMPONENTS placement model + placed-instance filtering |
| `def-format.net` | NETS connectivity + routed-wire model, fanout computation |
| `def-format.row` | ROWS/TRACKS placement-grid model, row-width computation |
| `def-format.parser` | simplified section-based parser for the above |

## Status

New — simplified subset covering DESIGN/UNITS/DIEAREA headers,
COMPONENTS placement, NETS connectivity + simplified routed-wire
geometry, and ROWS/TRACKS. Not implemented: SPECIALNETS, GCELLGRID,
VIAS, PROPERTYDEFINITIONS, most of DEF's other sections. 7 tests / 40
assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
