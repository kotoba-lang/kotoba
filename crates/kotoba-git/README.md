# kotoba-git

`kotoba-git` is the byte-exact Git object bridge for kotoba.

Git is already a content-addressed DAG keyed by SHA-1 over framed object bytes.
kotoba stores blocks by CID. This crate keeps both identities:

- `git oid = sha1("<type> <size>\0<body>")`
- `kotoba cid = cid(framed-bytes)`

The SHA-1 side preserves Git compatibility. The CID side lets kotoba replicate,
query, encrypt, and cache objects using the same block substrate as the rest of
the system.

## Implemented

- blob/tree/commit/tag framed object codec
- byte-exact parse/materialize round trip
- Git tree entry parsing
- commit/tag header projection
- `:git/oid` to `:git.object/cid` Datom schema
- commit parents, tree entries, tags, refs projected to Datoms
- loose object import/export
- pack v2 / idx v2 import with OFS/REF delta resolution
- snapshot manifest and rehydrate of the queryable projection
- bounded zlib inflation and bounded delta depth for hostile repos

## Boundary

This crate does not decide repository authority. It only answers:

- what bytes does this Git object have?
- what Git oid do those bytes hash to?
- what CID stores those bytes?
- what refs are currently projected?
- what commit/tree/tag facts are queryable?

Repository identity, delegate authorization, private grants, and peer
accountability belong to the `kotoba-rad` layer described in
`docs/ADR-kotoba-rad-git-sovereign-repo.md`.

## Maturity

| Stage | Scope | Status |
|---|---|---|
| R0 | byte-exact Git object bridge | implemented |
| R1 | signed repo identity and ref authorization | `kotoba-rad` design target |
| R2 | encrypted private Git object blocks | `kotoba-rad` / `kotoba-crypto` design target |
| R3 | p2p warrants and reputation | `kotoba-dht` integration target |
| R4 | hybrid post-quantum envelopes and signatures | future |

## Privacy Rule

Do not treat Git refs or peer allow-lists as a secrecy boundary. For private
repositories, the future `kotoba-rad` layer must encrypt Git framed bytes before
untrusted replication and publish only ciphertext CIDs to non-recipient peers.

`kotoba-git` remains the plaintext fidelity core: after decryption, it verifies
that the framed bytes recompute to the expected Git oid and CID.
