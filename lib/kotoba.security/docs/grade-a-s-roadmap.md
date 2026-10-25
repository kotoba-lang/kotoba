# Grade A / S roadmap

This roadmap moves all eight repositories from the current Grade B baseline to
Grade A and then Grade S. The machine-readable authority is
[`policy/grade-a-s-roadmap.edn`](../policy/grade-a-s-roadmap.edn).

## Promotion contract

| Target | Score | Critical controls | Maturity | Evidence | Gate | Residual critical gaps |
|---|---:|---:|---:|---:|---|---:|
| A | ≥80 | every control ≥60 | L4 | E4 | Partial or Pass | tracked |
| S | ≥90 | every control ≥80 | L4 | E5 | Pass | 0 |

A score alone is insufficient. Grade A requires signed production evidence and
scheduled drills. Grade S additionally requires independent continuous
verification, a passing release gate, and no residual critical gaps.

## Phase 0 — freeze measurement semantics

`quantum-communication` is currently displayed gray as N/A/non-goal but still
contributes zero to the weighted score. Before raising another score, publish
assurance model v2 with one explicit rule:

1. Prefer excluding explicitly accepted N/A controls and renormalizing declared
   weights.
2. Publish old and new baselines side by side.
3. Never convert a real gap to N/A.
4. Require semantic tests and score provenance for every migration.

This is a measurement correction, not retroactive security credit.

## Shared critical path

```text
W0 measurement model
  → W1 signed production evidence plane
    ├→ W2 real hybrid PQC provider and rotation
    ├→ W3 HSM/platform-provider qualification
    │   ├→ W4 production CA, mTLS, workload identity
    │   └→ W5 geo-recovery and destructive restore
    ├→ W6 insider-resistant governance
    ├→ W7 reproducible supply chain
    └→ W8 fuzzing, memory, resource and load bounds
          ↓
       W9 live detection, containment, restore, red-team retest
          ↓
       all repos A → all repos S
```

The shared implementations belong in `kotoba-lang/security`; repositories own
only their boundary adapters and production evidence.

## Repository order

| Repository | Now | A gap | S gap | First priorities |
|---|---:|---:|---:|---|
| kagi | 78/B | +2 | +12 | memory safety, DoS, provider qualification |
| compiler | 69/B | +11 | +21 | HSM, transport, monitoring, PQC, recovery |
| kotoba | 66/B | +14 | +24 | HSM, PQC, memory safety, detection |
| aiueos | 63/B | +17 | +27 | HSM, key theft, PQC, insider resistance |
| kagitaba | 61/B | +19 | +29 | HSM, transport, PQC, key theft, recovery |
| kotoba-lang | 60/B | +20 | +30 | HSM, monitoring, key theft, PQC, DoS |
| kototama | 60/B | +20 | +30 | HSM, key theft, PQC, tamper resistance |
| kotobase | 60/B | +20 | +30 | HSM, key theft, transport identity, memory |

Start with kagi because it supplies keys, PQC, recovery, and receipts to the
rest of the stack. Next qualify the shared evidence plane and provider APIs;
then advance consumer repositories in dependency order. Point gaps are planning
deltas from the current rounded score, not estimates of engineering effort.

## Grade A milestone

For every repository:

- ≥80 weighted score after the model-v2 dual-baseline review;
- no critical control below 60;
- L4 production qualification;
- E4 authority-signed, fresh, artifact-bound receipts;
- real ML-KEM-768 plus classical hybrid on applicable production paths;
- qualified non-exportable hardware custody with rotation and outage drills;
- production mTLS/workload identity and revocation evidence;
- independent encrypted immutable backups and measured destructive restore;
- live alert delivery and named on-call ownership.

## Grade S milestone

Grade S is not “more unit tests.” It requires:

- ≥90 score and every critical control ≥80;
- E5 evidence from an independent continuous verifier;
- Gate Pass and zero residual critical gaps;
- automated isolation, credential revocation, write freeze, known-clean restore,
  and post-restore verification;
- multi-region/provider-loss chaos drills;
- independent red-team findings closed and retested;
- continuous SBOM/provenance, key/certificate status, telemetry integrity, and
  recovery-SLO verification.

## Explicit non-claims

- Apple Secure Enclave signing is not a general HSM or PQ KEM provider.
- A hybrid metadata gate is not proof that ML-KEM ran.
- A simulated or CI receipt is not E4.
- An internal continuous test is not independent E5.
- A grade is neither a probability of safety nor release authorization.
