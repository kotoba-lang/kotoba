# kotoba-lang/org-si2-lef

Zero-dep portable `.cljc` implementation of the LEF (Library Exchange
Format) physical-abstract layout format (Si2, Silicon Integration
Initiative, si2.org — the industry-standard format for standard-cell/IP
physical abstracts, companion to DEF which describes the placed-and-routed
design). Extracted from `kotoba-lang/pdk` into its own repo as part of the
kotoba-lang `org-<standards-body>-<spec>` reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`). See also `kotoba-lang/org-si2-def`
for the companion DEF format.

| Namespace | Purpose |
|---|---|
| `lef.core` | LEF macro/pin/obs physical-abstract model + simplified token-based parser recognizing MACRO/CLASS/SIZE/SYMMETRY/SITE/PIN/DIRECTION/OBS/LAYER/RECT/END |

## Status

Simplified parser — recognizes a practical subset of LEF syntax (MACRO
geometry, pin ports, obstruction rects), not full LEF grammar conformance
(no vias, no antenna rules, no density rules). 1 test / 8 assertions.
Consumed by `kotoba-lang/pdk` for standard-cell physical-abstract lookups.

## Develop

```bash
kbb -M:test
```
