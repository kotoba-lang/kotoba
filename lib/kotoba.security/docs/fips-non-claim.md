# FIPS Validation — Product-Facing Non-Claim

Status: authoritative non-claim (pairs with [fips-validation.md](fips-validation.md))  
Date: 2026-07-18  
Risk: **R-003 remains OPEN**

## One-line product statement

> **Kotoba / kotoba-lang/security does not claim FIPS 140-2 or FIPS 140-3
> validation for any shipped library, runtime, package, or deployment
> profile as of 2026-07-18.**

Using FIPS-*approved* algorithms (AES-GCM, SHA-256, Ed25519, ML-KEM, ML-DSA,
…) in source code or test vectors is **not** a FIPS-*validated* system.

## What customers / auditors may rely on today

| Claim | Status |
|---|---|
| Crypto-agile envelope metadata (`:envelope/provider`, algorithms) | yes — enforceable |
| Policy mode `:fips-required` fails closed without validated provider flag | yes — fixtures + tests |
| Inventory rejects `:crypto/fips-status :not-claimed` under `:fips-required` | yes |
| Named FIPS 140-3 module + CMVP certificate | **no** |
| Deployment `fips-boundary.edn` with certificate id | **no** |
| Marketing or README language implying “FIPS certified / validated” | **forbidden** |

Deployed repository mode remains `:crypto-agile`
(`policy/crypto-policy.edn`). Enabling `:fips-required` without a named
validated module is a **configuration error**, not compliance.

## Module-boundary checklist (optional, for a future claim)

Only fill when a real CMVP-validated module is selected. Empty = no claim.

| Field | Value (TBD until validated module selected) |
|---|---|
| Module name / version | _absent_ |
| CMVP certificate id | _absent_ |
| Platform / OS | _absent_ |
| Approved mode config evidence | _absent_ |
| Key generation boundary | _absent_ |
| Sign / encrypt / wrap boundary | _absent_ |
| RNG source | _absent_ |
| Runtime proof logs attached | _absent_ |
| Release note names exact boundary | _absent_ |

Acceptance artifacts (from fips-validation.md): `fips-boundary.edn`,
certificate references, algorithm allowlist, non-FIPS rejection tests,
release security note.

## Product language guide

**Allowed**

- “FIPS-aligned design readiness”
- “Policy can require FIPS-validated providers when configured”
- “No FIPS validation claim without deployment evidence”

**Not allowed**

- “FIPS validated / certified / compliant”
- “Meets FIPS 140-3” without certificate + boundary evidence
- Implying ML-KEM/ML-DSA support alone equals FIPS validation

## Cross-references

- Detailed strategy: [fips-validation.md](fips-validation.md)
- Risk register R-003: `registers/risk-register.edn`
- Policy modes: `policy/crypto-policy.edn`, `src/kotoba/security/crypto_policy.cljk`
- Evidence: EV-0004, EV-0011 (policy readiness — not validation)
