# ADR-0003 — Signed manifests: authenticity & provenance

- Status: accepted (Phase 1, in progress)
- Date: 2026-06-26

## Context

Phase-0 gives **integrity**: a manifest may declare `:aiueos/wasm-sha256` and the
broker rejects the component if the loaded bytes don't match. That proves the
artifact wasn't tampered with — but **not who authored it**. Under a mythos-class
adversary that supplies a malicious component, integrity alone is insufficient:
the hash binds a name to bytes, but anyone can compute a hash. We need
**authenticity** — a cryptographic attestation that a known signer vouches for
"component `<id>` is exactly these bytes" — and **provenance** recorded in the
audit log.

## Decision

Add an ed25519 signature over the **identity↔artifact binding**, carried as data
in the manifest, verified by the broker against a policy-held registry of trusted
public keys.

### What is signed

The canonical signed message binds the component id to its artifact hash:

```
<component-id>\n<wasm-sha256>
```

e.g. `driver/sensor\n3b1f…`. Signing the *(id, artifact-hash)* pair (rather than
the whole manifest text) means the signature survives benign manifest edits
(comments, key order, limits tuning) while still pinning the security-critical
fact: *this identity runs exactly these bytes, vouched for by this signer.* A
component with no `:aiueos/wasm-sha256` cannot be signed (nothing to bind).

### Manifest fields

```edn
{:aiueos/component :driver/sensor
 :aiueos/wasm "sensor.wat"
 :aiueos/wasm-sha256 "3b1f…"
 :aiueos/signer "alice"          ; key id, resolved via the policy registry
 :aiueos/signature "9c2e…"}      ; hex ed25519 signature over the canonical message
```

### Policy: the signer registry

```edn
{:aiueos/signers {:alice "ed25519-public-key-hex"}}
```

### Verification flow (broker, before run)

1. If the manifest carries no `:aiueos/signature`, it is **unsigned** — handled by
   policy (a `require-signed` policy denies it; otherwise it runs at its declared
   trust, as today).
2. If signed: the signer must be in the registry, and the signature must verify
   against the canonical message under that public key. **Failure is a hard
   `Denied` — never a downgrade-to-unsigned.** A forged or stale signature is
   strictly worse than no signature.
3. A valid signature **elevates trust to `:verified`** (if the declared trust was
   lower), unlocking the verified tier's policy. The signer is recorded in the
   audit log (provenance).

### Why a binding, not a cert chain

Phase-1 keeps a flat signer registry (no CA hierarchy, no revocation lists). This
is the smallest thing that closes the authenticity gap; chains, expiry, and
revocation are future work and slot above this without changing the manifest
shape.

## Increments

1. **Data model + this ADR** — parse `:aiueos/signer` / `:aiueos/signature`; a
   `Manifest::signed_message()` helper returning the canonical bytes. *(no crypto
   dep yet)*
2. **Verification** — ed25519 verify behind a `signing` feature; the policy signer
   registry; `Denied` on bad signature.
3. **Trust elevation + provenance** — valid signature → `:verified`; audit the
   signer.
4. **Tooling** — `aiueos sign <manifest> --key …`, `verify --require-signed`.

## Consequences

- Closes the "manifests are unsigned" limitation called out in SECURITY.md.
- Adds one small, well-audited crypto dependency (ed25519) to a feature, not the
  minimal core.
- The binding is *(id, hash)*; a signer who rotates the artifact must re-sign —
  intended (the signature is a statement about specific bytes).
