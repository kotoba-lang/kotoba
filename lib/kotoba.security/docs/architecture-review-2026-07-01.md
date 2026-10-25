# Architecture Review - Kotoba Security

Status: proposed review record
Date: 2026-07-01
Scope: `kotoba-lang/kotoba-lang`, `kotoba-lang/kotoba`, `kotoba-lang/aiueos`,
and `kotoba-lang/security`

## Executive Verdict

Kotoba's architecture is directionally strong: the core security strategy is
capability confinement, deny-by-default safe-build, Wasm isolation, package CID
locks, signed identity, and auditable receipts. The design is better than a
typical language/runtime security posture because it treats authority as an
explicit object rather than ambient process privilege.

The architecture is not yet production-assurable. The main issue is not a lack
of security philosophy; it is that several critical controls are still contract
or design-only and have not been wired into end-to-end enforcement, monitoring,
revocation, and release evidence.

## Findings

### F-001 Critical - Package trust is still a contract, not an enforced release boundary

Evidence:

- `ADR-kotoba-package-cid-lock.md` marks the package model as accepted but
  implementation pending.
- Safe package references require repo RID, signed manifest CID, tree CID,
  transitive locks, granted capabilities, and optional component CID.
- `standards-assessment.md` still identifies SBOM/provenance, registry
  governance, signer revocation, and independent reproducibility as gaps.

Risk:

An attacker can exploit the gap between a strong package contract and a weak
installer/build path. If a safe execution path accepts version-only, local path,
unsigned, stale signer, or unverified transitive dependency input, the language
confinement model can run untrusted code with falsely trusted provenance.

Recommendation:

Make package verification a hard admission gate for safe execution:

- reject version-only dependencies;
- reject unsigned or unverifiable manifests;
- reject missing repo RID/tree CID/manifest CID;
- reject dependency capability grants not declared by the package and allowed by
  the caller policy;
- emit a package-verification receipt and attach it to release evidence.

Acceptance criteria:

- negative fixtures for version-only, missing CID, bad signature, bad repo RID,
  stale/revoked signer, and over-capability dependencies fail safe-build;
- a release cannot be marked safe without package verification evidence;
- risk `R-001` can move from `:open` to `:mitigated`.

### F-002 Critical - Key lifecycle and signer revocation are not enforceable yet

Evidence:

- `aiueos/SECURITY.md` states signer registry is a flat list with no expiry,
  revocation, certificate chains, or delegation.
- `key-lifecycle.md` defines states and crypto periods, but this is not yet an
  implementation gate.
- `risk-register.edn` tracks signer revocation/key expiry as `R-002`.

Risk:

A compromised signer or stale delegation can continue to authorize manifests,
packages, audit records, or runtime identities until operators manually edit
policy everywhere. That is too slow for a supply-chain or signing-key incident.

Recommendation:

Add a key-status verification layer shared by package verification, aiueos
manifest verification, audit verification, and release tooling.

Acceptance criteria:

- revoked and expired keys are rejected for new artifacts;
- retired keys verify historical artifacts only;
- compromised signer lookup produces an incident-severity finding;
- key status is included in package and release evidence packets.

### F-003 High - Capability values and dynamic CACAO intersection remain incomplete

Evidence:

- `ADR-safe-capability-language.md` lists capability value passing, effect to
  capability consistency, and CACAO dynamic checking as S4b remaining work.
- Static per-CID checks are strong for literal resources, but dynamic resource
  arguments fall back to broader class-level policy.

Risk:

Static safe-build can prove many properties, but runtime authority still needs
capability values that carry resource/action constraints through function calls
and across host boundaries. Without this, dynamic resource ids can force wider
grants than least privilege wants.

Recommendation:

Promote capability values to a first-class ABI/type concept:

- `GraphReadCap`, `GraphWriteCap`, `InferCap`, and future host caps are passed as
  values rather than ambient strings;
- effect rows must be consistent with capability parameters;
- runtime checks must compute CACAO/grant/local-policy intersection at call time.

Acceptance criteria:

- dynamic graph/model resource calls can be scoped without wildcard grants;
- least-privilege policy generation avoids `*` for capability-valued flows;
- runtime receipt records the concrete capability object used.

### F-004 High - Monitoring and incident response are designed but not exercised

Evidence:

- `continuous-monitoring.md` defines signals and alerts.
- `incident-response.md` defines playbooks.
- `standards-assessment.md` states live alerting, detection metrics, and incident
  drills are still gaps.

Risk:

Containment failures become visible only if receipt pipelines, alert rules, and
operators are already working. Without exercises, the architecture can be secure
in code but slow in response.

Recommendation:

Run two tabletop exercises and one technical alert simulation:

- compromised package signer;
- unauthorized key release;
- host capability denial spike.

Acceptance criteria:

- postmortem records exist in evidence index;
- alert samples include run/component/package ids;
- response gaps are added to the risk register or closed with evidence.

### F-005 High - FIPS/PQC boundaries are correctly non-claimed but not deployable controls

Evidence:

- `fips-validation.md` correctly says Kotoba must not claim FIPS validation
  without a named validated module boundary.
- `pqc-roadmap.md` defines ML-KEM/ML-DSA/SLH-DSA migration targets and
  algorithm-agile metadata.
- `crypto-inventory.edn` is seeded but not generated from implementation.

Risk:

Cryptographic claims can drift ahead of implementation. Long-retention private
data remains exposed to harvest-now-decrypt-later risk until hybrid wrapping and
epoch migration are implemented.

Recommendation:

Separate three policies:

- `crypto-agile`: metadata required, classical allowed;
- `hybrid-required`: long-retention object wrapping requires classical+PQC;
- `fips-required`: only validated providers inside named boundaries.

Acceptance criteria:

- crypto inventory is generated or checked in CI;
- non-FIPS provider is rejected when `:fips-required` is set;
- hybrid envelope test vectors exist for new object epochs.

### F-006 Medium - TCB and side-channel risks are acknowledged but need decision records

Evidence:

- `aiueos/SECURITY.md` states side channels are not addressed and TCB bugs are
  game over.
- `security-architecture.md` marks formal verification and side-channel
  resistance as non-claims.

Risk:

Without explicit deployment profiles, users may assume capability confinement
also covers timing/cache/power leakage or host runtime vulnerabilities. It does
not.

Recommendation:

Define deployment profiles:

- `research`: no side-channel claim;
- `sensitive-local`: host hardening, no co-tenant execution, audit encryption;
- `regulated`: FIPS/provider boundary, SBOM/SLSA, monitoring, key lifecycle;
- `high-assurance`: future formal verification and side-channel controls.

Acceptance criteria:

- README links deployment profiles;
- release notes name the profile and non-claims;
- high-assurance claims are impossible without explicit evidence.

### F-007 Medium - Operational evidence is not yet tied to release blocking

Evidence:

- `operational-evidence.md` defines release evidence packets.
- `evidence-gates.md` lists missing implementation gates for SBOM, SLSA,
  monitoring drills, revoked-key tests, and FIPS-provider tests.

Risk:

Security evidence can remain advisory if releases do not fail when evidence is
missing.

Recommendation:

Introduce release-blocking policy:

- `safe-release` requires conformance, package verification, SBOM, provenance,
  key status snapshot, and open critical/high risk review;
- missing evidence blocks release unless exception register has an unexpired
  security-owner approval.

Acceptance criteria:

- release tooling reads evidence index and exception register;
- missing packet artifacts fail the release gate;
- exception register entries require expiry and owner.

## Architecture Decisions

1. Keep the primary security invariant:
   `identity/delegation ∩ local policy ∩ component manifest ∩ package lock ∩ surface policy ∩ runtime limits`.
2. Treat package verification as part of execution admission, not a separate
   registry nicety.
3. Treat FIPS, PQC, side-channel resistance, and formal verification as explicit
   deployment claims, not default Kotoba properties.
4. Promote monitoring, IR drills, SBOM/SLSA, and key lifecycle from
   documentation to release/evidence gates.
5. Keep `kotoba-lang/security` as the owner of cross-repo assurance state, while
   implementation fixes remain in their respective repos.

## Review Matrix

| Area | Current posture | Review result |
|---|---|---|
| Language confinement | Strong safe-build gates, remaining typed-HIR/cap-value work | Accept with S4b follow-up |
| Runtime confinement | Strong aiueos capability checks, TCB trusted | Accept with monitoring/TCB profile |
| Package supply chain | Strong contract, incomplete enforcement | Must fix before safe production |
| Identity/key lifecycle | Signed manifests exist, lifecycle incomplete | Must fix before broad trust |
| Data confidentiality | Good sealed-store direction, PQC not complete | Accept for current, plan hybrid epochs |
| Governance/IR/monitoring | Designed baseline, not exercised | Must operationalize |
| FIPS/PQC claims | Correctly non-claimed | Keep blocked until evidence exists |

## Next 30 Days

1. Implement package verification gate in safe-build/release path.
2. Add key-status/revocation check to package and aiueos manifest verification.
3. Generate SBOM/provenance for one release candidate.
4. Run compromised-signer tabletop and host-denial alert simulation.
5. Add crypto inventory generation or CI check.

