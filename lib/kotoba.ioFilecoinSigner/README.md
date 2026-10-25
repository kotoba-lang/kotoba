# io-filecoin-signer

`filecoin.signer` — **secp256k1 signing for Filecoin**, the `f1` path, on both
runtimes. The seam [`io-filecoin`](https://github.com/kotoba-lang/io-filecoin)
leaves open, filled in for the one case that needs no new cryptography.

`io-filecoin` pins no curve on purpose, so the same message code runs on a
JVM, in a Worker or behind a WASM capability import, and a private key can
stay in a Keychain. This repo is a separate dependency for the same reason: a
caller who wants a curve pinned asks for it.

## Usage

```clojure
(require '[filecoin.signer :as signer]
         '[filecoin.message :as msg])

(signer/address-string priv)        ; => "f1…" — the account this key controls
(signer/sign-message priv message)  ; => a signed message, type 1
(signer/verify-message signed)      ; => recovers the signer, compares to :from

(signer/signer priv)                ; => an ISigner for io-filecoin's seam
```

## What differs from Ethereum — only the last step

The curve is the same, the signature is the same 65 bytes. The chains part
company at two places, and both are silent when wrong:

|  | Ethereum | Filecoin `f1` |
|---|---|---|
| address | keccak-256(X‖Y)[12:] | BLAKE2b-160(**`0x04`**‖X‖Y) |
| digest | keccak-256 of the payload | BLAKE2b-256 **of the message CID** |

**The `0x04` matters.** Ethereum hashes the 64-byte key; Filecoin hashes the
65-byte SEC1 uncompressed form, prefix included. Omit it and you get a
perfectly well-formed `f1` address for an account nobody controls — nothing
complains until a transfer disappears into it.

**The digest is hashed twice.** The message CID is already a BLAKE2b-256, and
secp256k1 signs BLAKE2b-256 *of* that. Signing the CID directly gives a
signature of the right length that verifies against nothing.

## What this cannot sign

- ~~**`f3` (BLS12-381).**~~ Implemented — see below. Verification only;
  BLS *signing* is not wired up, since nothing in this family needs to
  produce an `f3` signature.
- **Legacy EIP-155 delegated transactions.** `filecoin.signer.eth` produces
  EIP-1559 (type 2) only. The legacy shape is readable but not writable here:

  ```
  EIP-1559 (type 2)   r ‖ s ‖ v          65 bytes, v ∈ {0,1}
  legacy EIP-155      0x02 ‖ r ‖ s ‖ v   67 bytes on mainnet, since
                                         v = chainId·2 + 35 = 663 takes two
  ```

  Both shapes appear in this repo's mainnet vectors.

## The delegated path — `filecoin.signer.eth`

A message *from* an `f410f` account is not a Filecoin message signed
differently. It **is** an Ethereum transaction, and the Filecoin message is a
re-encoding the node rebuilds and checks byte-for-byte before it looks at the
signature at all.

```clojure
(require '[filecoin.signer.eth :as ethtx])

(ethtx/address-string priv :calibration)   ; => "t410f…"
(ethtx/sign-message priv {:nonce 0 :to contract :input calldata
                          :gas-limit 1000000 :max-fee-per-gas "100000"
                          :max-priority-fee-per-gas "1000"}
                    :calibration)          ; => a type-3 signed message
```

Three things are easy to get backwards, and each produces a well-formed
message that fails somewhere unhelpful:

- **RLP field order is not the message's.** The signed payload is
  `0x02 ‖ RLP[chainId, nonce, maxPriorityFeePerGas, maxFeePerGas, gasLimit,
  to, value, input, []]` — **priority fee before max fee**, where the message
  carries `GasFeeCap` before `GasPremium`.
- **RLP integers are minimal**, so zero is the *empty* byte string, not `0x00`.
- **Empty input means empty params**, not CBOR-empty. `getFilecoinMethodInfo`
  wraps the calldata only `if len(input) > 0`; writing `0x40` breaks the
  round-trip.

There is also a ClojureScript-only trap: `eth-crypto`'s cljs RLP tells a byte
string from a list **by JS type** — a JS array is a byte string, a cljs vector
is a list. Passing a vector of ints encodes each byte as its own nested item.
On the JVM the distinction is free, so this can only fail on one runtime.

## BLS12-381 — `filecoin.signer.bls`

**This implements no cryptography.** Pairing arithmetic is the last thing to
hand-roll, so the primitives come from `@noble/curves` (audited, pure JS).
What is here is the Filecoin-specific part: which DST, which group holds
what, and where a public key comes from.

```
signature   96 bytes, G2      public key  48 bytes, G1
DST         BLS_SIG_BLS12381G2_XMD:SHA-256_SSWU_RO_NUL_
```

The trailing `NUL_` is the **basic** scheme. noble defaults to `POP_`
(proof-of-possession) — a different hash-to-curve domain, so every signature
just fails with nothing to say the tag was why. There is a test that verifies
the *same* aggregate under `POP_` and asserts it does **not** pass.

An `f3` address **is** the public key, carried verbatim rather than hashed.
That is what makes a block's aggregate checkable with no chain state at all:

```clojure
(bls/verify-block-aggregate aggregate messages)   ; => true
```

A header's `BLSAggregate` is one signature over *every* BLS message in the
block. The test verifies a real mainnet block's — which requires the message
CID, the address→key extraction, the DST, the G1/G2 placement and the
aggregate scheme to be right simultaneously — and then checks that dropping a
message, altering one, or using the secp256k1 double-hashed digest each make
it fail.

One distinction worth knowing: a *corrupted* aggregate does not verify to
`false`, it **throws** — flipped bits are not a point on the curve. A caller
treating exceptions as transport errors would mishandle a tampered block.

**ClojureScript only.** There is no pure-Java BLS12-381 here and the JVM
options are JNI bindings to `blst`, which would pin a native library and a
platform. The `:clj` side throws and names the operation it was asked for.
That also matches AGENTS.md's runtime order, where ClojureScript ranks above
the JVM.

## Verification

The vectors are **mainnet's**, and they are checked in the one direction that
cannot be faked: **recovery**. Every signature in them was produced by
somebody else's wallet, over a message the network accepted. Recovering the
signer and getting back `From` exercises CBOR field order, the message CID,
the second BLAKE2b-256, ECDSA recovery, the `0x04` prefix and BLAKE2b-160 in a
single comparison — and nothing this library computes is an input to it.

The delegated vectors are there to assert a **negative**: recovery over the
message digest must *not* return the sender, because a delegated signature
covers something else. That is ADR-2607299300's correction, checked against
the network rather than against a reading of lotus — and the network turned
out to say something stronger than the ADR did, since one of the two shapes is
not 65 bytes at all.

RFC-6979 makes signing deterministic, so the pinned signature bytes are a
**cross-implementation** check: `eth-crypto` implements the nonce separately
on each runtime (BigInteger + javax.crypto; js/BigInt + a hand-written
SHA-256), and both suites assert the same bytes.

**123 assertions on the JVM, 126 under nbb.** They differ on purpose here: the BLS suite is ClojureScript-only, and the JVM runs a refusal test in its place.

```sh
kbb -M:test        # JVM
npm run test:cljs      # nbb
npm run vectors        # re-snapshot mainnet (not run in CI)
```

The test key is the EIP-155 worked example's, which is public by construction
and controls nothing. A generated key would make the pinned signatures
unreproducible, and a real one has no place in a test file.

### Verified against a real node

`io-filecoin-transport`'s `scripts/probe-delegated.cljs` pushes three messages
to calibration from an account that has never existed, and reads which of
lotus's checks caught each:

```
correct               Actor not found                       ← past AuthenticateMessage entirely
corrupted signature   Could not recover public key          ← the signature branch is live
method changed        signature verification failed:
                        failed to reconstruct               ← the round-trip check is live
```

`AuthenticateMessage` rebuilds the transaction, requires the message to
re-encode identically, and only then verifies the signature — all before the
sender's actor is looked up. So the first line means both passed, and the
other two show neither check was skipped. Nothing is spent: the balance is
read first and the push is refused unless it is exactly zero.

## Scope — read this before using it

**Nothing here has been used to send a transaction that landed.** The signatures are
verified by recovering them, which is the same check a node makes, but no
message signed by this code has been submitted to a network. A working client
also needs gas and nonce (`Filecoin.GasEstimateMessageGas`,
`Filecoin.MpoolGetNonce` — `filecoin.rpc` builds those request bodies) and a
transport, which is still nobody's job in this family of repos.
