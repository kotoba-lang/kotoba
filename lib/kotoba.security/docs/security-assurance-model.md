# Kotoba-lang repository-wide security assurance rule

This rule applies to every repository in the kotoba-lang organization. The
machine-readable authority is [the assurance model](../policy/security-assurance-model.edn).

## Mandatory report

Every assessment and release report must publish:

1. Security Control Maturity (0–100), not probability of safety.
2. Maturity L0–L4.
3. Grade S–F, subject to critical caps.
4. Release gate: pass, partial, fail, blocked, or not-applicable.
5. Evidence E0–E5.
6. Residual critical gap count.

No scalar score, stars, grade, or heatmap color may be used alone as a claim
that a repository is safe. A score of 66/100 does not mean 66% secure.

| Level | Meaning |
|---|---|
| L0 | Control absent |
| L1 | Design or ADR only |
| L2 | Code and local tests |
| L3 | Boundary enforcement, negative tests, and CI |
| L4 | Signed production evidence and recurring drill |

| Evidence | Meaning |
|---|---|
| E0 | Assertion only |
| E1 | Design or ADR |
| E2 | Unit test |
| E3 | Integration/negative test and CI |
| E4 | Fresh authority-signed production receipt |
| E5 | Independent continuous verification |

## Non-negotiable caps

- Any critical control below 40 caps the grade at C.
- Any critical control below 20 forces the release gate to fail.
- Missing E4 evidence keeps production qualification partial.
- An unresolved critical gap keeps the release gate partial or fail.
- Accepted non-goals are gray/N/A and cannot silently become green.

The score prioritizes engineering. The gate authorizes release. Residual risk
is separately evaluated as likelihood × impact × exposure.

## Current stack

| Repository | Score | Level | Grade | Gate | Evidence |
|---|---:|---:|---:|---|---:|
| kagi | 78 | L3 | B | Partial | E3 |
| compiler | 69 | L3 | B | Partial | E3 |
| kotoba | 66 | L3 | B | Partial | E3 |
| aiueos | 63 | L3 | B | Partial | E3 |
| kototama | 60 | L3 | B | Partial | E3 |
| kotoba-lang | 60 | L3 | B | Partial | E3 |
| kotobase | 60 | L3 | B | Partial | E3 |
| kagitaba | 61 | L3 | B | Partial | E3 |

## Security heatmap

Legend: 🟢 ≥80, 🟡 60–79, 🟠 40–59, 🔴 0–39, ◻️ N/A/non-goal.

| Control | kotoba | language | kototama | kotobase | aiueos | compiler | kagi | kagitaba |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zero trust | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟠 |
| Capability | 🟢 | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟡 |
| PQC | 🟠 | 🟠 | 🟠 | 🟡 | 🟠 | 🟠 | 🟢 | 🟠 |
| HSM | 🟠 | 🟠 | 🟠 | 🟠 | 🟠 | 🟠 | 🟢 | 🟠 |
| Monitoring/recovery | 🟡 | 🟠 | 🟡 | 🟡 | 🟡 | 🟠 | 🟢 | 🟡 |
| Transport C/I | 🟡 | 🟡 | 🟢 | 🟠 | 🟡 | 🟠 | 🟢 | 🟠 |
| Anti-impersonation | 🟢 | 🟡 | 🟡 | 🟠 | 🟡 | 🟢 | 🟢 | 🟡 |
| ABAC | 🟢 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 |
| Authorized abuse | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 |
| Software tamper | 🟡 | 🟢 | 🟠 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 |
| Private-key theft | 🟡 | 🟠 | 🟠 | 🟠 | 🟠 | 🟡 | 🟢 | 🟠 |
| Memory corruption | 🟠 | 🟡 | 🟡 | 🟠 | 🟡 | 🟢 | 🟠 | 🟡 |
| DoS | 🟡 | 🟠 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 |
| Information flow | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| Insider threat | 🟡 | 🟡 | 🟡 | 🟡 | 🟠 | 🟡 | 🟢 | 🟡 |
| Unknown compromise | 🟡 | 🟡 | 🟠 | 🟡 | 🟡 | 🟢 | 🟢 | 🟡 |
| Quantum communication | ◻️ | ◻️ | ◻️ | ◻️ | ◻️ | ◻️ | ◻️ | ◻️ |
| Unrecoverable loss | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 |

Colors aid navigation; exact values and evidence in
[the score register](../registers/stack-security-score.edn) remain authoritative.
