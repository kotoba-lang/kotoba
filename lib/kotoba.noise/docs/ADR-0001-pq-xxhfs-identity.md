# ADR-0001 — Post-quantum Noise for the native broker: XXhfs + ML-KEM-768, signed identity

- **Status**: Accepted (owner, 2026-10-30).
- **Issue**: AWAI-102 (native broker transport), following AWAI-117 (native primitives).
- **Owner direction (2026-10-30)**: choose designs that suit a decentralized network and
  have a track record.

## Context

The broker transport needs peer authentication and confidentiality. This repository's
security posture requires hybrid X25519 + ML-KEM-768 for confidentiality on any new
cryptographic boundary, with no classical-only downgrade, and ML-DSA-65 next to the
classical proof wherever an identity is admitted.

`noise.native` (this library, AWAI-102) implements classical Noise rev 34
`Noise_XX_25519_ChaChaPoly_SHA256`. That is the handshake libp2p uses (IPFS, Ethereum,
Filecoin), and the family WireGuard and Lightning use. It reproduces the Cacophony
vectors byte for byte. Peers are identified by public keys; no certificate authority is
involved, which suits roster keys and `did:key`.

## Decision

### 1. Confidentiality: the Noise `hfs` modifier with ML-KEM-768

Use the Noise extension "KEM-based Hybrid Forward Secrecy for Noise"
(noiseprotocol/noise_hfs_spec, commit `025f0f60`) unchanged, with ML-KEM-768 (FIPS 203) as
its KEM:

```
Noise_XXhfs_25519+MLKEM768_ChaChaPoly_SHA256
  -> e, e1
  <- e, ee, ekem1, s, es
  -> s, se
```

- `e1`: the ML-KEM-768 encapsulation key (1184 bytes). It is sent the way a static key is
  sent, with `EncryptAndHash`. In message 1 no key exists yet, so it is in the clear. The
  spec notes that KEM public keys may travel in clear.
- `ekem1`: the ML-KEM ciphertext to the received `e1` (1088 bytes), encrypted (a key
  exists after `ee`). Both sides then call `MixKey(kem_output)` with the 32-byte ML-KEM
  shared secret.
- By the spec's own security note, Noise's key derivation means that even a broken KEM
  does not weaken the classical handshake. A broken X25519 likewise leaves the ML-KEM
  secret in the chaining key.
- KEM randomness (the `e1` key pair from FIPS 203 `d`, `z`, and the encapsulation `m`)
  comes from the host's entropy provider, like the X25519 ephemerals. Nothing here
  generates randomness.

ML-KEM is used directly rather than X-Wing, because the hybrid combination is Noise's
own chaining key: the hfs modifier already mixes the X25519 DH outputs and the KEM output
in sequence. X-Wing (`org.ietf.xwing`) remains the hybrid KEM for uses outside a Noise
handshake, such as sealing data to a recipient.

### 2. Post-quantum authentication: signed handshake hash in the identity payload

XX authenticates the X25519 static keys only by DH, which is classical. Each side's
handshake payload carrying its static key (message 2 for the responder, message 3 for
the initiator) also carries an identity proof:

- the identity: Ed25519 public key (32) ++ ML-DSA-65 public key (1952);
- the proof: Ed25519 signature ++ ML-DSA-65 signature (pure ML-DSA, empty context), both
  over `"kotoba-noise-pq-identity/v1\n"` ++ the handshake hash `h` taken just before that
  payload is encrypted (after the message's `s` and DH tokens).

Both signatures must verify, and the identity must be the roster member the host expects
for that peer: the host selects it, never the remote side or an application. This follows
two deployed patterns:

- **libp2p's Noise handshake** places an identity key and a signature in the handshake
  payload, binding the long-term identity to the Noise static key.
- **TLS 1.3 CertificateVerify** signs the transcript hash, so the signature binds the
  whole handshake so far (both ephemerals, the KEM exchange and the static key) rather
  than the static key alone.

### 3. Framing

Each handshake message is sent with a 2-byte big-endian length prefix and is at most
65535 bytes, the Noise maximum message length. libp2p frames Noise handshake messages the
same way. Transport messages use the same framing over the native TCP wires (43-47).

## Consequences

- The protocol name differs from libp2p's, so this is not wire-compatible with libp2p
  peers. The classical layer is the same code and keeps its Cacophony gate.
- There are no published test vectors for `XXhfs` with ML-KEM-768. Verification will need:
  - an independent Python reference of the handshake, using OpenSSL 4 for ML-KEM from the
    FIPS 203 seed, and Python for X25519, SHA-256 and ChaCha20-Poly1305 (each already
    checked against its standard);
  - a byte-for-byte comparison of both sides' messages against that reference;
  - mutants, including a dropped `MixKey` after `ekem1`, a signature over the wrong `h`,
    and a roster mismatch.
- Message 2 grows by about 6.4 KB: the ciphertext, the ML-DSA key and the signatures.
- Not constant time (as for every native primitive here); not measured.

## Alternatives considered

- **pqh-v1 KEM + signed transcript + AEAD records**: in-house; no external review.
- **HPKE (RFC 9180) with X-Wing**: standard one-shot encryption, but mutual
  authentication and a long-lived session would have to be designed on top.
- **TLS 1.3 with X25519MLKEM768**: the most widely deployed hybrid, but its trust model is
  certificate authorities, which does not fit a roster-keyed decentralized network.
