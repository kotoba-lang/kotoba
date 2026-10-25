# Security assurance model v2

Model v2 resolves the mismatch between the gray `quantum-communication`
control and its former zero contribution to the aggregate score. The control is
an explicit accepted non-goal (G-009), so v2 excludes it and renormalizes the
declared weights of the remaining 17 controls.

This is a measurement correction, not evidence that any implementation became
safer. A missing, open, partial, or unevidenced control remains applicable and
cannot be excluded. The accepted-N/A set is versioned in
[`security-assurance-model-v2.edn`](../policy/security-assurance-model-v2.edn)
and must agree with the authoritative gap register.

## Dual baseline

| Repo | v1 | v2 | v2 numeric band | Operational grade |
|---|---:|---:|---|---|
| kotoba | 66 | 69 | B | B |
| kotoba-lang | 60 | 64 | B | B |
| kototama | 60 | 64 | B | B |
| kotobase | 60 | 64 | B | B |
| aiueos | 63 | 67 | B | B |
| compiler | 69 | 73 | B | B |
| kagi | 78 | 83 | A | B |
| kagitaba | 61 | 64 | B | B |

The machine-readable authority is
[`stack-security-dual-baseline.edn`](../registers/stack-security-dual-baseline.edn).
Kagi crosses the numeric A threshold under v2, but remains operational Grade B:
it has L3/E3 rather than the roadmap's required L4/E4. Numeric band, maturity,
evidence, critical-control floors, residual gaps, and release gate must all be
reported separately. A scalar score is neither a probability of safety nor a
release authorization.
