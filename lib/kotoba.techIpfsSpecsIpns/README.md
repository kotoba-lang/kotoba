# ipns

`kotoba-lang/ipns` is a small EDN-first library for **libp2p-key IPNS names**
— the `k51…` name (a CIDv1, identity-multihash, of the libp2p `PublicKey`
protobuf) deterministically derived from an Ed25519 public key.

An actor's graph IS its key: holding the Ed25519 private key is authority
over the graph named by `pubkey->name` — no registrar, no owner hand-off, no
shared token. This is the naming half of the same discipline `kotoba-lang/did`
covers for `did:key` — the two are siblings derived from the same raw pubkey,
kept as separate libraries because they are different specs (W3C DID vs.
libp2p/IPFS naming), not different concepts of identity.

## Two record formats, deliberately

| ns | format | who can validate it |
|---|---|---|
| `ipns.record` | **the IPNS Record of specs.ipfs.tech** — protobuf whose `signatureV2` covers a DAG-CBOR `data` field | Kubo, Helia, every IPFS implementation, the libp2p DHT |
| `ipns.head` | a kotobase-shaped map (`{:name :value :sequence :valid_until}`) | kotobase.net's own XRPC registry, and nothing else |

`ipns.pubsub` is the transport-neutral state/effect core for the standard IPNS
PubSub Router. It derives `/record/<base64url-unpadded(binary-routing-key)>`,
validates every protobuf record before selection, persists and republishes only
a strictly better record, and emits the Fetch effects that make PubSub updates
persistent. A libp2p host executes those effects; this library does not pretend
that an in-memory state machine is a live GossipSub/Fetch transport.

`ipns.head` came first and is not wrong — it is a local registry's record. But
it is **not** an IPNS record, so publishing those bytes to the DHT would put
something on the network that every peer rejects. Getting the format right is
therefore a strict prerequisite to any DHT transport, not a parallel concern.

### `ipns.record` — the parts that fail silently

**The signature covers the CBOR, not the protobuf**: `sign(key,
"ipns-signature:" || data)`. Signing the protobuf is the obvious-looking
mistake and produces a signature no implementation accepts, because a validator
rebuilds that exact input from the `data` field it received.

**The protobuf duplicates what `data` already says** — `value`, `validity`,
`validityType`, `sequence`, `ttl` — for readers that predate V2. `validate`
checks the two copies agree. Without that check, an attacker signs one CBOR and
then rewrites the unsigned protobuf half: the signature still verifies, and the
record reads differently depending on which half you look at. There is a test
for exactly that.

**V1-only records are refused.** V1 signatures were forgeable by rewriting the
unsigned fields, which is why V2 exists; accepting V1 "for compatibility"
reopens it.

**The routing key is `/ipns/` + the *binary multihash*** — not the text name,
not the CID. A peer that builds it from `"/ipns/k51…"` computes a different key
from every correct implementation, and its records land at an address nobody
looks at. Stored successfully, invisible forever.

**`ttl` is nanoseconds** and **`validity` is RFC 3339 with exactly nine
fractional digits**. Reading the TTL as seconds gives a record that is valid
and cached for a wildly wrong duration; a looser timestamp is refused because a
record this library cannot reproduce byte-identically is one whose signature it
will break.

## Usage

```clojure
(require '[ipns.core :as ipns])

(ipns/pubkey->name (vec (range 32)))
;; => "k51qzi5uqu5dg6lcd99r9gmb963kgugjinxxggwy7o93oagk3f2eg3qcjh7127"

(ipns/name->pubkey "k51qzi5uqu5dg6lcd99r9gmb963kgugjinxxggwy7o93oagk3f2eg3qcjh7127")
;; => [0 1 2 3 ... 31]
```

`pubkey->name` accepts either a JVM `byte[]` or a plain Clojure int vector —
callers on the JVM (e.g. an actor holding a `java.security.PublicKey`) pass
the raw 32-byte public key directly.

## Scope

- `ipns.core` (zero-dep, portable `.cljc`):
  - `pubkey->name` — Ed25519 raw public key → CIDv1 libp2p-key IPNS name (`k51…`)
  - `name->pubkey` — inverse decode, with structural validation
  - `name->pubkey*` / `name-matches-pubkey?` — the **fail-closed** pair a
    verifier uses (see "The name is the key" below)
  - `base36` / `base36-decode` — the underlying multibase codec, portable
    `.cljc` (no `BigInteger`, so it runs identically on ClojureScript)
  - Verified byte-identical to a real go-ipfs/Kubo node's IPNS name for
    the same key (`matches-a-real-kubo-node` test — an actual `ipfs
    init`/`ipfs id`/`ipfs cid format` run, not just cross-checked against
    this repo's own prior art).
- `ipns.head` (`:clj`-only — pulls in `ed25519`/`dag-cbor`, `ipns.core`
  itself stays free of them): `sign`/`verify` a mutable IPNS **head
  record** (`{:name :value :sequence :valid_until ...}`, the kotoba
  lexicon `head.json`/`publish.json` shape) over a canonical dag-cbor
  payload, via `ed25519`'s did:key primitives (ADR-2607061800).
- `ipns.pubsub` (portable `.cljc`): exact topic derivation plus a bounded
  validate/select/persist/republish state machine. Network I/O is expressed as
  effects (`:pubsub/subscribe`, `:pubsub/publish`, `:fetch/*`, `:persist/put`)
  for an `io-libp2p` host adapter to execute.

Not in scope: opening a real IPFS/libp2p connection or implementing GossipSub
and libp2p Fetch framing (host-port concern, see `kotoba-lang/io-libp2p`);
kotobase.net resolves
`ipns.head` records through its own XRPC registry instead, ADR-2607061800),
any DID method (see `kotoba-lang/did`), or a `:cljs` port of `ipns.head`'s
signing (tracked follow-up — `kotobase-client` already has a `@noble/curves`
precedent in its own `cacao.cljc` to port from).

## The name is the key — and a verifier has to act like it

This library's claim is that holding the Ed25519 private key *is* authority
over the name `pubkey->name` derives from it: no registrar, no hand-off, no
shared token. That claim is only true if **every verifier resolves the
authoritative key from the name.**

Until 2026-08-04 `ipns.head/verify` did not. It checked that the record's own
`:public_key_multibase` had signed the payload, and never that that key is the
one `:name` names. Since anyone can make a keypair, anyone could sign a record
carrying somebody else's `k51…` and have it verify — and
`kotobase.server.ipns/verify-and-decide-publish`, whose only other gate is
sequence monotonicity, would accept it. That is takeover of an arbitrary name
in kotobase.net's registry, and `head_test/name-takeover-is-refused`
reproduces it against the unpatched code rather than describing it.

`ipns.record/validate` never had the bug — it derives the pubkey with
`name->pubkey` and verifies against *that*, which is the correct shape. The
fix generalises that discipline into `ipns.core/name-matches-pubkey?` so both
record formats, and the ClojureScript twin in `kotobase-client`, share one
predicate instead of three chances to get it wrong:

```clojure
(ipns/name-matches-pubkey? name pub)   ; => true only if name IS pubkey->name(pub)
```

It is fail-closed by construction: a malformed name, a `nil` key or a key of
the wrong length returns `false`, never a throw, because a verifier whose
caller must remember a `try` will meet the adversarial input on the path
where they forgot.

Superproject decision record: **ADR-2608047000**.

## Provenance

This replaces a byte-for-byte-identical derivation that had been copy-pasted
into two JVM actor-identity call sites — `kotoba-lang/kekkai`'s `cacao.clj`
(`ipns-name`) and `kotoba-lang/kagi`'s `identity.clj` (`ipns-name`) — each a
private `BigInteger`-based reimplementation of the same libp2p-key CIDv1
construction. Both are cross-checked against this library's output
byte-for-byte (see ADR-2607050100).
