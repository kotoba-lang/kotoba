# kotoba-lang/org-si2-openaccess

Zero-dep portable `.cljc` implementation of core OpenAccess concepts,
published by Si2 (Silicon Integration Initiative, si2.org) — the
industry-standard IC design database (in reality a large C++ API/schema
used by virtually every commercial place-and-route/custom-layout tool).
This restoration models a small, static, EDN-native SUBSET of the
object model (Lib/Cell/View hierarchy, geometric shapes, hierarchical
instances with 2D transforms) — not the real OpenAccess C++ API, and
not a database engine (no persistence, no incremental update, no
callbacks). Part of the kotoba-lang EDA standards-substrate
reverse-domain naming initiative (ADR-2607072500, `com-junkawasaki/root`).

| Namespace | Purpose |
|---|---|
| `openaccess.library` | Lib/Cell/View hierarchy + lookup functions |
| `openaccess.shape` | Rect/Polygon/Path geometry + bounding-box computation |
| `openaccess.design` | View contents (shapes + instances) + 2D instance-transform math (8 Manhattan orientations) |
| `openaccess.query` | bounding-box/layer-filter/one-level-flatten queries composing the above |

## Status

New — simplified static object model covering library/cell/view
hierarchy, 3 shape kinds, hierarchical instances with correct 2D
transform math for all 8 Manhattan orientations, and one-level
instance flattening. Not implemented: the real OpenAccess C++ API
surface, persistence/database semantics, parasitic/electrical views,
multi-level flattening, non-Manhattan (arbitrary-angle) transforms. 13
tests / 41 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
