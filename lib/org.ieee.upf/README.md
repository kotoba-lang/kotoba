# kotoba-lang/org-ieee-upf

Zero-dep portable `.cljc` implementation of a simplified subset of UPF
(Unified Power Format, IEEE 1801) — power intent for low-power IC
design: power domains, supply networks, power states, and isolation/
level-shifter strategies for power-gated blocks. Part of the
kotoba-lang EDA standards-substrate reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`).

| Namespace | Purpose |
|---|---|
| `upf.domain` | create_power_domain model + longest-prefix instance-to-domain lookup |
| `upf.supply` | supply port/net/connection model + net-voltage-path tracing |
| `upf.power-state` | add_power_state model + all-off-state detection |
| `upf.strategy` | isolation/level-shifter strategy model + domain-applicability filtering |
| `upf.parser` | simplified TCL-style command parser for the above |

## Status

New — simplified subset covering power domains, supply ports/nets,
power states, and isolation/level-shifter strategies. Not implemented:
UPF's full command set (set_retention, map_power_switch, save_upf,
load_upf, and most of the ~100 other UPF commands). 13 tests / 37
assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
