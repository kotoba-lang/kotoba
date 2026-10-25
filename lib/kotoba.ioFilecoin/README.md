# io-filecoin

`filecoin.*` — a **Filecoin protocol client** for the kotoba-lang stack:
addresses, messages, the bytes a signature covers, and the Lotus JSON-RPC
surface, as **portable `.cljc` over injected crypto and transport**.

Companion to [`io-filecoin-node`](https://github.com/kotoba-lang/io-filecoin-node)
(the other end of the network — what a node *is*) and
[`cloud-filecoin`](https://github.com/kotoba-lang/cloud-filecoin) (Filecoin
Onchain Cloud: PDP, Filecoin Pay, Warm Storage). Sibling of
[`io-storj`](https://github.com/kotoba-lang/io-storj) and
[`io-ipfs`](https://github.com/kotoba-lang/io-ipfs).

| Namespace | What it owns |
|---|---|
| `filecoin.address` | `f0`–`f4`, both encodings, and every reason one is invalid. |
| `filecoin.message` | The 10-element array, its CID, and **the bytes signatures cover**. |
| `filecoin.signature` | Signature types, signed messages, and which CID names one. |
| `filecoin.bigint` | attoFIL and its arithmetic, on runtimes that cannot hold it. |
| `filecoin.cid` | CIDv1 + dag-cbor + BLAKE2b-256 — the chain's one CID shape. |
| `filecoin.rpc` | Lotus JSON-RPC bodies, and message ⇄ JSON. |
| `filecoin.method` | FRC-0042 — method **numbers**, derived from names. |
| `filecoin.varint` | Unsigned LEB128, in arithmetic rather than 32-bit shifts. |
| `filecoin.protocols` | The seams: `IHttp`, `ISigner`, `IVerifier`. |

## Usage

```clojure
(require '[filecoin.address :as addr]
         '[filecoin.message :as msg]
         '[filecoin.signature :as sig]
         '[filecoin.rpc :as rpc])

(addr/from-string "f1xpbyy4tkdx5si2bgo37dubc2xwv6fum5tk57mia")
;; => {:protocol 1 :payload [...] :network :mainnet}

(addr/from-eth-address "0xff00000000000000000000000000000000000064")
;; => the f410f… address for an FEVM contract

(def m (msg/message {:to "f1…" :from "f1…" :nonce 12
                     :value (bigint/fil->atto "0.5")
                     :gas-limit 2000000 :gas-fee-cap "100000"
                     :gas-premium "99000" :method 0}))

(msg/cid m)                     ; => "bafy2bzace…"
(msg/signing-bytes m)           ; what a BLS signer signs
(msg/digest-for-secp256k1 m)    ; what an ECDSA signer signs

(def signed (sig/signed-message m (sig/signature sig/secp256k1 sig-bytes)))
(sig/cid signed)                ; the CID the chain will know it by

(rpc/http-request (:mainnet rpc/endpoints) (rpc/mpool-push signed))
;; => {:method :post :url … :headers … :body "{\"jsonrpc\":\"2.0\",…}"}
```

## Design

**Zero network I/O, zero key handling.** The library builds request maps and
hands them to your `IHttp`; it produces bytes to be signed and takes back a
signature through `ISigner`. So the same code runs on a JVM, in a Cloudflare
Worker, under nbb, or behind a WASM capability import — and a private key can
stay in a Keychain, a KMS or a browser extension without this code knowing.
Same contract as `kotoba.lang.ipfs` and `storj.core` (ADR-2606302300 §Step-1).

**Amounts are decimal strings, never numbers.** A balance is attoFIL: the
total supply is 2×10²⁷, which is nine orders of magnitude past what a
JavaScript `Number` represents exactly. `filecoin.bigint` is the only place a
platform big-integer appears, and `fil->atto` does its decimal shift by string
surgery rather than by multiplying a float by 10¹⁸. Its `div` is **Euclidean**,
matching `math/big.Int.Div`: both runtimes divide by truncating toward zero and
Go does not, so a direct translation is off by one for every negative
numerator — which is the sign the gas formulas divide with most of the time.

**Two encodings of a message, and they are not renames of each other.** The
chain form is a definite-length 10-element CBOR array with sign-magnitude byte
strings; the RPC form is a JSON object with capitalised keys, decimal-string
amounts and base64 params. Both are written out in full, because deriving one
from the other by renaming is how a field ends up in the wrong slot — and a
message with `value` and `gas-limit` transposed is not invalid, it is a valid
message that sends a different amount.

**What gets signed, exactly — and the three answers are different.** `encode`
→ CBOR; the binary CIDv1 of that (dag-cbor + BLAKE2b-256) is `signing-bytes`.
A **BLS** signature covers those bytes; **secp256k1** signs `BLAKE2b-256`
**of** those bytes — hashed twice in total, and `digest-for-secp256k1` applies
the second hash so a signer does not have to know that.

**Delegated (type 3) is not a third variation of this.** It covers the
**RLP-encoded unsigned Ethereum transaction**, keccak-256 hashed — not the CID
in any form. Lotus reconstructs the Ethereum transaction from the message,
requires the round-trip to be byte-identical, and verifies against that. So
this library can decode, name and verify-by-CID a delegated message, but
**cannot produce the payload to sign a new one**: RLP and keccak-256 are both
absent, and keccak has no portable implementation in this workspace. Sending
to an FEVM contract without that is still possible — see `filecoin.method`.

## What is not here

- **secp256k1 and BLS12-381.** Signing and verification are seams.
  secp256k1 exists in this workspace already
  ([`kotoba-lang/eth-crypto`](https://github.com/kotoba-lang/eth-crypto));
  BLS12-381 — which `f3` addresses and block signatures need — does not, and a
  pairing-friendly curve is not something to write on the way to a client.
- **Namespaces and actor IDs above 2^53.** `filecoin.varint` refuses them.
  go-address allows up to 2^63-1, but a JavaScript `Number` stops being exact
  at 2^53, and a value that is one number on the JVM and a different one under
  nbb is worse than an error. Mainnet's only allocated `f4` namespace is `10`
  and actor IDs are in the millions, so this is a spec boundary rather than a
  practical one — but it is a refusal, with a test, not a silent rounding.
- **State.** No actor state, no HAMT/AMT traversal, no FVM. `StateGetActor`
  will return you a state root CID; reading what is under it is
  `io-filecoin-node`'s problem, and mostly not solved there either.
- **Retrieval and deals.** No Graphsync, no bitswap, no storage market. The
  modern path for putting data on Filecoin is Onchain Cloud — that is
  `cloud-filecoin`.

## Verification

The address vectors are **upstream's**, regenerated from
`filecoin-project/go-address`'s own `address_test.go` by
`testdata/gen_vectors.cljk`. An address implementation that only agrees with
itself is worth nothing.

The message vectors are **mainnet's**. `testdata/gen_chain_vectors.cljk`
snapshots real messages off the public Glif endpoint together with the CIDs the
network gave them; the suite recomputes each CID from scratch. That single
assertion covers address bytes, sign-magnitude amounts, field order,
definite-length CBOR, BLAKE2b-256, the multihash prefix and base32 at once —
and there is no way to pass it by agreeing with oneself. Ten messages, BLS and
secp256k1 and delegated (FEVM), including a 29,409,837,650,000,000,000 attoFIL
transfer that a `Number` cannot hold.

The division vectors are `math/big`'s **contract** rather than a table of
quotients: for every sign combination, `x = y·q + m` with `0 ≤ m < |y|` is
asserted directly, because a table only catches the cases someone thought to
write one for.

Both runtimes run the whole suite, because nearly every line above names a
place where they differ. **430 assertions, green on both.**

```sh
kbb -M:test                 # JVM
npm run test:cljs               # nbb
kbb --backend sci testdata/gen_vectors.cljk > test/filecoin/vectors.cljk   # regenerate
```

The chain vectors are deliberately **not** regenerated in CI: the chain moves,
so a diff would always fail. They are a permanent snapshot — mainnet history
does not change.

## Scope — read this before using it

**No live request has ever been made against a node from this code.** The
mainnet vectors were fetched by a generator script; nothing in `src/` has
opened a socket, because nothing in `src/` can. `rpc/http-request` returns a
map for your transport to execute, and whether your transport gets the headers
right is not something this suite knows.
