# ADR-0286 — Signed catalog and update manifest: Ed25519 + ML-DSA-65 together

Date: 2026-11-05

## Status

Accepted 2026-11-06 (owner: "おすすめで決定", the recommended options for every question this ADR left open, listed in Amendment 2). Amendment 1 (owner, 2026-11-06) made key custody and distribution decentralized. Nothing in this ADR is implemented except the region-based ML-DSA-65 verifier (kotoba#1231-#1234); no key exists and no origin is registered. Design only: nothing here is implemented and no row is claimed. It fills what ADR-0283 and
ADR-0284 left open for the catalog and update artifacts, and it asks the owner for the decisions in the last section. It
registers no origin, creates no key and changes no kernel. The installed-state schema is ADR-0284 and is not repeated.

## Context

Measured in the source (2026-11-05):

- `native/update.kotoba` admits an `AIUEIMG1` image: a 128-byte header (64-byte manifest, Ed25519 signature) and the image.
  The verifier is classical Ed25519 only and keeps no installed version (rollback check is `version >= 1`).
- `gov.nist.mlDsa` (`kotoba/mldsa/core.kotoba`) is ML-DSA-65 (FIPS 204) in native `.kotoba` with an ACVP gate (keyGen,
  sigGen, sigVer). It works on heap `:vector-i64` values. The kernel modules (`aiueos.ed25519`, `aiueos.lib.sha256-stream`)
  work on fixed kernel regions and do not allocate, so the library cannot be linked into the kernel unchanged. The "ML-DSA-65
  verifier is open work" in `update-policy.json` therefore means a region-based port, not a missing algorithm.
- ADR-0277 already states the rule: Ed25519 together with ML-DSA-65, both verified, no classical-only downgrade.
- The kernel-v3 text margin after amu#1825 is about 511 KB (kotoba#1228 build), so code size no longer blocks this.

## Decision

1. **Both signatures, always.** A catalog or image is accepted only if its Ed25519 and its ML-DSA-65 signature both verify
   under the pinned keys. One valid signature never suffices, and a missing one is a refusal, not a downgrade.
2. **`AIUEIMG2` header.** 4096 bytes: 0 `"AIUEIMG2"`, 8 version (u64 LE), 16 size, 24 key id (u32) and reserved zero, 32 SHA-256
   of the image (as `AIUEIMG1`, the 64-byte manifest), 64 Ed25519 signature (64 bytes), 128 ML-DSA-65 signature (3309 bytes),
   rest zero. Both signatures cover the 64-byte manifest, with ML-DSA context `"AIUEIMG2"` so a signature made for another
   object type does not verify here. The image follows the header. `AIUEIMG1` is refused once `AIUEIMG2` ships.
3. **Pinned keys.** Ed25519 public key (32 B) and ML-DSA-65 public key (1952 B), indexed by key id, are baked into the
   kernel. Packed 8 bytes per word, the ML-DSA key is about 244 words (order of 40 KB of text at the measured
   ~160 B per packed word: affordable). Rotation = a new key id in a new image signed by the old keys; no network supplied key
   is ever a root.
4. **Rollback.** The highest accepted `version` per channel is stored in the sealed NVMe state and signed by the device key
   (ADR-0284's append-only chain, one more record kind `image-version`). A manifest with `version` not above it is refused.
5. **Catalog object `AIUECAT1`.** Same header shape: version, count (1..64), key id, SHA-256 of the body, both signatures over
   the manifest. Body entries, each fixed 128 bytes: dock id (u32, installable apps start at 19), title (ASCII, 32), manifest
   CID (36), bundle CID (36), size (u32), reserved. The packed catalog compiled into the kernel (JUN-811) stays the default and
   offline list; a fetched catalog only adds entries, and each entry is admitted by CID (`aiueos.cid-v1-admit`) before use.
6. **Operations.** `fetch-catalog`, `download-app` and the update `check`/`download`/`install` stay separate each-operation
   approvals. Verification is local and sends nothing.

## ML-DSA-65 verify in the kernel: sizing (estimate, to be measured)

From FIPS 204 ML-DSA-65 (k=6, l=5, q=8380417; public key 1952 B, signature 3309 B = 48 c-tilde + 5x640 z + 61 hint):

- Raw inputs held in regions: pk 1952 B + signature 3309 B.
- Working set if verify streams row by row (generate A[i][*] from rho with SHAKE128, accumulate A*z - c*t1*2^d for row i,
  UseHint, pack w1): z in NTT form 5 KiB, c 1 KiB, accumulator 1 KiB, one temp polynomial 1 KiB, w1 bytes 768 B, SHA-3 state
  200 B. About 9 KiB plus the inputs: roughly 15 KiB, which exceeds the 8 KiB browser context and the 4 KiB owned page the
  Ed25519 verifier uses, so it needs its own owned window.
- Work: 5 forward NTTs of z, 1 of c, 6 x 5 pointwise products, 6 inverse NTTs, one SHAKE256 over mu and w1 (about 6 x 256
  coefficients). The gate must show it completes within the desktop frame budget or runs in the update flow only (it is
  not on the interactive path).
- Gate: the ACVP sigVer cases already in `gov.nist.mlDsa` plus the two crafted hint/`||z||` cases, run on the kernel build, and a
  differential run against the library's heap verifier on random signatures. Negative controls: one flipped byte in pk, c-tilde,
  z and hint each refuses; Ed25519-only and ML-DSA-only images refuse.

## Order of work

1. This ADR accepted; owner decisions below.
2. Region-based `aiueos.mldsa65-verify` (new module), its own QEMU profile like `ed25519`, ACVP + differential gate.
3. `AIUEIMG2` in `update.kotoba` with the self-test fixtures signed by published test keys (the fixtures prove the path, not a key).
4. Version record in the sealed state; `auto-install` may then be called qualified.
5. `AIUECAT1` reader and the installer's `fetch-catalog`/`download-app` once an origin and key exist.

## Not decided here (owner)

- **Origins.** The catalog origin, the artifact origin and the update origin (full https origins; they also fix the static CSP of
  the dapp). None is registered.
- **Key custody.** Who generates the Ed25519 and ML-DSA-65 signing keys (the operator's Mac as for `AIUEIMG1`, or a
  hardware token), their key ids, and the rotation rule. The seeds must never enter this repository.
- Acceptance of the `AIUEIMG2` layout and of retiring `AIUEIMG1`.
- Whether a publisher catalog (third-party) may exist beside the distribution catalog (ADR-0284 keeps publisher trust a user choice).

## Amendment 1 (2026-11-06, owner): decentralized key custody and distribution

The owner decided that the signing keys and the distribution origin are decentralized ("署名鍵の保管と配信元は、分散型で").
This is a direction, not a finished design. What follows is what the direction implies for the text above, read from this
ADR and the sizes measured in it. Parameters the owner has not given are listed as open and are not chosen here.

**Key custody: several independent signers, not one key.**

- A catalog or image is accepted only when at least M distinct signers out of N pinned signers have both of their signatures
  valid (Ed25519 and ML-DSA-65, decision 1 stays per signer). No single holder can publish.
- There is no standardized threshold ML-DSA, so this is a list of ordinary signatures, not threshold cryptography. The cost
  is linear: M verifications, N pinned keys.
- The `AIUEIMG2` layout of decision 2 does not hold more than one signer: Ed25519 (64 B) plus ML-DSA-65 (3309 B) is 3373 B per
  signer, and the 4096-byte header already carries 128 B of fields. The header has to become a signature block of M entries
  (key id, both signatures) after the fixed fields. `AIUECAT1` changes the same way. The layout is therefore not accepted
  as written in decision 2.
- Pinned keys (decision 3) grow to N pairs: N x (32 B + 1952 B). At the ~40 KB of text per ML-DSA key estimated above, N = 5
  is order of 200 KB of kernel text, which the margin (about 0.82 MB after amu#1840) can hold; the number is to be measured.
- Rotation (decision 3) generalizes: a new signer set is accepted when the current set signs it with its own threshold M.
  The same rule covers removing a signer.
- Seeds still never enter this repository, and no signer's key is held by the same custodian as another's.

**Distribution: content addressed, the origin is not a trust root.**

- Integrity comes from the signed manifest and the content identifier of each object, which decision 5 already requires
  (`aiueos.cid-v1-admit` before use). Where the bytes came from therefore does not decide whether they are accepted: any
  mirror or peer may serve them, and a wrong object is refused by the kernel, not by the origin.
- This replaces "register one origin" with a set of interchangeable, untrusted sources. It does not remove the Kotoba rule that
  each fetch is an operation the user approves for a declared service and endpoint, nor the static CSP derived from the
  declared origins (the shared contract in the workspace AGENTS.md): every source class still has to be declared. A
  peer-to-peer transport needs its own declared service and approval; this ADR does not define one.
- An untrusted source can withhold. Rollback protection (decision 4) stops an old image being installed, but it does not stop a
  source from hiding a new one. A signed freshness statement (a short-lived signed "latest version" record with an expiry)
  would let a device notice. That is a proposal to be decided, not part of this amendment.

**Order of work (replaces step 5 only):** the multi-signer block layout is designed and accepted first; the region-based
ML-DSA-65 verifier (steps 2, already merged as stages 1-4) is unchanged because it verifies one signature at a time.

**Open owner parameters:** the number of signers N and the threshold M; who the signers are and where each key lives; which
content-addressed network or networks are used (and their declared service origins); the signer-set rotation procedure; whether
a freshness statement is required; the layout of the signature block.

Not verified: no signature block, multi-signer verification or mirror fetch exists; the size figures are estimates from the
numbers above.

## Amendment 2 (2026-11-06, owner: recommended options): the open parameters

The owner answered every open question of this ADR and of Amendment 1 with "the recommended option". The recommendations and
their reasons follow. Where a choice needs a real-world fact only the owner has (who holds a key, which host serves a
gateway), the decision is the rule, and the fact is named as still to be supplied; nothing is invented here.

| Question | Decision | Reason |
| -- | -- | -- |
| Signers | N = 3 pinned signer slots, M = 2 required | Survives the loss or compromise of one key; the smallest set with no single point. |
| Who holds them | Three independent custodians: (1) the operator's Mac, as for `AIUEIMG1`; (2) a hardware token kept apart from the Mac; (3) an offline cold key in a third place. No custodian holds two. | Different failure and theft modes. Real holders and devices are the owner's to name; seeds never enter this repository. |
| `AIUEIMG2` layout | Header 16384 bytes: 128 fixed bytes as in decision 2 without the signature fields, then up to 4 signature entries of 3392 bytes each (key id u32, 4 reserved, Ed25519 64 B, ML-DSA-65 3309 B, padding), rest zero. The count is a fixed field. `AIUEIMG1` is retired once `AIUEIMG2` ships. | 3 x 3381 B does not fit 4096; 16 KiB holds the four entries (three signers plus one slot for a rotation overlap) with room to spare. |
| Admission rule | At least M entries with distinct key ids, each with both signatures valid under the pinned pair for that id. Duplicates, unknown ids and a missing half are refused, never counted. | Decision 1 per signer; distinctness stops one key counting twice. |
| `AIUECAT1` | Same signature-block rule, same key ids; body as decision 5. | One rule for both objects. |
| Rotation and removal | A new signer set (up to 4 slots) is accepted when the current set signs it with M of its own entries, and takes effect for the next object. | Generalizes decision 3; no network supplied root. |
| Freshness | Required for the update channel: a signed "latest" record (version, issued-at, valid-until) under the same admission rule, valid 30 days. A stale or missing record does not block installing a verified object that is newer than the stored version; it makes `check` report "not fresh" so a hidden update is visible. | Rollback protection stops old images, not a source hiding new ones (Amendment 1). Blocking offline devices would be worse than warning. |
| Distribution network | Content-addressed (CID). Sources are interchangeable and untrusted: IPFS-style retrieval by CID, with HTTPS gateways as declared service origins. Acceptance is by CID plus signatures, never by source. | Matches `aiueos.cid-v1-admit` and decision 5. |
| Origins | No origin is named by this ADR. The owner supplies the gateway host list; each host is declared as a service endpoint with its own each-operation approval and enters the static CSP. A peer-to-peer transport needs its own declared service and is out of scope. | Registering a host is a real-world act; the rule is fixed, the hostnames are not mine to invent. **Still to be supplied by the owner.** |

**Consequences for the work order.** Step 3 becomes: `AIUEIMG2` with the 16 KiB signature block and the admission rule,
fixtures signed by published *test* keys (the fixtures prove the path, not a key). Pinned production keys, the real
custodians and the gateway hosts are separate, later and owner-supplied. Kernel text for three pinned ML-DSA keys is to be
measured, estimated at order 120 KB.

