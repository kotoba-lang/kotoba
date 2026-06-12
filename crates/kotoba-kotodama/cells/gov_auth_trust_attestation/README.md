# gov_auth_trust_attestation

L5 routing-around authentication: trust-level evaluation and public attestation.

## Status

**R0 scaffold** (2026-05-26): `solve()` throws `RuntimeError` until Council activation.

**R1 activation gate** (post-2026-06-19): Requires ADR-2605260000 R1 + Council Lv6+ ≥3 multisig:
- `COUNCIL_ATTESTATION_TX_HASH`: Base L2 multisig confirmation Tx
- `SILEN_GOV_AUTH_BASELINE_REVIEW_CID`: Council audit record IPFS CID

## Purpose

Operationalizes trust-level evaluation for DID-based identity attestation (ADR-2605260000):
- **Trust Level 1** → WebAuthn platform authenticator (FaceID/TouchID/Windows Hello) verified
- **Trust Level 2** → Trust Level 1 + MyNumber IC card binding (XChaCha20 decryption successful)

**Constitutional invariant**: Attestation record is **public** (no encryption) and contains **no PII**. Personal identifiers are encrypted separately in `credentialBinding.encryptedPayloadCid` and Signal-wrapped keyWrap records.

## Flow

### Input
```python
{
  "subject_did": "did:web:etzhayyim.com:member:alice",
  "authentication_method": "webauthn-plus-mynumber",  # or "webauthn-only"
  "webauthn_verified": True,
  "mynumber_decrypted": True,  # True if MyNumber XChaCha20 decryption succeeded
  "attestor_did": "did:web:etzhayyim.com:council:seat1"
}
```

### Pregel nodes (R0: all RuntimeError)

| Node | Purpose | Output |
|---|---|---|
| `evaluate_trust_level` | Assess authentication evidence. Require webauthn_verified=True. Map to trustLevel (1 or 2) based on method + mynumber_decrypted. | `{trust_level, reason_code, audit_log}` |
| `emit_attestation` | Create public `com.etzhayyim.gov.procedure.auth.didTrustAttestation` (no encryption, no PII). | `{attested_tid, sig, expiry}` |

### Output (R1+)
```python
{
  "com.etzhayyim.gov.procedure.auth.didTrustAttestation": {
    "subjectDidHash": "blake2b_256(subject_did)",  # hashed DID only (no plaintext)
    "trustLevel": 2,  # 1 or 2
    "attestedBy": "did:web:etzhayyim.com:council:seat1",
    "reason": "webauthn-plus-mynumber",  # "webauthn-only" | "webauthn-plus-mynumber"
    "epoch": 1748284800,  # Unix timestamp
    "expiresAt": 1779820800,  # Unix timestamp (optional, default 365 days)
    "silenAuditCid": "bafy..."  # optional Council audit record CID
  }
}
```

## Security Properties

1. **Public attestation**: No encryption. Safe to expose in user-facing dashboards, regulatory audits, etc.
2. **Privacy-preserving**: Hash of DID only, no plaintext identifiers.
3. **Immutable once written**: MST record is content-addressed; cryptographic integrity guaranteed.
4. **Council-signed (R1+)**: Attestor DID must be Council-delegated; signature validates authenticity.
5. **Time-bound (R1+)**: Optional expiresAt enforces re-evaluation at regular intervals.

## R1 Implementation Tasks

- [ ] evaluate_trust_level: enum validation + logic (L1 vs L2 determination)
- [ ] emit_attestation: record construction + MST emission (`com.etzhayyim.gov.procedure.auth.didTrustAttestation`)
- [ ] blake2b_256 DID hash computation
- [ ] Optional signature + expiry handling
- [ ] Council activation ADR (R1 ADR-2605260100 reserved)

## R2+ Roadmap

- **R2**: Attestation chain (chain of trust from previous attestations); revocation records.
- **R3**: External SSO bridge (OAuth/OpenID Connect integration); external-sso-bridge reason code.

## Constraints

- **Public**: No encryption; all fields visible.
- **No PII**: Plaintext DID is never stored; blake2b_256 hash only.
- **Council-only**: Attestor must be Council-delegated DID.
- **Immutable**: Once emitted to MST, record cannot be modified (only new attestations override).

---

ADR-2605260000, ADR-2605181100, ADR-2605260000 R1 (reserved).
