# gov_auth_mynumber_bind

L5 routing-around authentication: MyNumber card IC chip → XChaCha20-encrypted DID-bound credential.

## Status

**R0 scaffold** (2026-05-26): `solve()` throws `RuntimeError` until Council activation.

**R1 activation gate** (post-2026-06-19): Requires ADR-2605260000 R1 + Council Lv6+ ≥3 multisig:
- `COUNCIL_ATTESTATION_TX_HASH`: Base L2 multisig confirmation Tx
- `SILEN_GOV_AUTH_BASELINE_REVIEW_CID`: Council audit record IPFS CID

## Purpose

Operationalizes Trust Level 2 authentication (ADR-2605260000):
- **Trust Level 1** (base): DID + WebAuthn platform authenticator (FaceID/TouchID/Windows Hello)
- **Trust Level 2** (opt-in): Trust Level 1 + MyNumber card IC binding

**Constitutional invariants**:
- DID is primary identity; MyNumber is trust elevation only.
- Plaintext MyNumber never stored on MST (ADR-2605181100 XChaCha20-Poly1305 mandatory).
- §0.4 non-registration: MyNumber is one-way read (Web NFC). No state database interaction.
- §2(c) anti-surveillance: Plaintext credentials encrypted, decryption key Signal-wrapped.

## Flow

### Input
```python
{
  "subject_did": "did:web:etzhayyim.com:member:alice",
  "webauthn_credential_id": "base64url...",
  "webauthn_signature": "base64url(P-256_ECDSA_sig)",
  "mynumber_ic_response": b"<raw_Web_NFC_IC_dump>",
  "signal_identities": {
    "did:web:etzhayyim.com:council:seat1": {signal_public_key_json},
    ...
  }
}
```

### Pregel nodes (R0: all RuntimeError)

| Node | Purpose | Output |
|---|---|---|
| `validate_webauthn` | Verify P-256 ECDSA signature against subject DID's authentication key. Reject if platform authenticator != FaceID/TouchID/Windows Hello. | `{valid: bool}` |
| `bind_mynumber_encrypted` | Parse JPKI IC response → XChaCha20 encrypt → IPFS upload → Signal-wrap per-recipient keys. | `{encrypted_payload_cid, key_wrap_cids}` |
| `emit_trust_attestation` | Create `com.etzhayyim.gov.procedure.auth.didTrustAttestation` (trustLevel=2) signed by attestor DID. | `{attested_tid, sig}` |

### Output (R1+)
```python
{
  "com.etzhayyim.gov.procedure.auth.credentialBinding": {
    "subjectDid": "did:web:etzhayyim.com:member:alice",
    "trustLevel": 2,
    "webauthnCredentialId": "base64url...",
    "bindingEpoch": 1748284800,  # Unix timestamp
    "encryptedPayloadCid": "bafy...",  # XChaCha20 ciphertext
    "sig": "base64url(Ed25519_sig)"
  },
  "com.etzhayyim.encrypted.keyWrap": [
    {
      "senderDid": "did:web:etzhayyim.com:member:alice",
      "recipientDid": "did:web:etzhayyim.com:council:seat1",
      "wrappedSymKey": "base64url(Signal_wrapped_XChaCha20_key)",
      "nonce": "base64url(24_byte_nonce)"
    },
    ...
  ],
  "com.etzhayyim.gov.procedure.auth.didTrustAttestation": {
    "subjectDidHash": "blake2b_256(subject_did)",
    "trustLevel": 2,
    "attestedBy": "did:web:etzhayyim.com:council:seat1",
    "reason": "webauthn-plus-mynumber",
    "epoch": 1748284800,
    "silenAuditCid": "bafy..."  # optional Council audit
  }
}
```

## R1 Implementation Tasks

- [ ] WebAuthn P-256 ECDSA verification (resolve DID → extract pubkey → verify sig)
- [ ] JPKI IC chip response parsing (TLV decoder, JPKI cert validation)
- [ ] XChaCha20-Poly1305 encryption (use `@etzhayyim/sdk/crypto` via checkpointer sidecar)
- [ ] IPFS upload (CID receipt)
- [ ] Signal X3DH session establishment + key wrapping (per `@etzhayyim/sdk/signal`)
- [ ] MST record emission (`com.etzhayyim.*.` lexicons)
- [ ] Council activation ADR (R1 ADR-2605260100 reserved)

## R2+ Roadmap

- **R2**: Trust Level 1 plaintext decryption (biometric attestation blob, if any); Trust Level 2 enhanced audit trail.
- **R3**: OAuth/OpenID Connect bridge (external identity provider federation); "external-sso-bridge" reason code.

## Constraints

- **XChaCha20 mandatory**: Per ADR-2605181100, plaintext MyNumber cannot appear on MST.
- **DID-primary**: MyNumber is opt-in elevation, not replacement.
- **Signal-wrapped keys**: Decrypt key is never sent to the subject in plaintext; only Council delegates + subject DID (via Signal protocol) can decrypt.
- **Platform authenticator only**: R0-R3 forbid security keys (FIDO2 USB keys, etc.); FaceID/TouchID/Windows Hello only.

---

ADR-2605260000, ADR-2605181100, ADR-2605260000 R1 (reserved).
