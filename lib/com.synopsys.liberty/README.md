# kotoba-lang/org-synopsys-liberty

Zero-dep portable `.cljc` implementation of the Liberty (.lib) timing
library format (Synopsys, the de facto standard for standard-cell timing
characterization consumed by STA/synthesis tools industry-wide). Extracted
from `kotoba-lang/pdk` into its own repo as part of the kotoba-lang
`org-<standards-body>-<spec>` reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`).

| Namespace | Purpose |
|---|---|
| `liberty.core` | Liberty (.lib) timing library model (library/cell/pin/timing-arc) + simplified line-based parser recognizing `library`/`cell`/`pin`/`timing` blocks and their key attributes |

## Status

Simplified parser — recognizes a practical subset of Liberty syntax
(library/cell/pin/timing blocks, nom_voltage/nom_temperature/time_unit/
area/cell_leakage_power/direction/capacitance/function/related_pin
attributes), not full Liberty grammar conformance. 1 test / 5 assertions.
Consumed by `kotoba-lang/pdk` for standard-cell library timing lookups.

## Develop

```bash
kbb -M:test
```
