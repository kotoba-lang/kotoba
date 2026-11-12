# ADR-0284 — Install, update and delete of Itonami dapps are signed by the user's key

Date: 2026-11-04

## Status

Proposed (owner request 2026-11-04, JUN-820). Design only: nothing here is implemented, and no row is claimed. It fills the
"installed-state schema" and "delete" gaps that ADR-0283 and JUN-812 left open, and it creates no kernel, ABI, signer or
trust root. Extends ADR-0275 (W3 wallet sign, W4 CID open, W5 dapp grant), ADR-0282 (dapps run offline) and ADR-0283
(Itonami Apps, Updates, signed catalog).

## Context

Measured in the source (2026-11-04):

- Today only a boot-time catalog exists: `contracts/boot-v1.edn` `:kotoba-app-catalog` (capacity 4, two entries, 16-byte
  ids, SHA-256, RSA2048 PKCS1 v1.5, unknown id rejected) and `:kotoba-app` (looked up by signed catalog id, up to 98,304
  bytes, policy key baked into the kernel). Changing it means re-signing and rebuilding the image.
- No user-facing install, update or delete exists. ADR-0283 §3 says Itonami Apps installs by digest from a signed catalog,
  but names no publisher key, no catalog origin and no installed-state schema (JUN-812 lists these as open), and says
  nothing about removal.
- ADR-0283 §2 / JUN-811 replace the four fixed cards with a signed variable-length catalog (`app-catalog.sig`) read as
  data. That is the discovery list; it is not a record of what this machine installed.
- A web3 dapp separates three things: the code (addressed by hash), who published it, and which user chose to run it. The
  current design merges them into one image-level signature.

## Decision

Three roles, three signatures, no new root of trust.

1. **A dapp is a content-addressed bundle.** A manifest (`itonami.dapp.v1`, as in `distributions/awai/dapps/<id>.json`:
   dock-independent id, local core, local state, declared remote operations, `"dns": "never"`) and its code are named by
   CID (raw CIDv1, SHA-256, admitted by `aiueos.cid-v1-admit`). The app id shown to the user is derived from the manifest
   CID, so a changed byte is a different app. Launch re-hashes the bytes and refuses a mismatch (W4).
2. **The publisher signs provenance only.** A publisher DID signs the manifest CID (Ed25519 now; ML-DSA-65 when its
   verifier exists, as in ADR-0283). A valid publisher signature means "this manifest came from that DID". It does not
   mean "trusted": whether a publisher is trusted is the user's choice (point 4).
3. **The user's key signs the local install state.** The device key (W3 wallet, ADR-0270) signs an append-only install log
   kept in the draft store. Record kinds:

   | Kind | Fields (canonical, length-prefixed text) | Meaning |
   |---|---|---|
   | `install` | `manifest-cid`, `bundle-cid`, `declared-ops-digest`, `publisher-did`, `source` (`os-image` / catalog id), `seq`, `prev` | this user chose to install this exact bundle |
   | `tombstone` | `manifest-cid`, `reason`, `keep-state` (bool), `seq`, `prev` | this user removed it |
   | `trust` / `distrust` | `publisher-did`, `seq`, `prev` | the user's publisher trust list |

   `seq` rises by one and `prev` is the SHA-256 of the previous record, so a record cannot be dropped or reordered
   without breaking the chain. The installed set is the fold of the log: the last record per `manifest-cid`. A log signed
   by another device's key, or with a broken chain, is refused as a whole and the machine shows the shipped defaults only.
4. **Trust roots stay where they are.**
   - System layer: the kernel-baked catalog and the OS image signature (ADR-0274/0283). Apps shipped in the image are
     `source: os-image`.
   - User layer: the user's publisher trust list. The distribution may ship a signed *suggested* list; an entry becomes
     effective only as the user's own `trust` record. Nothing the network supplies can add a root.
5. **A default app is a pre-seeded install record.** The distribution ships the `install` records of its default apps
   (`source: os-image`). They are ordinary records: the user can tombstone them, and the OS image does not need a rebuild
   to hide a default app. The dock shows `fold(log)` plus the system apps below.
6. **System apps cannot be removed.** `tokei`, `wifi`, `bluetooth`, `settei`, `itonami-apps`, `updates` are part of the
   image (a tombstone for them is refused). Everything else, including the default dapps, can be removed.

### Install

`Itonami Apps` lists the signed catalog (ADR-0283; offline copy first). Choosing an entry:

1. Show the manifest's declared operations (W5) and the publisher DID with its trust state, before any request.
2. `fetch-catalog` and `download-app` are external operations, each with its own fresh approval naming service, endpoint,
   operation and data (shared contract). Denial sends nothing; there is no fallback and no app-origin proxy.
3. Admit: bundle bytes hash to the CID; manifest CID matches; publisher signature verifies; `declared-ops-digest` equals
   the digest of the manifest's `remoteOperations`. Any failure stores nothing.
4. The user signs the `install` record. The effective operation set starts with **no approvals** (W5); install is not
   consent for any operation.

### Update

An update is a new bundle with a new manifest CID, installed beside the old one. Before the user signs the new `install`
record, the app shows a diff of declared operations against the installed one. A larger operation set, a new endpoint
origin or a new data category needs a fresh explicit approval; a smaller or equal set may proceed on the install approval
alone. The old bundle stays until the new one is admitted and launched once (rollback = a new `install` record naming the
old CID; no bytes are re-fetched if still present). Auto modes in `update-policy.json` only raise a prompt (ADR-0283 §4);
they never sign.

### Delete

The user signs a `tombstone`. The bundle may be garbage-collected after a tombstone and a quiet period; the app's local
state is erased unless `keep-state` is true, and the choice is shown before signing. A tombstone cannot be forged by an
app: only the device key signs, and the signing prompt is a shell surface (W1), not app UI. Re-installing the same CID
later is a new `install` record. A publisher the user no longer trusts gets a `distrust` record; installed apps from that
publisher keep running until the user chooses, but their updates are refused.

## Relation to the data-driven catalog (JUN-811, JUN-812, ADR-0283)

| Concern | Owner | Note |
|---|---|---|
| What can be installed (discovery) | signed catalog / `app-catalog.sig` | publisher-or-distribution signed, variable length |
| What is installed here | user-signed install log (this ADR) | the JUN-812 "installed-state schema" |
| What is on the dock | `fold(log)` + system apps | JUN-811 reads the app list as data from this fold |
| What an app may do | its declared ops + each-operation consent | unchanged |

The catalog never marks anything installed, and the log never carries authority: it records the user's choice. JUN-811's
native frame ABI v3 should take its app count and titles from the fold, so a delete is a dock change with no rebuild.

## Not decided here (owner)

- Catalog origin and the signing key (none registered); the install log's on-disk object format and capacity.
- Whether a tombstone for an `os-image` default is stored as a record or as a hide flag (this ADR says record).
- ML-DSA-65 for publisher and update signatures (Ed25519 is below the post-quantum floor, as ADR-0283 states).
- Torihiki: owner decision 2026-11-04 enables order submission in the hosted session, **devnet / demo only** (JUN-822). The
  session signs a transaction with its own non-extractable Ed25519 key (a throwaway devnet key, not a wallet) and sends it to
  the node endpoint the user typed, after approving the displayed operation (`read-quotes`, `read-account`,
  `request-devnet-funds`, `submit-order`; each lists its requests and data). Nothing is signed or sent unless the node's chain
  id contains `devnet`. Torihiki is an exchange sequencer on a devnet whose collateral is unbacked, so a mainnet or bridged-collateral chain stays refused by the chain-id guard. Real money, custody and settlement remain out of scope until owner, legal and the torihiki
  decentralization roadmap (D1–D4) approve. Open: the signing payload is a positional 37-field string that follows the
  node's engine version, so a node on another version rejects every signature as `bad-signature`.

## Consequences

- Installing and deleting need no image rebuild and no new kernel trust root; the system layer is unchanged.
- The user's key becomes load-bearing for the local app set: losing it loses the right to alter the log (W3 backup, ADR-0279,
  covers recovery).
- The native renderer budget (8192-byte surface, 259 ops) still bounds how many apps one frame can list; paging stays in
  JUN-811.
- Verification of the log chain and the CID/signature checks are pure functions; they can be written in Kotoba with
  negative controls (tampered byte, wrong device key, dropped record, reordered record, widened operation set).

## Verification now

`scripts/check-dapp-records.py` (host-side JSON check) covers the install record for `torihiki`; `scripts/session-torihiki-test.js` checks
the page's signing payload and account derivation against vectors the torihiki engine produced. The log, tombstone and update
rules above have no gate yet; each becomes a row only when its own gate prints its marker.
