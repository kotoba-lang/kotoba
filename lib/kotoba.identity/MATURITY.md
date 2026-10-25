# Maturity

**Level: R2 live adapter**

Implemented:
- Subject, evidence reference, and attestation models.
- Validation for known subject and evidence kinds, required IDs, attestation fields, and non-adjudicating records.
- Datom emitters for subjects, evidence references, and attestations.
- Ledger adapter boundary for validated subject/evidence/attestation datom transactions.
- Durable EDN ledger implementation.
- Datomic/Kotoba ledger backend adapter with transaction option propagation.
- DID resolver adapter boundary and DID document to subject binding.
- Verifiable Credential verifier boundary with evidence and attestation binding.
- Cross-source subject merge policy with aliases and conflict markers.
- Contract tests for subject shape, invalid records, attestation datoms, DID resolution, VC binding, merge policy, ledger payloads, and durable transaction reload.
- Causal identity epochs, attributed identifier-link claims, scoped evaluator
  trust claims, inheritable obligations, and basis-bound epoch transitions.
- Atomic transition persistence: the successor epoch starts at trust zero only
  when every open obligation is carried and every prior active grant is named
  for revocation.
- Fail-closed EAS verification with explicit chain/contract coordinates,
  schema and attester allowlists, revocation, expiration, and time checks.
- Human Passport current-schema normalization into a 90-day scoped
  Sybil-resistance claim and Sekisho evidence, without importing its score as a
  general trust score.
- Kotoba Passport (`identity.passport`): four stamp classes, nullifier
  ledger rule with first-claim-wins dedup, revocation and vouch budgets,
  policy-pinned scoring with class caps, majority witness certificates, and
  identity-model output. Tested with real Ed25519/SHA-256 (node:crypto) under
  kbb; no issuer, witness set, or ledger deployment exists yet.
- Current draft ERC-8004 three-registry registration, reputation, and
  validation normalization with mandatory client/validator allowlists.
- Atomic persistence of externally verified trust bundles.
- Reference JVM JSON-RPC/ABI host for read-only EAS and Human Passport reads,
  with HTTPS RPC pinning, chain-ID verification, bounded responses, strict ABI
  bounds checks, and both expired-refusal and fresh-positive Base live
  proofs against the official schema and exact Itonami policy.
- Coordinate-driven JVM ERC-8004 reader for Identity, Reputation, and Validation
  registry calls plus bounded HTTPS, IPFS-gateway, and base64 data registration
  documents.
- Published trust-profile/v1 JSON Schema and role-specific policy projection.
- Itonami `identity.sybil-step-up` policy decision with verified Principal
  account recipient binding; the decision is evidence-only and grants no
  capability.

Not yet R2:
- ERC-8004 Validation activation. The official deployment table publishes Base
  Identity and Reputation coordinates but no governed Base Validation address.
- Current live state of the historical Etzhayyim private chain is unverified;
  its old monolithic contract is explicitly outside current ERC-8004 support.
- Authenticated production-user receipts remain separate service evidence:
  this repo proves the fresh public attestation read without impersonating an
  Itonami Principal or writing a Kotobase tenant receipt.
