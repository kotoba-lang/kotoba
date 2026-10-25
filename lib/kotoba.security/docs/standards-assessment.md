# Standards Assessment

Status: proposed baseline
Date: 2026-07-01

## Verdict

Kotoba is aligned with the technical direction of modern zero-trust,
least-privilege, supply-chain, and accountability guidance. With the
`kotoba-lang/security` baseline, it now has a design for governance, incident
response, monitoring, risk management, key lifecycle, FIPS boundaries,
SBOM/SLSA, and operational evidence. It still does not "satisfy NIST" as a
complete program until those designs are implemented, exercised, monitored, and
assessed with deployment evidence.

The right claim today is:

```text
Kotoba has strong design alignment and an assurance design baseline.
Kotoba does not yet have complete implementation and compliance evidence.
```

## NIST CSF 2.0

| Function | Current alignment | Gaps |
|---|---|---|
| Govern | Governance roles, decision classes, risk/exception registers, release sign-off | named owners and actual review evidence |
| Identify | CID objects, repo RID, manifests, component graphs, crypto/key registers | full deployment asset inventory and data classification catalog |
| Protect | deny-by-default capabilities, Wasm sandbox, key lifecycle, FIPS/PQC strategy | live key rotation, FIPS provider enforcement, secrets runbooks |
| Detect | monitoring signals, alert rules, audit receipts, denial/trap events | live alerting, detection coverage metrics, alert drills |
| Respond | IR severity model, playbooks, evidence preservation | exercised incident drills and comms workflow |
| Recover | content addressing, deterministic builds, release evidence packets | backup/restore objectives and disaster recovery exercises |

## NIST SP 800-53 Rev. 5 Control Families

High-alignment families:

- AC Access Control: capability grants, least privilege, per-resource checks.
- AU Audit and Accountability: run receipts, access receipts, signed commits.
- CM Configuration Management: manifests, lockfiles, deterministic build inputs.
- IA Identification and Authentication: DID, signer registry, CACAO delegation.
- SC System and Communications Protection: Wasm isolation, encrypted objects,
  import confinement.
- SI System and Information Integrity: conformance tests, package integrity,
  trap/denial evidence.
- SR Supply Chain Risk Management: CID locks, repo RID, signer authority,
  transitive dependency locks.

Families now designed but still requiring implementation evidence:

- AT Awareness and Training: governance can assign ownership, but training
  artifacts are not present.
- CP Contingency Planning: evidence packets exist, but no recovery plans or
  exercises.
- IR Incident Response: playbooks exist, but no drill/postmortem evidence.
- PE Physical and Environmental Protection: out of scope.
- PL Planning / PM Program Management: governance baseline exists, but owners
  have not signed off.
- RA Risk Assessment: seed risk register exists, but it is not yet operated.

## NIST SP 800-207 Zero Trust

Kotoba maps well to resource-centric zero trust:

- resources are graph/model/package/component objects, often CID-addressed;
- every host call is intended to be evaluated by policy and context;
- network location is not authority;
- grants are scoped and can be attenuated.

Main gaps:

- continuous policy decision point telemetry is not specified across all hosts;
- device/user posture is not modeled for enterprise deployments;
- revocation latency and cached grants need explicit bounds.

## NIST SP 800-218 SSDF

Good alignment:

- source conformance fixtures;
- negative tests for unsafe language forms;
- deterministic build evidence;
- package lock contract;
- implementation gates in CI.

Gaps:

- secure development roles and training;
- vulnerability intake and disclosure workflow;
- SBOM/VEX generation is specified but not implemented;
- release signing and provenance are specified but not enforced across every
  artifact;
- dependency update policy and vulnerability triage SLA.

## NIST SP 800-161 C-SCRM

Good alignment:

- repo RID plus signed package manifest;
- source tree CID and component CID;
- transitive dependency lock entries;
- package capabilities declared separately from granted capabilities.

Gaps:

- supplier risk tiers;
- registry governance;
- signer revocation is designed but not implemented end-to-end;
- compromised package response;
- independent reproducibility verification.

## NIST SP 800-57 Key Management

Good alignment:

- key epoch and rotation concepts exist in storage/custody design;
- t-of-N custody reduces single-key failure;
- algorithm-agile envelope metadata is planned.

Gaps:

- key states and crypto periods are designed, but archival/destruction and
  escrow procedures need deployment evidence;
- KMS/HSM integration;
- formal separation between signing, wrapping, encryption, and audit keys;
- PQC transition inventory is seeded but not generated from implementation.

## NIST PQC Standards

As of the current NIST standards, production PQC primitives to track are:

- FIPS 203: ML-KEM for key establishment;
- FIPS 204: ML-DSA for signatures;
- FIPS 205: SLH-DSA for stateless hash-based signatures.

Kotoba has a design target for hybrid classical plus PQ envelopes, but no
complete implementation claim should be made yet.

## DoDAF 2.02

DoDAF is an architecture description framework, not a security control catalog.
Kotoba can use it to structure architecture evidence:

- AV: scope, vocabulary, assumptions;
- CV: capability taxonomy and roadmap;
- DIV: EDN/Datom/CID/WIT data model;
- OV: operational activities such as build, grant, run, audit, recover;
- SvcV: host services, package registry, custody, runtime broker;
- SV: runtime systems and deployment nodes;
- StdV: NIST, W3C DID, CACAO, WIT, Wasm, FIPS references;
- PV: migration plan and milestones.
