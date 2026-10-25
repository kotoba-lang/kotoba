# DoDAF 2.02 Viewpoints for Kotoba Security

Status: proposed baseline
Date: 2026-07-01

## Purpose

Use DoDAF to keep Kotoba's security architecture reviewable across language,
runtime, package, storage, and operating-system layers. DoDAF is used here as an
architecture evidence format, not as a claim of DoD accreditation.

## Minimal Architecture Products

| Viewpoint | Kotoba security product |
|---|---|
| AV-1 | Security architecture scope, assumptions, stakeholders |
| AV-2 | Vocabulary: CID, DID, CACAO, Grant, Capability, Receipt, RID |
| CV-1 | Security capability vision: confined language to auditable mesh |
| CV-2 | Capability taxonomy: build, grant, run, store, audit, recover |
| CV-6 | Capability-to-control mapping against NIST CSF/SP 800 families |
| DIV-1 | Conceptual data model for package, grant, manifest, receipt |
| DIV-2 | Logical EDN/Datom/WIT schema model |
| DIV-3 | Physical file/schema locations and CID layouts |
| OV-5b | Operational activities: safe-build, verify manifest, launch, trap, audit |
| OV-6c | Event traces: package publish, component run, key release, incident |
| SvcV-1 | Services: compiler gate, broker, registry, custody, audit, storage |
| SvcV-4 | Service dependencies and capability flows |
| SV-1 | Systems: CLI, runtime host, aiueos broker, store, custody, registry |
| SV-6 | System data exchanges: manifests, lockfiles, receipts, envelopes |
| StdV-1 | Standards profile: NIST CSF, SP 800-53, SP 800-207, SP 800-218, PQC |
| PV-2 | Security capability roadmap |

## First Diagram Set

The first architecture review should produce four diagrams:

1. Source-to-Wasm safe-build boundary.
2. aiueos capability broker and host-call enforcement.
3. Package publish/install/lock/sign/verify flow.
4. Private object encryption and access receipt flow.

Each diagram must identify:

- trust boundary;
- authority source;
- cryptographic binding;
- runtime enforcement point;
- audit evidence.

