# kotoba-lang/ip-xact

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-ip`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI IP Management: IP-XACT component catalog, bus protocol generation,
NoC topology synthesis, and CDC analysis.

**Named `ip-xact`, not `ip`** — `ip` is dangerously ambiguous (IP address
vs. intellectual property) in a large, actively-developed org, same class
of correction as `kami-si` -> `signal-integrity`.

| Namespace | Restored from | Purpose |
|---|---|---|
| `ip-xact.component` | `ip_xact` | IP-XACT component catalog + IEEE 1685-2014 XML export |
| `ip-xact.bus-protocol` | `bus_protocol` | AXI4/APB bus config + Verilog RTL port list generation |
| `ip-xact.noc` | `noc` | Network-on-Chip topology synthesis (mesh/ring/crossbar/tree) |
| `ip-xact.cdc` | `cdc` | Clock Domain Crossing analysis + violation detection |

## Status

Restored — all 4 modules ported from the original 861-line Rust source
(`lib.rs` + `ip_xact.rs` + `bus_protocol.rs` + `noc.rs` + `cdc.rs`), with
all 9 original Rust unit tests mirrored 1:1 in `test/ip_xact_test.cljk`
(+1 smoke test) — 10 tests / 22 assertions, 0 failures. Pure data + pure
functions throughout; no IO/GPU.

`ip-xact.noc` has its own `port-directions` set (north/south/east/west/
local), distinct from `ip-xact.component/port-directions` (in/out/
in-out) — matches the original's two separately-scoped `PortDirection`
enums in different Rust modules.

## Develop

```bash
kbb -M:test
```
