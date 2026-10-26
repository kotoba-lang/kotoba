# ADR-0005: Maturity R1 — session report, host-free guests, emit lint

- **Status:** accepted
- **Date:** 2026-07-10
- **Deciders:** kototama maintainers / com-junkawasaki fleet

## Context

kototama.tender already ran real Chicory guests (ADR-2607062330) with
host-import fixtures. Operators still lacked:

1. structured post-run observability (fuel used, limits counters)
2. first-class **host-free** pure-compute path (empty grants)
3. pre-emit lint for known `kotoba wasm emit` pitfalls (defn docstring → arity)
4. a CLI and an honest maturity ladder (R0–R3)

## Decision

Declare **maturity R1** as the current stable level:

- `tender/open-session` + `run-report` + `inspect-module`
- `guest/lint-kotoba-source` + `guest/profile` + `guest/maturity-report`
- CLI: `kbb -M:cli doctor|lint|inspect|run`
- Checked-in host-free fixtures: `fact` (120) and Williams peak-cells proxy (240)
- Document ladder in `docs/maturity.md`

## Consequences

- R1 CI gate remains `kbb -M:test` (now includes guest + maturity suites)
- Browser parity stays R2 (partial); fleet durable loop stays R3 (planned)
- Guest authors must pass lint before emit; docstring-on-defn is a hard fail

## Related

- Superproject ADR-2607062330 (tender Chicory runtime)
- Superproject ADR-2607072400 (aiueos decides / kototama enforces)
