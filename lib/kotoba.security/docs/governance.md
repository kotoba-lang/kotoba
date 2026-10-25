# Security Governance

Status: proposed baseline
Date: 2026-07-01

## Purpose

Governance turns Kotoba's security design into accountable decisions,
exceptions, evidence, and periodic reassessment. A strong language/runtime model
is not enough: security posture must be owned, reviewed, and measured.

## Governance Model

| Role | Responsibility | Evidence |
|---|---|---|
| Security owner | Accepts security posture, risk appetite, and exceptions | signed review notes, risk acceptances |
| Language owner | Owns safe Kotoba source/profile semantics | profile ADRs, conformance results |
| Runtime owner | Owns Wasm host, aiueos broker, resource limits | runtime tests, host-call audit |
| Package owner | Owns registry, package locks, signing policy | lock conformance, signer registry |
| Crypto owner | Owns key lifecycle, FIPS/PQC policy, crypto inventory | key register, crypto inventory |
| Operations owner | Owns monitoring, IR, recovery, evidence retention | alerts, incident records, drills |

One person can hold multiple roles in early-stage Kotoba, but every security
decision must name the role that accepted it.

## Security Decision Classes

| Class | Examples | Required review |
|---|---|---|
| Host capability | new import, new egress path, new secret source | language + runtime + security |
| Crypto change | new algorithm, key length, envelope format | crypto + security |
| Package trust | new signer, registry rule, lockfile exception | package + security |
| Runtime boundary | aiueos broker change, memory/fuel policy | runtime + security |
| Data exposure | public metadata, audit retention, receipt export | operations + security |
| Exception | temporary classical-only signature, unsigned package | security owner approval with expiry |

## Cadence

- Weekly while pre-production: review open critical/high risks and failed gates.
- Monthly: update risk register, exception register, key register, and evidence
  index.
- Per release: run evidence gates, generate SBOM/provenance, review FIPS/PQC
  non-claims, and sign a release security note.
- Per major architecture change: update DoDAF products and threat model.

## Required Registers

- [Risk Register](../registers/risk-register.edn)
- [Exception Register](../registers/exception-register.edn)
- [Key Register](../registers/key-register.edn)
- [Evidence Index](../registers/evidence-index.edn)
- [Crypto Inventory](../registers/crypto-inventory.edn)

## Risk Acceptance Rule

No risk can be marked accepted without:

- risk id;
- owner role;
- affected assets;
- impact and likelihood;
- compensating controls;
- expiration date;
- review evidence.

Accepted risks expire by default after 90 days unless a shorter period is
required by the control owner.

## Control Objectives

| Objective | Target |
|---|---|
| Least privilege | no host import or dependency capability without explicit policy |
| Accountability | every grant, denial, run, and key release has a receipt |
| Reproducibility | source/profile/package gates produce repeatable evidence |
| Crypto agility | all new security envelopes carry algorithm metadata |
| Operational readiness | IR, monitoring, backup, and recovery are exercised |
| Honest claims | no FIPS/NIST/PQC compliance claim without matching evidence |

## Release Security Note

Every release should record:

- commit/release id;
- SBOM location and digest;
- provenance statement location and digest;
- conformance gate results;
- package lock gate results;
- known unresolved critical/high risks;
- crypto/FIPS/PQC claim status;
- security owner sign-off.

