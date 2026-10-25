# Kotoba Security Architecture

Status: proposed baseline
Date: 2026-07-01

## Security Objective

Kotoba should treat every program, dependency, agent output, component, package,
peer, and transport as untrusted unless a small, explicit, auditable capability
chain grants access to a specific resource.

The primary invariant is:

```text
effective access =
  identity/delegation
  intersect local policy
  intersect component manifest
  intersect package lock
  intersect surface policy
  intersect runtime limits
```

No single artifact is sufficient authority. CID proves bytes, not current trust.
DID proves a principal, not resource authorization. CACAO proves delegated
intent, not local permission. A package manifest declares requested
capabilities, not granted capabilities.

## Trust Boundaries

| Boundary | Trust assumption | Required control |
|---|---|---|
| Source to compiler | Source may be hostile or AI-generated | safe subset, effect gate, type gate, capability policy |
| Compiler to Wasm | Compiler is trusted until self-host slices replace it | deterministic build, conformance suite, signed release |
| Wasm guest to host | Guest is untrusted | import table is capability-derived only |
| Package to execution | Dependency may be malicious | lock by repo RID, manifest CID, tree CID, signer, component CID |
| Component to aiueos | Component may be hostile | manifest verification, runtime host-call checks, fuel, memory pages |
| Peer/transport to data | Transport is untrusted | content addressing, signature verification, encryption envelope |
| Storage to confidentiality | Public replication is allowed | ciphertext-only replication, recipient/epoch key policy |
| Audit to accountability | Operators may be faulty | hash-linked receipts, signed commits, anchors, evidence retention |

## Defense Model

### 1. Language confinement

Safe Kotoba is not "arbitrary Clojure with linting." It is a Wasm-targeted,
capability-safe profile with a small accepted source contract. Required controls:

- deny `eval`, runtime `require`, ambient host interop, raw filesystem/network,
  reflection, dynamic loading, and unsafe memory primitives from user code;
- infer and check host effects transitively through the call graph;
- bind graph/model/resource access at capability class and resource-id level;
- treat `kotoba -e` as compile-and-run sugar, not runtime eval;
- keep conformance fixtures independent from the compiler crate.

### 2. Runtime confinement

The runtime must not bind a full host world and rely on guest cooperation. It
must instantiate only imports authorized by policy, then check host calls at the
broker boundary.

Required controls:

- no ambient `fetch`, filesystem, DOM, process, environment, secrets, random, or
  clock access;
- fuel and epoch interruption for CPU;
- memory-page caps for RAM;
- per-topic/per-resource checks where coarse capabilities are not enough;
- run receipts for grants, denials, traps, inputs, outputs, and parent receipts.

### 3. Supply-chain confinement

Package safety is the combination of integrity, authority, and least privilege.

Required controls:

- package references must lock name, version, repo RID, manifest CID, source tree
  CID, optional Git commit, signer DIDs, requested capabilities, transitive deps,
  and optional component CID;
- name plus semver is non-conforming for safe execution;
- dependency capabilities are denied unless the package requested them, the
  lockfile carries them, and the caller policy grants them;
- registry records are convenience indexes, not root trust.

### 4. Identity and delegation

DID/CACAO/Grant/aiueos must remain separate layers:

- DID: principal and verification relationship;
- CACAO: signed external delegation envelope;
- Kotoba Grant: typed resource/action/constraint capability;
- aiueos: local policy decision and runtime materialization.

### 5. Data confidentiality and accountability

Selective replication is not a confidentiality boundary. Private content must be
encrypted objects, with public metadata treated as intentionally visible.

Required controls:

- ciphertext CID for replication;
- plaintext CID only inside authority-scoped metadata;
- algorithm-agile envelope metadata: `alg`, `hash`, `sig`, `kem`, `key-id`,
  `recipient-set`, `epoch`, `created-at`;
- epoch rotation for future writes after revocation;
- access receipts for key release and non-public reads;
- signed and hash-linked audit records.

### 6. Governance and operations

Technical confinement must be paired with operating controls:

- named control owners for language, runtime, package, crypto, operations, and
  security acceptance;
- maintained risk, exception, key, crypto, and evidence registers;
- incident response playbooks for safe-build bypass, signer compromise,
  unauthorized key release, and host escape;
- monitoring for grants, denials, traps, package verification, key events, and
  audit sink failures;
- release evidence packets containing SBOM, provenance, conformance results,
  package verification, known risks, exceptions, key status, and sign-off.

## Non-Claims

Kotoba should not claim any of the following until evidence exists:

- FIPS 140-3 validated cryptographic module usage;
- complete NIST SP 800-53 compliance;
- complete NIST CSF 2.0 organizational implementation;
- side-channel resistance;
- formal verification of the compiler or broker;
- production PQC migration.
