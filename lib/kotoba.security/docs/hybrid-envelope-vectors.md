# Hybrid Envelope Test Vectors

Status: implemented — real vectors generated and verified
Date: 2026-07-02 (contract defined; vectors landed same day)

## Purpose

The PQC roadmap (docs/pqc-roadmap.md) requires a test fixture proving hybrid
key wrapping and epoch rotation: object/key wrapping migrates from
X25519/HPKE to hybrid X25519 + ML-KEM. This document specifies the wrapping
scheme, the vector file contract, and how the vectors are generated and
verified.

## Security consumer path (object encryption)

Independent of ML-KEM host availability, sealed envelopes that carry
`:envelope/*` metadata (as emitted by `kotoba.lang.crypto/seal`) are admitted
to long-retention object storage only through:

`kotoba.security.object-encryption-gate/admit-object-store-write!`

Under default `:hybrid-required` policy (epoch floor 1), classical-only KEM
envelopes are **denied** and the write function is never invoked (EV-0015).

## Wrapping Scheme (kotoba.hybrid.v1)

The recipient holds two keypairs: an X25519 keypair and an ML-KEM-768
keypair. Encapsulation for that recipient:

1. Generate an ephemeral X25519 keypair; `ss1 = X25519(ephemeral-secret,
   recipient-x25519-public)` (32 bytes). The ephemeral public key is sent.
2. ML-KEM-768 encapsulation against the recipient encapsulation key
   produces `(ciphertext, ss2)` (ciphertext 1088 bytes, `ss2` 32 bytes).
3. The key-encryption key is

   ```
   KEK = HKDF-SHA256(ikm  = ss1 || ss2,
                     salt = ASCII "kotoba.hybrid.v1",
                     info = 4-byte big-endian unsigned epoch)   ; 32 bytes
   ```

   (RFC 5869 extract-then-expand; a single expand block suffices for 32
   bytes.)

Decapsulation recomputes `ss1 = X25519(recipient-x25519-secret,
ephemeral-public)` and `ss2 = ML-KEM-768.Decaps(decapsulation-key,
ciphertext)`, then the same HKDF. Binding the epoch into the HKDF `info`
makes epoch rotation part of the derivation, not just metadata.

## Vector File Contract

Vector files live at `conformance/crypto/vectors/*.edn`. Each file holds an
EDN **vector of vector maps** (the hybrid file carries >= 3 vectors with
distinct seeds and epochs). Each vector map:

```edn
{:vector/id "hybrid-x25519-mlkem768-0001"
 :vector/epoch 1
 :vector/kem [:x25519 :ml-kem-768]
 :vector/seed "…64 hex chars…"          ; DRBG seed = SHA-256(:vector/seed-label)
 :vector/seed-label "kotoba.hybrid.v1/vector/0001"
 :vector/inputs {:x25519/recipient-public "…64 hex…"
                 :x25519/recipient-secret "…64 hex…"
                 :x25519/ephemeral-public "…64 hex…"
                 :x25519/ephemeral-secret "…64 hex…"
                 :ml-kem/encapsulation-key "…2368 hex…"    ; 1184 bytes
                 :ml-kem/decapsulation-key "…4800 hex…"    ; 2400 bytes (expanded)
                 :ml-kem/ciphertext "…2176 hex…"}          ; 1088 bytes
 :vector/expected {:x25519/shared-secret "…64 hex…"
                   :ml-kem/shared-secret "…64 hex…"
                   :kek "…64 hex…"
                   :envelope {:envelope/algorithms [:x25519 :ml-kem-768 :aes-256-gcm]
                              :envelope/provider {:provider/id :bc-hybrid-x25519-mlkem768
                                                  :provider/fips-validated false}
                              :envelope/epoch 1
                              :envelope/kem? true
                              :envelope/hybrid? true}}}
```

- `:vector/id` — stable unique string id.
- `:vector/epoch` — encryption epoch the vector exercises; vectors with
  epoch >= the policy `:hybrid-epoch-floor` must be hybrid. The epoch is
  bound into the KEK via the HKDF `info`.
- `:vector/kem` — the KEM combination, `[:x25519 :ml-kem-768]` for the
  hybrid target.
- `:vector/seed` / `:vector/seed-label` — the DRBG seed the generator used,
  so the whole vector is regenerable.
- `:vector/inputs` — all keys and the ML-KEM ciphertext as lowercase hex, so
  both the encapsulation direction (ephemeral secret + recipient public) and
  the decapsulation direction (recipient secrets + ciphertext) are
  recomputable.
- `:vector/expected` — both shared secrets, the derived KEK, and the
  envelope metadata the wrapper must emit; the envelope passes
  `kotoba.security.crypto-policy/check-envelope` under `:hybrid-required`
  (and `:crypto-agile`), and is rejected under `:fips-required` because the
  Bouncy Castle provider is not FIPS-validated.

## Generation (deterministic, BC confined to :vectors)

`scripts/gen-hybrid-vectors.cljk` generates the vectors with Bouncy Castle
(`org.bouncycastle/bcprov-jdk18on` 1.81, final ML-KEM support), which is
available **only** under the `:vectors` deps.edn alias — the default paths
and default `:test` alias stay BC-free:

```bash
kbb -M:vectors scripts/gen-hybrid-vectors.cljk
```

All randomness (X25519 secrets, ML-KEM keygen d/z, ML-KEM encapsulation
randomness) comes from a seeded HMAC-SHA256 counter DRBG implemented in the
script (`block_i = HMAC-SHA256(seed, ASCII(label + "." + i))`, streamed
sequentially per labelled domain) — never from `SecureRandom` defaults —
so regeneration is byte-for-byte reproducible.

## Verification Evidence

- **Cryptographic recomputation** (Bouncy Castle, `:vectors` alias only):
  `kbb -M:vectors:vectors-test` runs
  `test-vectors/kotoba/security/hybrid_vectors_test.cljk`, which recomputes
  `ss1` in both directions (encapsulation and decapsulation), decapsulates
  the recorded ML-KEM ciphertext, re-derives the KEK, and asserts it matches
  `:vector/expected :kek`. CI runs this in the dedicated `vectors` job.
- **Structural gate** (BC-free, default suite + babashka):
  `kotoba.security.hybrid-vectors/check-vector-file` validates fields, the
  kem list, and hex shapes/lengths; it runs in the default `kbb -M:test`
  suite (`hybrid_vectors_structure_test.clj`) and in
  `scripts/check-crypto-inventory.bb`, so every CI run validates the vector
  file without Bouncy Castle.
- This closes the "vectors pending" follow-up: the hybrid key-wrapping
  fixture required by docs/pqc-roadmap.md and referenced by
  docs/evidence-gates.md now exists at
  `conformance/crypto/vectors/hybrid-x25519-mlkem768.edn` (3 vectors,
  epochs 1–3, distinct seeds). ML-KEM is not hand-rolled (pqc-roadmap
  non-goal): Bouncy Castle 1.81 provides the ML-KEM-768 implementation.
  The crypto-inventory register itself is updated separately by its owner.
