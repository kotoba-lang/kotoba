# ADR-0286 — Signed catalog and update manifest: Ed25519 + ML-DSA-65 together

Date: 2026-11-05

## Status

Accepted 2026-11-06 (owner: "おすすめで決定", the recommended options for every question this ADR left open, listed in Amendment 2). Amendment 1 (owner, 2026-11-06) made key custody and distribution decentralized. Implemented (QEMU gates, test keys only; Amendments 3 to 6): the region-based ML-DSA-65 verifier (kotoba#1231-#1234), the AIUEIMG2 multi-signer admission (stages 5a, 5b), the hash-checked version floor (stage 5c, Amendment 4), the AIUECAT1 catalog admission (stage 6, Amendment 5) and the AIUEFRS1 freshness admission with an RTC clock (Amendment 6). Not implemented: any production key or signer set, any origin, a consumer of the catalog or the freshness record, the signed device-key floor. No row is claimed beyond the gates named in each amendment. It fills what ADR-0283 and
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


## Amendment 3 (2026-11-06): header tail and AIUEIMG1 retirement, from review of stages 5a and 5b

Two review findings that change no behaviour. They state what the implementation does and what must hold before production.

1. **Header bytes after the last entry are ignored and unauthenticated.** Amendment 2 says the rest of the 16384-byte header is
   zero. Neither kernel path reads or checks bytes `128 + count * 3392 .. 16383`: the stage 5a self-test discards them, and the
   network pull (stage 5b) never fetches them, the image starting at byte 16384 of the stream only after the entries. The
   signatures cover the 64-byte manifest, not the header, so these bytes cannot affect admission and nobody has signed them. A
   producer should still write zeros, and a consumer must treat the tail as padding, never as data. The bytes that *are*
   checked are: magic, manifest reserved bytes 24..31, count 1..4, layout bytes 68..127, and per entry the key id (all four
   bytes), reserved bytes 4..7 and padding bytes 3381..3391; an entry with a non-pinned id or any nonzero reserved/padding
   byte is skipped, never counted (stage 5a hardening makes the 5a kernel match the stage 5b path and the host oracle here).
2. **`AIUEIMG1` MUST be retired in the same change that pins a production signer set.** The kernel keeps accepting `AIUEIMG1`
   (one Ed25519 signature, one pinned key) while no production `AIUEIMG2` signer set exists, so that the existing update path
   and its self-test still work. Once production keys for the multi-signer rule are pinned, leaving `AIUEIMG1` admissible would
   let one key (and no ML-DSA signature) install an image, bypassing the two-of-three rule and the post-quantum floor. The
   change that pins the production set must therefore remove the `AIUEIMG1` branch of `admit` (and the single-key pin) in the
   same commit; a release that has both is not acceptable.

## Amendment 4 (2026-11-06, owner decision, JUN-813 stage 5c): an interim hash-checked version floor

**Decision (owner, recorded).** Ship rollback refusal now with a hash-checked per-channel version floor kept in the existing update
journal (`native/update_journal.kotoba`, file `OSMETA.BIN`, AWAI-122). Decision 4's "signed by the device key" (ADR-0284's append-only
chain) is **not** met by this and stays the goal. It is follow-up work behind ADR-0284: that chain does not exist yet, and the device
key cannot sign on the unattended update path (it is consent-bound, ADR-0277). Decision 4 is therefore partly implemented, not closed.

**The threat this answers, and its limit.** Rollback protection answers *replay of an old but validly signed image arriving over the
network* (a mirror, a peer or an on-path attacker serving version 3 to a device at version 5; the signature is still good). The floor
refuses it. An attacker who can **write the disk** can replace `BOOTX64.EFI` directly, without touching the floor, so a device signature
over the floor would not stop that attacker either: signing the floor protects the floor, not the image the firmware boots. What the
journal's SHA-256 gives is protection against **corruption and accidental edits** (a torn write, a flipped bit, a half-written
record), not against an adversary. What a hash-checked floor does **not** give: protection against someone who can rewrite
`OSMETA.BIN` consistently (a valid record with a lower floor and its correct hash); they can lower the floor and then replay. The
hash is not a MAC and the file is not sealed.

**What was built.**

1. `admit` (both `AIUEIMG1` and `AIUEIMG2`; the self-test and the `self-install` hooks do not go through it) first loads the journal
   (re-probes NVMe and the ESP, mounts `OSMETA.BIN` read-only, `load`: marker, head, both slots and the SHA-256 of the published
   record all checked). Only then does it fetch the 128 header bytes. After the header is admitted (signatures counted, size and
   version valid) the manifest version must be **strictly above** the floor. No image byte has been taken at that point.
2. **New result codes (word 180, and 208 for installs).** `9`: the version is not above the floor (equal is refused). `10`: the floor
   cannot be read: `OSMETA.BIN` is missing, unreadable, corrupt, fails its hash or schema, or was never initialised. A journal that
   cannot be read **fails closed**: the update is refused. It is never taken as floor 0. `50` (word 208 only): the image was installed
   and committed but the journal could not be advanced; the operator must see this, because the same version can then be installed
   again. Words 256..262 are the observation words (floor read, load result, advance result, floor after, provisioning hook).
3. **Crash order: install, then advance.** After the install is committed (`BOOTX64.EFI` swapped and hashed back to the manifest digest)
   the floor advances through the journal's own crash-ordered `prepare`: the new floor is `version`. If the machine stops between the
   two, the new image is installed with the old floor: **one repeat install of the same version is admitted, and nothing is bricked.**
   Advancing first would turn every install that fails halfway (digest mismatch, write failure, power loss) into a device that refuses
   its own retry. A verify-only boot, a refused header and a failed install never advance the floor.
4. **Journal phases.** An advance leaves the journal "prepared" (phase 1, floor = candidate = the installed version). Nothing confirms
   it: confirming needs boot-health evidence (the first good boot of the new image) and no such evidence exists. A later install that
   finds an earlier unconfirmed prepare abandons it through the journal's own `trial` then `rollback` transitions (phase 3, floor
   kept) before preparing the new version. `confirm-installed` exists as the one future call site and has no caller.
5. **Provisioning: fail closed, do not create.** The ESP of the `update2` and `nvme` gate fixtures, and of every installed board, has no
   `OSMETA.BIN`; nothing at boot or on the network path creates it (the journal's rule "no boot formatting"). The smallest correct
   choice is to refuse: creating the file on the update path would initialise the floor from an image nobody has trusted yet, which is
   floor 0 by another name for the first replay. So a board with no `OSMETA.BIN` **refuses every network update with 10** until a
   deliberate, separate provisioning step creates it with a floor the owner chose. That step is
   `os/aiueos/scripts/aiueos-provision-esp.py DISK --version N` (JUN-813 follow-up): it writes `\EFI\ITONAMI\OSMETA.BIN` with the
   journal's exact format (floor = active = N, confirmed, generation 1, active-image digest = SHA-256 of that ESP's `BOOTX64.EFI`) into
   an existing `\EFI\ITONAMI\`, with the placement `record-file` demands, and refuses (nothing written) a missing `--version`,
   a missing directory, an existing `OSMETA.BIN` without `--replace`, or a file that cannot be placed. The QEMU `provision` gate
   boots a disk the command made, with no hook. The earlier `update2` gate still provisions through a hypervisor-only fw_cfg hook
   (request `4`: floor 4, active 4) that no physical board has.

**Consequence the owner must know.** Merging this makes the existing network `install` path refuse (result 10) on every currently
installed board until it has an `OSMETA.BIN`. That is the intended fail-closed behaviour. Boards already deployed (and any board
imaged before this change) stay refused until the operator runs `aiueos-provision-esp.py DISK --version N` against the ESP (the
version of the image the board runs now); the choice of N is the owner's, and a too-low N re-admits older images. The image
builders (`make-release-image.py`, `make-install-usb-image.py`) do not create `\EFI\ITONAMI\` at all, so a board freshly imaged
by them has neither the native loader path nor an `OSMETA.BIN`; building that directory into new images is a separate, open gap and
this change does not close it.

**Verified (QEMU/TCG, test keys, `-nic none`):** the `update2` gate (hook-provisioned floor 4, independent oracle): floor boundary
(above, equal, below) for `AIUEIMG2` and `AIUEIMG1`; install advances the floor 4 to 5 and a second install of version 5 is refused; a
newer version advances it again; an install that stops before the advance leaves the floor at 4, a repeat is admitted once and then
refused; a tampered image and a one-signer header never advance it; a corrupt and an absent `OSMETA.BIN` give 10 with nothing
written. Negative controls: rebuilt kernels without the floor check, without the advance, and with a corrupt journal read as floor 0
each fail this gate (see the pull request). **Not verified:** the network pull itself (no RTL8168 in QEMU); physical hardware;
power loss between the install and the advance (the crash case is simulated by the hook stopping before the advance, the guest is not
killed between the writes); an adversary who rewrites `OSMETA.BIN`; real-board provisioning; a floor per channel (one floor is kept,
the update image channel is the only channel today).

## Amendment 5 (2026-11-06, JUN-813 stage 6): the `AIUECAT1` byte layout and its kernel-side admission

Decision 5 named the catalog object but fixed no bytes. This amendment fixes them, using Amendment 2's signature block unchanged, and records
the choices the text could not settle (marked **chosen**: the safest option, not an owner decision). It is implemented as a QEMU-only
admission in `native/update.kotoba` and is **not** wired into the desktop's app list.

**Container.** An `AIUECAT1` object is, in order: a 16384-byte header, then the body. The header is the `AIUEIMG2` signature block of
Amendment 2 byte for byte: the 64-byte manifest at 0, the signature count `u32` at 64 (1..4), bytes 68..127 zero, up to four 3392-byte
entries from 128 (key id `u32`, 4 zero bytes, Ed25519 signature 64, ML-DSA-65 signature 3309, 11 zero bytes), the rest of the 16384 bytes
ignored and unauthenticated (Amendment 3). The body starts at byte 16384, immediately after the header and not after the last entry, and
is `128 * count` bytes long (at most 8192).

**Manifest (64 bytes, the bytes both signatures cover).**

| Offset | Size | Field |
| -- | -- | -- |
| 0 | 8 | `"AIUECAT1"` |
| 8 | 8 | version, `u64` LE, at least 1 |
| 16 | 8 | body length, `u64` LE, must equal `128 * count` |
| 24 | 4 | catalog entry count, `u32` LE, 1..64 |
| 28 | 4 | reserved, zero |
| 32 | 32 | SHA-256 of the body |

This differs from the `AIUEIMG2` manifest only where the image has "size" and "reserved" (bytes 16..31): the catalog's length is redundant
with its count on purpose (a signed length that disagrees with the signed count is refused, `3`), and the count sits in the signed bytes.
The signature count at byte 64 is the signature block's, not the catalog's; the two are different fields.

**Signed message and domain separation.** Ed25519 signs the 64 manifest bytes (as `AIUEIMG2`). ML-DSA-65 signs
`M' = 0 || 8 || "AIUECAT1" || manifest`, context `"AIUECAT1"`. The magic is part of the manifest, so an Ed25519 signature over an image
manifest cannot be replayed as a catalog manifest (the magic differs, so the bytes differ), and the ML-DSA context separates the other
direction: a catalog signed under `"AIUEIMG2"` is refused as a catalog because the ML-DSA half fails, and one signed under `"AIUECAT1"` is
refused as an image for the same reason. The kernel selects the kind by the call (the catalog entry point), never by the magic alone, and
rejects a header whose magic is the other kind (`2`). The same pinned signer slots, the 2-of-3 rule and the skip-never-count rule of
Amendments 2 and 3 apply unchanged.

**Body entry (128 bytes).**

| Offset | Size | Field | Rule |
| -- | -- | -- | -- |
| 0 | 4 | dock id, `u32` LE | 19..82 (**chosen**), no two entries equal |
| 4 | 32 | title | 1..31 printable ASCII bytes (`0x20..0x7e`), then a NUL, then only zero bytes |
| 36 | 36 | manifest CID | binary CIDv1 envelope |
| 72 | 36 | bundle CID | binary CIDv1 envelope |
| 108 | 4 | bundle size, `u32` LE | 1..33554432 (**chosen**) |
| 112 | 16 | reserved | all zero |

- **Dock id range 19..82 (chosen).** The text says installable apps start at 19 and a catalog holds 1..64 entries; it names no upper bound.
  19..82 is the only bound that lets a full 64-entry catalog exist and makes duplicate detection a 64-bit mask in two context words. A
  consumer (not in this stage) may narrow it further; widening it needs a larger mask.
- **Title.** Empty, unterminated, non-ASCII, control characters (including `0x7f`) and bytes after the first NUL are all refused.
- **CID envelope.** The four prefix bytes the way `aiueos.cid-v1-admit` reads them (reasons 2..5: version 1, codec 0x55, 0x70 or 0x71,
  multihash 0x12, length 0x20); any 36-byte string that is not that, including a textual CID, is refused. This is a structural check
  only: the digest is compared with a block when the manifest or the bundle is downloaded (`aiueos-cid-v1-admit` itself needs the
  block, which a catalog does not carry). The prefix test is written again in `update.kotoba` rather than called, because the module's one
  entry point hashes a block and changing it would change the pinned `cid-v1-admit.o`.
- **Bundle size bound 1..2^25 (chosen).** The same 32 MiB limit the image path already applies; zero and larger are refused.

**Admission order and result codes** (word 180; shared with the image path where the code is the same): `2` magic (or the other kind's
magic), `5` manifest reserved bytes, `3` signature count / layout bytes 68..127, `8` no production signer set pinned (test mode only
has one; the check is before any signature work), then the per-entry signatures as each entry's last byte lands, `1` fewer than two
distinct valid signers, `3` entry count outside 1..64 or length not `128 * count`, `4` version 0; only then is the body taken. The body
is streamed through the image path unchanged (chunks that end on a 1 KiB line, SHA-256 against the manifest) and each 128-byte entry is
checked in the page as its chunk lands; `7` is the body hash differing, `16` the hash matches but an entry is refused, `15` verified. `7`
wins over `16`: an entry of a body whose hash is wrong is not looked at as evidence. Entry flags (word 270, OR over all entries, no early
exit): 1 dock id outside the range, 2 duplicate dock id, 4 reserved bytes, 8 title, 16 CID, 32 size.

**Memory and words.** The header uses exactly the memory of the `AIUEIMG2` path (ML-DSA arena = owned window 4, Ed25519 buffers, SHA state);
the body adds nothing: it lands in the same one-page buffer as an image block and is gone when the next chunk lands. Added state: word 231
(kind: 1 catalog), 270 flags, 271/272 the seen-dock-id mask (bit `id - 19`); the QEMU hook records case k at word 300 + k as
`result | counted mask << 8 | flags << 16`.

**What this stage does not do.** The catalog's version is checked for `>= 1` only: the hash-checked floor of Amendment 4 is the **image**
channel's, and a catalog needs its own channel record (open). Nothing reads a fetched catalog into the app list; the desktop still uses the
packed catalog only (JUN-811). `fetch-catalog` and `download-app` are not built. No production signer set is pinned (a production-mode
catalog is refused with `8`). The CIDs are checked for shape, not against any bytes. An entry for a dock id that the packed default also
defines (ids 1..18 are refused, so a fetched catalog cannot shadow them) is the only conflict rule: how a consumer treats a fetched id that
is not yet installed is the consumer's.

**Verified (QEMU/TCG, test keys, `-nic none`):** the `catalog` gate (44 cases, every verdict equal to the independent oracle's), and the `update2` (now 39 cases, two of them
AIUECAT1-context signatures presented as images, refused), `imgsig`, `nvme` and default `desktop` regressions. Negative controls (kernels
rebuilt with one rule removed, each failing the catalog gate on exactly the cases that rule decides): the image context accepted for catalogs,
the duplicate-dock-id check dropped, the body-hash check dropped. Kernel text: 2501888 to 2515840 bytes (+13952; estimated margin
588704 to 574752), the same for the debug and the default desktop kernels because `chunk-done` is shared. **Not verified:** a physical board; the network pull of a catalog (no
RTL8168 in QEMU); anything about a consumer, because none exists.

## Amendment 6 (2026-11-06, JUN-813 freshness): the clock, the `AIUEFRS1` record, and what it stops

Amendment 2 decided a signed "latest" record (version, issued-at, valid-until, 30 days) and left open the clock it is judged against. The
investigation is in `90-docs/evidence/freshness-time-source-20261106/README.md` (every claim labelled measured or read). Its result, in one
paragraph: the native kernel has **no wall clock at all today** (the TSC is calibrated against the PIT and counts from boot, nothing reads
the CMOS RTC, nothing speaks a time protocol, nothing checks a certificate date). The only wall clock a PC offers is the CMOS RTC
(ports 0x70/0x71), which is battery-backed, survives reboot, and is set by whoever controls the firmware, the hypervisor or code running on the
machine, never by the network. That is a clock the device can trust **as far as the stated threat needs** (a source withholding or replaying
old records, at a granularity of days) and no further. It is read by `native/update.kotoba` (`rtc-now`) and used only for this decision.

**Record layout.** Object `AIUEFRS1`: the `AIUEIMG2` signature block of Amendment 2 byte for byte (16384 bytes: 64-byte manifest, signature count
`u32` at 64, bytes 68..127 zero, up to four 3392-byte entries; the tail is ignored and unauthenticated, Amendment 3). It has **no body**.

| Offset | Size | Manifest field (the 64 signed bytes) |
| -- | -- | -- |
| 0 | 8 | `"AIUEFRS1"` |
| 8 | 8 | latest version, `u64` LE, 1..2^63-1: the highest `AIUEIMG2` version the signers publish on the channel |
| 16 | 8 | issued-at, `u64` LE, UTC seconds since 1970-01-01, 1..2^63-1 |
| 24 | 8 | valid-until, `u64` LE, UTC seconds, above issued-at, below 2^63 |
| 32 | 4 | channel, `u32` LE, 1 = the update image channel (the only one today); any other value is refused |
| 36 | 28 | reserved, zero |

The signed message is fixed at 64 bytes in the kernel (`copy-manifest`, the Ed25519 message length), so the record cannot also carry the
SHA-256 of the latest image's manifest; the version number is the whole claim, and the image itself is separately admitted. ML-DSA-65 signs
`M' = 0 || 8 || "AIUEFRS1" || manifest`, context `"AIUEFRS1"`; Ed25519 signs the 64 manifest bytes (so the magic keeps an Ed25519 signature made for
another kind from verifying here, and the context keeps the ML-DSA half apart in the other direction). The kernel selects the kind by the call
(bit 2 of `admit`'s test argument: 5 = TEST keys, 4 = production set, which is not pinned), never by the magic. Same pinned slots, same 2-of-3
rule, same skip-never-count rule.

**Admission order and codes** (word 180): `2` magic (an image or catalog magic included), `5` manifest bytes 36..63 not zero, `3` signature
count / layout bytes 68..127, `8` no production signer set, then the per-entry signatures, `1` fewer than two distinct valid signers, `3` the
structure (issued-at below 1 or at or above 2^63, valid-until not above issued-at or at or above 2^63, **lifetime above 30 days = 2592000 s**,
channel not 1), `4` version below 1 (or at or above 2^63), `15` verified. A record that is verified is then judged against the clock.

**Which clock, and the verdict** (word 273, set only when the result is 15). `now` is the RTC read by `rtc-now`: update-in-progress flag awaited,
two snapshots that agree, register D bit 7 (the RTC kept power) set, BCD or binary and 12 or 24 hour as register B says, the century register 0x32
used when it holds BCD 19..21 and otherwise 20 assumed, every field range-checked (day against the month and leap year), and the result refused
(status word 365 = 1, 2, 3 or 5) when it is **earlier than the build floor 2026-11-06T00:00:00Z** compiled into the kernel (the usual dead-RTC
resets, 1970, 1980 and 2000, are all earlier). Verdict: `1` fresh (`issued-at <= now + 86400` and `now <= valid-until`); `2` expired; `3` the clock is
more than a day behind issued-at (the clock is wrong, or was set back: the record cannot be judged); `4` no usable clock. The one day of
slack on issued-at, and the lack of any on valid-until, cover an RTC kept in local time (up to 14 hours either way: a record then expires up to 14 hours
early or late, which a 30-day window absorbs). Verdicts 2, 3 and 4 are all "not fresh".

**What each state does** (the update manager's `check` is not built; this is the rule it must follow, and word 273 is its input):

| Record | `check` | Install | Version floor |
| -- | -- | -- | -- |
| fresh (1), version above the installed one | "update to V available", with issued-at | unchanged: only the image's own admission and the floor decide | unchanged |
| fresh (1), version not above | "up to date as of issued-at" | unchanged | unchanged |
| expired, behind or no clock (2, 3, 4) | "**not fresh**: cannot tell whether a newer version exists"; a signed version above the installed one is still shown as "at least V exists" (a signed record is a true lower bound however old) | unchanged: a verified newer image installs | unchanged |
| missing, or refused (any result but 15) | exactly the same "not fresh" line; a refused record contributes no data | unchanged | unchanged |

A record never authorizes an install and never moves the floor; only a committed install advances it (Amendment 4). Nothing about freshness
blocks an offline device, as Amendment 2 required.

**Monotonic rule (decided, not built).** Rule: a record is accepted for display only if its issued-at is not below the issued-at of the last record
this device accepted, and the trusted lower bound of the clock is `max(build floor, last accepted issued-at)` (a record's issued-at is the signers'
own time, so it is a lower bound on the present that no clock attacker can lower). This stops an attacker who is serving an older, still unexpired
record (R1, v5, valid to day 30) after the device has seen a newer one (R2, v6, issued day 10): without the rule R1 is "fresh" until day 30 and hides v6.
It needs persisted state, and `OSMETA.BIN`'s journal can hold it: its record has 16 bytes at 48..63 that `valid` requires to be zero today (and
352 at 128..479), the record schema word is 1, and the SHA-256 at 480 already covers them. Missing: schema 2 with `valid` accepting bytes 48..63
(last issued-at `u64`, last version `u64`), a journal operation that updates them with the journal's own crash-ordered `publish`, the change in
`aiueos-provision-esp.py`, and the journal's gates for the new schema. A kernel that predates schema 2 would read the new record as invalid and
refuse every update (fail closed). Until that lands the exposure of a replayed record is its remaining validity, at most 30 days.

**What this stops, and what it does not.**

| Who | Can they make a stale record look fresh? | Why |
| -- | -- | -- |
| A mirror, peer or on-path attacker (the Amendment 1 threat) | **No** | They can serve only bytes. They cannot set the RTC, and the kernel reads no time from the network. They can still withhold; the device then reports "not fresh" once the last record it has expires |
| Anyone who replays an old record | Only for its remaining validity (at most 30 days); with the monotonic rule, not after the device has seen a newer one | Signed records cannot be forged or extended (the tamper cases in the gate) |
| A disk-write attacker | Not by writing the disk alone | The RTC is not on the disk. Replacing `BOOTX64.EFI` gives them code that can set the RTC, but then they own the machine and the freshness of a record is the least of it (Amendment 4) |
| Someone with the firmware setup screen or physical access | **Yes**: set the RTC back inside the old record's window | The RTC is whatever the firmware says. The build floor and the persisted lower bound narrow it, they do not close it |
| A dead RTC battery | Fails safe: the reading falls below the build floor, so "no usable clock" and "not fresh" | |
| A hypervisor or the VM host | **Yes**, completely | It supplies the RTC (measured under QEMU: the guest reads exactly what `-rtc` says) |
| Any attacker, for the *signers'* clock | n/a | The signers' issued-at is trusted as signed |

Not used as clocks, and why: an NTP/SNTP reply, a TLS or HTTP `Date` (unauthenticated or served by the very source being checked: the
withholding attacker controls it, so it is strictly worse than the RTC against the stated threat); the TSC (it counts from boot and says nothing
about the date); a signed time statement carried in the record (it is a lower bound only: it can prove time has passed, never that none has).

**Built and gated.** `update.kotoba` admits `AIUEFRS1` as a third kind with the existing signature-block machinery, reads the RTC, and keeps the verdict
in words 273..280; QEMU hooks `opt/aiueos/fresh` (cases) and `opt/aiueos/clock` (RTC probe and decoder rows) only; not wired to the desktop, no
`check`, nothing persisted, no production signer set. Gate `fresh` (`check-native-fresh-qemu.py`, `fresh_oracle.py`). Results, mutants and what was
not verified are in the evidence README and the pull request.

**Documentation that disagreed with the code (corrected in this change).** The Status paragraph above said "Design only, nothing here is implemented" although `native/update.kotoba` implements stages 5a to 6; and `distributions/awai/update-policy.json` said the ML-DSA-65 verifier was open work and that versions "must rise (>= 1)". Both now state the real state (comments and text only).
