# io-storj-node

`storj.node.*` — the **storage node** side of Storj, as portable `.cljc`:
identities, order limits, the bytes their signatures cover, and how a piece is
laid out on disk.

Companion to [`io-storj`](https://github.com/kotoba-lang/io-storj), which is
the client side and reaches Storj through the S3 gateway. This repo is the
other end of the network: not a program that talks to Storj, but the part of
Storj a node is.

| Namespace | What it owns |
|---|---|
| `storj.node.id` | Node IDs — base58check, the version byte, difficulty. |
| `storj.node.identity` | What a peer's certificate chain says, and whether to believe it. |
| `storj.node.der` | Just enough DER to read an X.509 certificate, and to write one. |
| `storj.node.certificate` | The two certificates a Storj identity is made of. |
| `storj.node.mint` | The proof of work, and the identity it names. |
| `storj.node.pem` | PEM and base64 — what an identity looks like on disk. |
| `storj.node.tls` | What a Storj TLS connection is, as data, and who may be on it. |
| `storj.node.pb` | The Storj messages, and **the exact bytes their signatures cover**. |
| `storj.node.orders` | Whether an order limit may be acted on, and every reason it may not. |
| `storj.node.piece` | Blob paths and the V1 piece header. |
| `storj.node.protocols` | The host seams: `IVerifier`, `IClock`, `IBlobStore`. |
| `storj.node.host.verify` | The reference `IVerifier` — the four schemes Storj presents. |
| `storj.node.host.keys` | The reference `IKeyMaterial` — key generation, signing, entropy. |
| `storj.node.host.tls` | Sockets. The one namespace here that decides nothing. |
| `storj.node.contact` | Check-in — the first thing a node says. |
| `storj.node.retain` | Which pieces to keep, and which to keep anyway. |
| `storj.node.service` | What a node answers when it is asked. |
| `storj.node.piecestore` | Storing a piece, and giving it back. |
| `storj.node.host.blobs` | An `IBlobStore` that keeps everything in memory. |
| `storj.node.host.rpc` | A DRPC call on a verified connection — the last joint. |
| `storj.node.bytes` | The one file that knows which runtime it is on. |

## Scope — read this before using it

**This is the protocol core of a storage node, not a storage node.** What is
here decides; what is missing does.

Implemented and tested on two runtimes:

- Node ID encoding, decoding, version handling and difficulty.
- Decoding `OrderLimit`, `Order`, `PieceHash`, `PieceHeader`, and reproducing
  the bytes Storj signs for each.
- Admission of an order limit: addressed to this node, unexpired, action
  matches, signature valid — with the crypto deliberately last.
- Blob path derivation and the 512-byte V1 piece header.
- Reading a peer's certificate chain, deriving its node id from the CA key,
  and admitting or refusing it — chain signatures, difficulty floor, expected
  id, identity version, extension rules.
- **Minting an identity**: the proof of work over CA keys, and the CA and
  leaf certificates that carry it — accepted by `storj.io/common` and
  byte-identical to what `identity.NewCA` produces for the same inputs.
- **Identity files**: reading and writing `ca.cert`, `ca.key`,
  `identity.cert` and `identity.key`, in Storj's layout. This is the part an
  operator actually needs — almost nobody mints an identity, and everybody who
  has one already has four files. `identity.FullIdentityFromPEM` loads what
  this writes, and what this renders is byte-identical to Go's own PEM.
- **What an upload and a download are allowed to be.** Chunks contiguous from
  zero, the order limit enforced as the bytes arrive rather than after, a
  second limit refused rather than ignored, and a `done` that must name the
  piece the limit named and the size that actually arrived. Driven by a real
  upload conversation built with `storj.io/common`.
- **Retain.** The bloom filter a satellite sends, and the decision under it.
  Checked against every answer Storj's own filter gives for the same ids —
  not a round trip, because a filter that decodes is not a filter that agrees.
  **Absence from the filter is not a reason to delete**: the filter was built
  at a moment, and a piece accepted after it cannot be in it.
- **Several calls on one connection.** `drpc.session` dispatches answers to
  the call that asked.
- **Answering a satellite.** `PingNode`, `Exists`, `Retain`, `DeletePieces`
  and `RestoreTrash` — the unary surface a satellite asks between transfers.
  A peer built from Storj's own `tlsopts` and `drpcconn` calls the node over
  mutual TLS in CI and reads the answer. Three of these read backwards from
  the obvious guess: `Exists` answers with *indices* rather than piece ids,
  `DeletePieces` counts what it could **not** do, and `Retain` decides without
  deleting anything.
- **Check-in.** `/node.Node/CheckIn`, byte-identical to `pb.Marshal`, and the
  response read as what it actually says: `ping_node_success` is the satellite
  reporting whether it could dial *back*, so a call can succeed while the
  introduction fails. Nothing in a check-in is signed — the mutual TLS
  underneath already named the node.
- **Mutual TLS.** Connecting and accepting with Storj's rules: no trusted
  roots, no hostnames, `RequireAnyClientCert`, and
  `storj.node.identity/admit-chain` in the place certificate validation would
  otherwise be. A live handshake against a peer built from Storj's own
  `tlsopts` runs in CI, in all four client/server × JVM/nbb combinations.
- Signature verification for all four schemes Storj presents: ECDSA-SHA256,
  ed25519 piece keys, and RSA under **both** PKCS#1 v1.5 (certificates) and
  PSS (messages) — checked against signatures Storj's own code produced, on
  both runtimes.

**Not implemented.** A node built on this would still need all of it. The
list below is what is actually absent, checked against the source rather than
remembered — an earlier version of this section claimed check-in and retain
were both implemented and missing.

*A piece moves, and is stored as a piece file when its hash was checked.*

`storj.node.transfer` drives `piecestore` one message at a time and
`host.rpc/serve-connection` carries it. A 300-byte piece goes up in four
messages and comes back in three, byte for byte, over real TLS and real DRPC
— both transfers on one connection, on two streams. What is still missing:

- **The uplink's signature on `done` is checked**, and `:hash-verified?`
  reports whether it was rather than leaving the caller to guess. The key is
  `uplink_public_key` in the limit — 32 raw ed25519 bytes, the one row in
  `host.verify`'s table that is not a DER SPKI — and the signed bytes are a
  `PieceHashSigning`, which drops the signature and drops the timestamp *when
  it is zero*, the opposite of an `OrderLimit`. Unknown fields are refused
  outright; an order limit keeps them. Held to a signature `gen_piecestore.go`
  produced with Storj's own code, so passing means an ed25519 signature made
  by Go verified against bytes rebuilt here.

  The wire path does not exercise it: the harness uplink sends no key and an
  unsigned `done`, so the node reports `hash-verified? false` and CI asserts
  that it says so. Signing one would mean this library's uplink signing its
  own upload for this library's node to check — weaker evidence than Go's
  signature, not stronger.
- **The node signs its own `PieceHash`** with its identity key. Not the CA
  key — the node id comes from the CA and every *signature* comes from the
  leaf (`SignerFromFullIdentity` uses `identity.Key`,
  `SigneeFromPeerIdentity` uses `identity.Leaf.PublicKey`). Getting that
  backwards gives a signature that is present, a key that is present, and a
  verification that fails for no visible reason, which is how it was found.
  `admit-chain` now hands back `:signing-key` so a caller that admitted a
  chain does not have to choose between the two certificates again. CI has
  the uplink check the node's signature against the key the handshake gave
  it.
- **A verified piece is stored as a V1 file**, header and body; an unverified
  one as a body (V0). The header carries the uplink's signature, which a
  later reader cannot check without the limit's key — so a header built from
  an unverified hash is a file that looks proven and is not. Reads try `.sj1`
  then the bare path, because a node can hold both and looking only for the
  format this build writes would report an older piece as `no such piece`.
- **A piece is buffered whole.** `IBlobStore/-put` takes a whole blob, so the
  streaming is real up to the store and stops there. That is a limit of that
  protocol, not of the transport.

*The transport can do more than this repo asks of it.*

`drpc` has streams and multiplexing; `storj.node.host.rpc` uses neither.

- **No streaming call is made or served here.** `drpc.session/begin-stream`
  and `drpc.server`'s per-message delivery exist and nothing in this repo
  calls them.
- **One call at a time per connection.** `drpc.session` dispatches answers to
  the call that asked, and `storj.node.host.rpc` still reads one call's answer
  off a socket directly. The decision exists; the wiring does not.

*Nothing is stored.*

- **The only `IBlobStore` forgets everything.**
  `storj.node.host.blobs/in-memory` exists so `Exists` and `DeletePieces` have
  something to answer from. Nothing writes to a disk and nothing survives a
  restart, which is not storage.
- **No streaming storage.** `IBlobStore` moves whole blobs; a real node
  streams and enforces the order limit as it goes — `within-limit?` exists and
  nothing calls it.
- **Nothing acts on a retain filter.** `Retain` decides and hands the decision
  to a callback; walking every piece a node holds for a satellite is hours of
  disk and is not scheduled here. `DeletePieces` does delete, because the
  satellite named those.
- **No piece expiration and no space accounting.** `free_disk` in a check-in
  is whatever the caller passes in.

*And the rest of the protocol.*

- **Settlement** (`SettlementWithWindow`) — how a node is paid — and
  **graceful exit**.
- **Revocation.** `2.999.1.2` is named in `storj.node.identity` and never
  read. A revoked peer certificate is admitted.
- **Noise and QUIC**, the newer transports.
- **The uplink side entirely** — erasure coding, encryption, segment
  metadata. That asymmetry is not an oversight: a node stores opaque shares
  and never decodes anything, which is exactly why the node side fits in a
  library like this and the client side does not.

## What a real satellite has actually accepted

A **check-in**, against `storj-up`'s satellite (1.158.2) on both runtimes,
with the satellite dialling this node back and being served. Its log:

```
node_id: 18zC3pJ2mQYCnuKgmjsrymmWsdTTaJHhai4Nv84jhfN34U58g1
node_addr: host.docker.internal:28967
ping_node_success: true
```

That node id comes from this repo's minter, and `ping_node_success` cannot be
true unless the satellite reached this process and got an answer to
`/contact.Contact/PingNode` — so a single exchange covers dialling out,
mutual TLS in both directions, DRPC framing both ways, and the reverse
handshake. The satellite's own certificate verified to
`12whfK1EDvHJtajBiAUeajQLYcWqxcQmdYQU5zX5cCf6bAxfgu4`, which is the value
storj-up records as `Satellite0Identity`.

Three things only a real peer found, all invisible to `testdata/tls_peer.go`
because it speaks plain TLS and serves whatever rpc name it is handed:

- **`drpc-mux-header`.** `"DRPC!!!1"` precedes the ClientHello in both
  directions. Absent it, the peer closes with no TLS alert and no log line.
- **`/contact.Node/CheckIn`**, not `/node.Node/CheckIn`. A test asserted the
  wrong one and passed. `testdata/gen_rpc_paths.go` now prints every path from
  `storj.io/common`'s DRPC descriptions and CI diffs them.
- A hand-built server-side `TLSSocket` emits **`secure`**, not
  `secureConnect`. The wrong event fails silently: the handshake completes and
  nothing is ever served.

**Beyond introduction, nothing has been tried against a real satellite.**
Pieces move between this library's own node and its own uplink, in CI; no
piece has been uploaded to or downloaded from anything on the Storj network.

## Verification

The parts of this protocol that matter cannot be checked against themselves.
Whether `encode-order-limit-for-signing` produces the bytes a satellite
actually signed is a question about gogoproto's treatment of `nullable=false`
fields and Go's definition of a zero time — and reasoning about it from the
`.proto` is precisely how one writes a plausible implementation that verifies
nothing.

So the expected values come from elsewhere:

- **Storj's own code.** `testdata/gen_vectors.go` links `storj.io/common` and
  asks `signing.EncodeOrderLimit`, `EncodeOrder`, `EncodePieceHash`,
  `NodeID.String()` and `PieceID.String()` what they emit. Those outputs are
  the literals in the tests.
- **Published identities.** The four satellite node IDs Storj publishes are
  decoded in full: length, version byte, double-SHA-256 checksum, difficulty.
- **A real generated identity.** `testdata/gen_identity.go` runs the same
  `identity.NewCA` a node operator does, and the resulting certificates are
  checked in. CI runs that program with `-verify`, which re-parses the fixture
  with `storj.io/common` and asserts the node id, version and chain
  relationships the tests claim — holding the fixture to the reference
  implementation rather than to a previous run of the generator.
- **The other direction.** Every other vector has the reference
  implementation produce bytes and this library assert it reads them the same
  way. `testdata/verify_minted.go` inverts it: this library mints a chain and
  `storj.io/common` is asked whether it is a Storj identity — parsed, both
  signatures checked, `peertls.VerifyPeerCertChains`, `NodeIDFromCert`,
  `PeerIdentityFromChain`, and the structural details down to which
  certificate carries a subjectKeyIdentifier. A parser agreeing with its own
  writer proves nothing, and reading a certificate correctly is not evidence
  that one can be written. Since identity files landed it goes further: the
  .cljc writes a whole identity directory and `identity.FullIdentityFromPEM`
  and `FullCAConfig.Load` read it back — 24 checks, including that each
  private key really is the key its certificate carries. CI mints afresh on
  both runtimes every run.
- **A live handshake.** The `tls` job runs a peer built from `tlsopts` and one
  built from this library against each other and requires both to name the
  other's node ID — client and server, JVM and nbb, four combinations. The
  greeting exchanged afterwards is not decoration: on TLS 1.3 a client that
  hangs up right after its own Finished leaves the server reporting EOF while
  the client reports success, which is what happened the first time this ran.
  Its last step makes a **DRPC call** on that connection, answered by a server
  built from `tlsopts` *and* `drpcserver` — every step a real node takes
  before it says anything, and then **checks in** — a real `CheckInRequest`
  parsed by `storj.io/common`'s own generated code, and a real
  `CheckInResponse` read back, on both the accepted and refused paths.
- **Byte-identical reconstruction.** Stronger still, and deterministic: given
  the serial, key and extensions of the fixture's real certificate,
  `storj.node.certificate` rebuilds its signed body and the result is equal,
  byte for byte, to what Go's `x509.CreateCertificate` emitted — 282 bytes
  for the CA and 268 for the leaf. A certificate that merely parses leaves
  room for a field encoded a legal-but-different way; equality does not.
- **Real signatures.** `testdata/gen_sigs.go` signs with `pkcrypto` and
  `storj.PiecePrivateKey` and records the result; CI runs it with `-verify`.
  Until this existed, `IVerifier` was stubbed everywhere and the entire
  admission path — certificate chains and order limits both — had never once
  seen a signature that could fail.
- **Both runtimes.** JVM and nbb run the same suite. SHA-256 comes from
  `MessageDigest` on one and `@noble/hashes` on the other, and varint
  handling has to survive JavaScript truncating bitwise operators at 32 bits.
  The verifier is the sharpest case: `java.security` on one side, Node's
  OpenSSL bindings on the other, asked the same four questions.

Reading the `.proto` and reasoning carefully produced an implementation that
was wrong in two independent ways, and the vectors caught both:

1. `limit`, `action` and `satellite_signature` were placed at field numbers
   8, 9 and 6. They are 6, 7 and 10.
2. An unset timestamp was assumed to reach the wire as `seconds = 0`. Go's
   zero time is year 1, so it arrives as `-62135596800`, and the signing form
   drops the field on that basis. Every satellite signature would have failed.

A third came from Storj's own encoder disagreeing with a round trip: the last
byte of a node ID is the **identity version**, not part of the hash. It is
zeroed on encode and rewritten on decode, and `Difficulty()` skips it.

A fourth would have been just as quiet: an OID whose first byte is 80 or
above encodes a first arc of 2, and dividing by 40 instead — the obvious
reading — turns Storj's `2.999.2.1` identity-version extension into
`24.39.2.1`, so every certificate would silently look unversioned.

A sixth was the same trap in a new message. `NodeVersion.timestamp` is
`(gogoproto.nullable) = false`, so gogo marshals a `time.Time` *value* and a
zero `time.Time` is still a value — the field goes out even when nothing set
it. Omitting it produced a `CheckInRequest` eleven bytes shorter than
`pb.Marshal`'s. The generator that caught it has a comment warning about
exactly this, written before the mistake was made.

A fifth is the one this repo went looking for rather than tripped over.
Storj signs *messages* with RSA-PSS and *certificates* with PKCS#1 v1.5 —
same key, same hash, two paddings. One RSA implementation used for both
questions does not raise an error; it reports a valid signature as invalid,
and only on the identities old enough to still use RSA. The fixture records
both signatures over the same message so each padding is checked against the
other's bytes.

Writing certificates added two more, both caught in the first hour:

6. **`[3] EXPLICIT Extensions` is two nested constructions**, not one —
   `Extensions` is itself a `SEQUENCE OF`. Emitting the extensions directly
   inside the context tag produces a certificate whose first extension's
   *fields* parse as extensions. The reader caught the writer: the rule that
   refuses duplicate extension IDs fired.
7. **A `loop` accumulator seeded from a rebound binding.** `loop` bindings are
   sequential like `let`, so seeding the output vector from `v` after `v` had
   been rebound to `(quot v 128)` collapsed every subidentifier below 128 to
   zero — which turned *every* OID into the same OID. Also caught by the
   duplicate-extension rule, which is the only reason it did not become a
   certificate that parsed and meant something else.

A near miss worth recording too: the first version of the serial-number test
asserted a 16-byte length, and a 128-bit serial encodes as 17 bytes whenever
its top bit is set. It passed about half the time. It was found because a
rerun disagreed with the run before it, not because it failed.

The suite has been checked to fail when each of those is reintroduced,
including deriving the node id from the leaf rather than the CA, dropping the
self-signature check that ends a chain, verifying PSS with PKCS#1 padding,
using a hash-length PSS salt instead of the largest that fits, and handing
ed25519 its raw key without the SPKI wrapper, flattening the extensions
context tag, seeding the OID accumulator from the rebound binding, emitting a
fixed unused-bit count, dropping an INTEGER's sign byte, accepting the first
key regardless of difficulty, signing the leaf with its own key, hashing the
whole SubjectPublicKeyInfo for the subjectKeyIdentifier, and tagging the
validity dates as UTCTime, swapping two letters of the base64 alphabet,
wrapping PEM lines at 76 characters, and skipping an unterminated PEM block
the way Go does.

Twenty-seven controls in total. The eleven for the verifier were run on both
runtimes, because that namespace is two implementations of the same four
questions; the eight for minting were run on the JVM, because the code they
break is shared `.cljc` and would fail identically on either.

Two of them silently failed to compile on the first attempt and reported
nothing at all. A control that produces no failure and a control that
produces no result look the same from a distance, and neither is evidence —
worth stating twice, because it happened twice.

A third control genuinely passed, and the fault was in the test rather than
in the code. Removing the unterminated-block check left the suite green,
because the test used `thrown?` and the missing check produced a
null-pointer exception instead of a refusal — which `thrown?` accepts just as
happily. Every refusal in `pem_test.cljc` now names *which* error, with
`thrown-with-msg?`. A test that accepts any exception is not testing the
refusal it claims to.

## Test

```sh
kbb -M:test                                              # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk
kbb -M:lint
cd testdata && go run gen_vectors.go                         # regenerate vectors
cd testdata && go run gen_sigs.go -verify                    # recheck signatures
kbb -M:mint /tmp/identity 16                              # mint an identity
kbb -M:tls-peer serve /tmp/identity 19443                # and speak TLS with it
kbb -M:tls-peer call /tmp/identity 127.0.0.1:19443 \
  <node-id-hex> /echo.Echo/Echo hello                        # TLS + DRPC in one
kbb -M:tls-peer check-in /tmp/identity 127.0.0.1:19443 \
  <node-id-hex> 127.0.0.1:28967                              # and a real check-in
cd testdata && go run verify_minted.go -dir /tmp/identity    # and let Storj load it
cd testdata && go run gen_identity.go -pem                   # rebuild identity.cert
```

`testdata/` is a vector generator, not a dependency: nothing under `src/`
links Go, and the library's own dependencies are two `.cljc` libraries
(`proto` for the wire codec, `io-multiformats` for base58/base32/SHA-256,
`drpc` for the framing and the shape of a unary call).
