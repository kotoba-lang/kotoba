# Content protocol

This plane owns object shape and the two link kinds. It does not collapse URL,
DNS, HTTP, Git, package-manager, and RPC concerns into one Merkle DAG.

## Two link kinds

Defined by `kotoba.protocol.layers/link-kinds`:

```text
:merkle  edge is block content       parent CID changes    IPLD / Git tree / Nix closure
:action  edge is signed metadata     parent CID unchanged  Holochain CreateLink / datom
```

A published Wasm import table, a CID inside a datom snapshot, and a Git-tree
blob link are Merkle links. Pinning and verification cover that exact closure.

An assertion added later—"this entry now points to that entry"—is an action
link. A datom such as `[e :kotoba.link/to b tx true]` has the same shape: the
value CID remains stable while the ordered action-log snapshot advances.

Merkle links alone require republishing a parent every time an edge is added.
Action links alone cannot prove a distribution closure with one CID. The
protocol needs both and keeps them distinct.

## Executable graph algebra

`kotoba.protocol.graph` provides:

- `put-node` — rejects a different body or Merkle-link set under the same CID
  with `:cid-mismatch`
- `merkle-child` — produces a new node identity when a child is added
- `create-link` — leaves node maps unchanged and advances only the dirty action log
- `log-state` / `commit-log` — commits the ordered action log through an injected
  `chain.core/commit!`-shaped function; this repository does not hash it
- `neighbors` / `walk` — traverse a selected link kind without conflating the two

The committed L2 graph CID is hasher-owned. An archive `Location` may use the
raw CID of the same bytes; location codec and graph identity remain distinct.

## Surface projection

| System | Identity | Structure | Naming |
|---|---|---|---|
| Git | blob/commit SHA | tree/commit Merkle links | ref |
| Nix | NAR hash and derivation hash | closure | attrpath or lock |
| Unison | term hash | none; names are namespace entries | local name |
| Holochain | EntryHash / ActionHash | CreateLink action | DNA/role |
| HTTP URL | none; it is a location | none | path projection |
| DNS | none | none | mutable naming |
| RPC | call-object CID | result is a separate object | capability name |
| IPFS UnixFS path | not a public identity | host-side walk only | not used |

L1 datoms are the fact surface of the content protocol. L5 app manifests are an
application built on those facts. Full projection data lives in
`kotoba.protocol.surfaces`.

## Client-held confidentiality

IPFS, IPLD, and IPNS do not specify Storj-Uplink-shaped client encryption.
Confidentiality is therefore a content-protocol object shape, not a ninth
communication plane (ADR-2608070400, ADR-2608161600).
`kotoba.protocol.sealed` is the composition algebra; this repository still
does not wrap keys or ratchet.

| Construction | Implementation | Protects | Forward secrecy |
|---|---|---|---|
| `:object` | `envelope` | bytes at rest; one content key, many wraps | no |
| `:session` | `org-signal` | sender to recipient (X3DH + Double Ratchet) | yes |
| `:hop` | `noise` | adjacent libp2p peers | hop only |
| `:ipns` | `tech-ipfs-specs-ipns` | authenticity of a pointer, not secrecy | n/a |
| `:dag-jose` | draft IPLD container | JWE/JWS bytes | no; not a ratchet |

A Signal ciphertext may be stored under an object CID. That is composition.
Using envelope as the per-message construction, or treating Noise as E2EE,
is `:construction-mismatch`. IPNS publishes a prekey-bundle CID and a
mailbox head CID; it does not encrypt them. One-time prekey consumption
cannot be guaranteed by a content-addressed store alone. Convergent
encryption is forbidden: identical plaintext must not produce identical
ciphertext CIDs.
