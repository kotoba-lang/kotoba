# kotoba-lang/ic-packaging

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-pkg`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Packaging: IC package modeling, wire bond/flip chip bonding, and
thermal analysis.

**Named `ic-packaging`, not `pkg`** — `pkg` is a generic term (software
package, npm/Debian package, etc.) that would have been confusing, same
class of correction as `kami-si` -> `signal-integrity`. The mistaken
`kotoba-lang/pkg` scaffold was deleted.

| Namespace | Restored from | Purpose |
|---|---|---|
| `ic-packaging.package` | `package` | IC package type (QFP/BGA/CSP/WLCSP/SiP/Chiplet-2.5D/Chiplet-3D) geometry + thermal-resistance estimation |
| `ic-packaging.bonding` | `bonding` | Wire bond / flip chip bonding diagram generation |
| `ic-packaging.thermal` | `thermal` | Junction/case temperature thermal-resistance-network analysis |

## Status

Restored — all 3 modules ported from the original 359-line Rust source
(`lib.rs` + `package.rs` + `bonding.rs` + `thermal.rs`), with all 6
original Rust unit tests mirrored 1:1 in `test/ic_packaging_test.cljk`
(+1 smoke test) — 6 tests / 10 assertions, 0 failures. Pure data + pure
functions throughout; no IO/GPU.

## Kotoba bounded profile

`src/ic_packaging/bounded_thermal.kotoba` is a capability-free port of
`ic-packaging.thermal`'s junction/case temperature formula (the simple
thermal-resistance network, including the forced-airflow `1/sqrt(1+v)`
factor). `ic-packaging.package`/`ic-packaging.bonding` stay CLJC (not
reviewed this pass). See
[migration/bounded-thermal-v1.edn](migration/bounded-thermal-v1.edn) for
the full record.

## Develop

```bash
kbb -M:test
```
