# kotoba-lang/org-ibis

Zero-dep portable `.cljc` implementation of IBIS (I/O Buffer Information
Specification), published by the IBIS Open Forum (ibis.org). IBIS
describes I/O buffer electrical behavior (driver/receiver V-I curves,
ramp rates, package parasitics) so board-level signal-integrity tools can
simulate I/O behavior without exposing transistor-level IP. Part of the
kotoba-lang EDA standards-substrate reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`).

Named `org-ibis` (no spec suffix) because the IBIS Open Forum's only
published spec is IBIS itself, same pattern as `org-materialx`/
`org-openusd`/`org-ros`/`org-signal`.

| Namespace | Purpose |
|---|---|
| `ibis.component` | Component/Pin/Package model with RLC package parasitics |
| `ibis.model` | Model section: V-I curve tables (pulldown/pullup/power-clamp/gnd-clamp), ramp rate, linear V-I interpolation |
| `ibis.parser` | Simplified `.ibs`-format section parser |

Related: `kotoba-lang/signal-integrity` (consumes I/O buffer models for
crosstalk/eye-diagram analysis; not yet wired as a code dependency).

## Status

New — simplified subset of IBIS covering single-ended buffer models
(Component/Pin/Model/V-I-tables/Ramp). Not implemented: differential pin
mapping, series models, submodels, multi-lingual IBIS extensions. 11 tests
/ 42 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
