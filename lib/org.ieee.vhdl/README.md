# kotoba-lang/org-ieee-vhdl

Zero-dep portable `.cljc` implementation of a simplified subset of VHDL
(IEEE 1076), the hardware description language. Part of the kotoba-lang
EDA standards-substrate reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`). Sibling to
`kotoba-lang/org-ieee-verilog` (IEEE 1364) and
`kotoba-lang/org-ieee-systemverilog` (IEEE 1800) — VHDL and Verilog are
independent, unrelated HDLs (not variants of each other), each modeled
in its own repo.

| Namespace | Purpose |
|---|---|
| `vhdl.entity` | entity/port declarations, bus-width parsing |
| `vhdl.signal` | signal declarations + type-default-value resolution |
| `vhdl.architecture` | architecture body: signals + processes, combinational-vs-sequential heuristic |
| `vhdl.parser` | simplified line-based parser for entity/architecture/signal/process |

## Status

New — simplified subset covering entity/port declarations, signal
declarations for std_logic/std_logic_vector/integer/boolean, and
process blocks (sensitivity list + statement count, no statement
semantics). Not implemented: generics, generate statements, packages,
configurations, VHDL-2008 fixed/floating-point types. 11 tests / 38
assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
