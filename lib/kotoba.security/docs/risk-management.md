# Risk Management

Status: proposed baseline
Date: 2026-07-01

## Purpose

Kotoba needs a maintained risk register because several security properties are
design targets but not yet complete implementation evidence.

## Risk Taxonomy

| Category | Examples |
|---|---|
| Language confinement | unsafe form bypass, wrong effect inference, missing host import classification |
| Runtime confinement | host adapter bug, import materialization error, resource-limit bypass |
| Supply chain | unsigned package, compromised signer, registry tampering |
| Cryptography | weak algorithm, expired key, missing revocation, non-FIPS module |
| Data protection | metadata leak, unencrypted blob, failed key rotation |
| Operations | missing alert, failed audit sink, incomplete incident response |
| Governance | unowned exception, stale control evidence, inaccurate compliance claim |

## Scoring

Impact and likelihood are scored 1 to 5.

```text
risk_score = impact * likelihood
critical = 20-25
high     = 12-19
medium   = 6-11
low      = 1-5
```

## Required Risk Fields

Each risk entry must include:

- `:risk/id`
- `:risk/title`
- `:risk/category`
- `:risk/affected-assets`
- `:risk/impact`
- `:risk/likelihood`
- `:risk/score`
- `:risk/status`
- `:risk/owner`
- `:risk/mitigations`
- `:risk/evidence`
- `:risk/review-by`

## Initial Risk Backlog

The seed register in `registers/risk-register.edn` tracks:

- incomplete key lifecycle and signer revocation;
- no FIPS validation claim/evidence;
- package lock enforcement not complete end-to-end;
- PQC migration not implemented;
- incomplete monitoring and IR drills;
- side-channel non-coverage;
- incomplete SBOM/SLSA release evidence.

## Review Rules

- Critical risks: review weekly until mitigated or explicitly accepted.
- High risks: review monthly.
- Accepted risks: expire within 90 days.
- Any risk affecting released artifacts requires a release security note entry.

