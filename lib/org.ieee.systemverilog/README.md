# kotoba-lang/org-ieee-systemverilog

Zero-dep portable `.cljc` implementation of a simplified subset of
SystemVerilog (IEEE 1800), the verification/design superset of Verilog
(IEEE 1364, see `kotoba-lang/org-ieee-verilog`). Part of the kotoba-lang
EDA standards-substrate reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`).

| Namespace | Purpose |
|---|---|
| `systemverilog.datatype` | 4-state/2-state typed signals, packed struct/union fields, bit-width computation |
| `systemverilog.interface` | interface/modport declarations + dangling-reference validation |
| `systemverilog.class` | minimal class model with single-inheritance field/method resolution |
| `systemverilog.assertion` | immediate assertion model + evaluator |
| `systemverilog.parser` | simplified line-based parser for the above constructs |

## Status

New — simplified subset covering interfaces, classes (fields/methods,
no method bodies), immediate assertions, and 4-state/2-state/packed data
types. Not implemented: constrained-random, coverage, sequences/
properties (SVA temporal operators), packages, parameterized classes.
12 tests / 47 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
