# io-filecoin-transport

`filecoin.transport` + `filecoin.client` — **the socket `io-filecoin` refuses
to open**, and the order the calls have to go in.

Everything else in this family builds request maps and hands them back. This
repo sends them, and it is the first one that has ever actually talked to a
node.

## Usage

```clojure
(require '[filecoin.transport :as transport]
         '[filecoin.client :as client])

(def http (transport/http))
(def endpoint "https://api.node.glif.io/rpc/v1")

(client/height http endpoint)                 ; => 6233477
(client/balance http endpoint "f1…")          ; => "27318921114299575156"
(client/read-contract http endpoint msg ["uint256"])

(client/send-message-with-key http endpoint priv message)
;; prepare → sign → push, in that order
```

For a provider's byte endpoint, pass a byte sequence as `:body` with
`:method :put`, or request `:response-type :bytes` on a GET. The result's
`:body` is a JVM byte array or a JS Uint8Array, and `:headers` includes
response headers such as the upload ticket's `Location`. The default remains
UTF-8 text for JSON-RPC. A loopback HTTP test sends and receives bytes
`00 7f 80 ff` on both runtimes. Transferring bytes alone is not a durable
Filecoin deal; the on-chain custody and payment steps are separate.

`npm run probe:provider` now retrieves through `IHttp` and recomputes the
PieceCID. In a 2026-09-26 15:48 UTC mainnet read-only run, 15 providers
reported the chain-derived piece present; 4 returned 204,898 bytes matching
the PieceCID and 11 failed byte verification or retrieval. This proves the
transport can preserve bytes from real providers, not custody of our CARs.

`npm run probe:upload-canary` sends a public 127-byte canary to one selected
provider and verifies its PieceCID after retrieval. To probe a public CAR,
set `FILECOIN_CANARY_FILE`, `FILECOIN_CANARY_SHA256`, and
`FILECOIN_CANARY_PIECE_CID`; the script checks both identities before any
network request and refuses files over 4 MiB. In a 2026-09-26 16:00 UTC run,
the 20,007-byte Yataverse apex CAR with SHA-256
`579bb7a70d702a831fa5d4329043e62f3ef37659497fb714974f5d173b1d67b7`
received HTTP 204 on PUT and was read back with PieceCID
`bafkzcibd3fqqvdbpswakueaauvwwtfsvgbw7wapwap4dpgffmj2evphn2owumfab`.
This is a transfer and retrieval receipt, not a durable Filecoin contract.

## The sequence is the point

A single request is easy. The order is where a client goes wrong, in ways no
one request reveals:

- **Gas is estimated on a message that already has its nonce.** The estimate
  is computed from the serialised message and the nonce is part of it.
  Estimating first gives a limit for a different message.
- **`GasEstimateMessageGas` returns the whole message, not three numbers.**
  Lotus fills the fields in and hands it back. Taking only `GasLimit` and
  keeping your own fee cap is how a message ends up priced below the base fee
  and sits in the pool.
- **The signature is taken over the message *after* gas.** Sign first and the
  CID moves underneath you — there is a test asserting exactly that.

So `prepare` is one function rather than two calls a caller might reorder,
and `send-message` is prepare-then-sign-then-push.

## Reading a contract without spending anything

`StateCall` executes a message against current state and throws the result
away — no signature, no gas, no funds, nothing on chain. That is how an FEVM
contract is read from the Filecoin side: build the `InvokeContract` message
with `filecoin.cloud.evm`, run it, decode `Return`.

`Return` is unwrapped **twice**: base64, then a CBOR byte string. Handing the
CBOR to the ABI decoder leaves two bytes of header on the front and shifts
every word. And a reverting call still returns HTTP 200 with a non-zero
`ExitCode`, so decoding its empty `Return` would hand back `[]` and read as
success.

## Verification

The offline suite uses a transport that answers from a fixture and records
what it was asked, so the assertions are about the **conversation**: which
methods, in which order, with which fields already filled in.

The live suite (`npm run live`) is the other half, and it is not run in CI.
Against Filecoin mainnet, read-only, with no key and no funds:

```
endpoint: https://api.node.glif.io/rpc/v1
  ok   ChainHead height → 6233477
  ok   StateNetworkName → "mainnet"
  ok   MpoolGetNonce → 22067
  ok   WalletBalance (attoFIL) → "27318921114299575156"
  ok   GasEstimateMessageGas → {:gas-limit 926078, :gas-fee-cap "54773194", :gas-premium "101618"}
  ok   PDPVerifier.getChallengeFinality() via StateCall → ["150"]
  ok   PDPVerifier.getNextDataSetId() via StateCall → ["1413"]
  ok   signature accepted by a real node (differential probe)

8 checks, 0 failed
```

The last two are the ones worth having. They run a real call against the
deployed PDPVerifier at its real mainnet address, through the FRC-0042 method
number, the CBOR params wrapper, `f410f` addressing, the function selector and
ABI decoding — five repos at once, and no offline test can show that they are
right *together*.

### Proving the signature without spending anything

The last check settles what was previously only argued for: that a signature
produced by `io-filecoin-signer` is accepted by a real implementation.

lotus validates a pushed message in `MessagePool.Add` as `checkMessage` →
`ValidForBlockInclusion` → **`VerifyMsgSig`**, and only *afterwards* looks the
sender's actor up. So push the same message twice from an empty account —
once signed properly, once with a single bit flipped in the signature — and
the two rejections come from different places:

```
our signature      failed to look up actor state nonce: resolution lookup failed
one bit flipped    signature verification failed: failed to validate signature
```

Two *different* errors is the evidence. The same error twice would mean the
signature was never reached and the run proved nothing, which is why the probe
fails rather than passes in that case.

Nothing is spent and nothing lands: the account's balance is read first and
the push is skipped unless it is exactly zero, so both messages are rejected
by construction. Calibration rather than mainnet, because a probe belongs on a
testnet.

What this establishes is precise: **lotus's `VerifyMsgSig` accepts what this
code signs** — the digest, the 65-byte format, the address derivation and the
CBOR. It says nothing about whether a message would *execute* correctly, or
about the gas and nonce logic on a funded account.

The live suite found a bug on its first run: `filecoin.rpc/message->json`
skipped normalisation when `:to` was present, which is true of exactly the raw
map a caller writes by hand, and handed a string to the address encoder. Lotus
answers that with `unmarshaling params: unknown address protocol`, which reads
as a malformed request rather than an un-normalised one. Fixed in io-filecoin
`244db55`.

**20 assertions offline, green on both runtimes; 8 live checks against
mainnet and calibration.**

```sh
kbb -M:test        # JVM, offline
npm run test:cljs      # nbb, offline
npm run live           # mainnet, read-only
npm run probe:delegated  # calibration, the delegated-path differential
```

### The delegated-path probe

`scripts/probe-delegated.cljk` establishes that lotus accepts a **type-3**
(FEVM) message built by `filecoin.signer.eth`, without spending anything. It
pushes three messages from an account that has never existed and reads which
check caught each:

```
correct               Actor not found                  ← past AuthenticateMessage entirely
corrupted signature   Could not recover public key     ← the signature branch is live
method changed        signature verification failed:
                        failed to reconstruct          ← the round-trip check is live
```

`AuthenticateMessage` rebuilds the Ethereum transaction from the message,
requires the message to re-encode identically, and only then verifies the
signature — all before the sender's actor is looked up. So the first line
means both passed, and the other two show neither check was skipped.

Getting this case right took three attempts, which is the point of writing
the verdict so it *fails* rather than passes when inconclusive: swapping the
gas fields is refused earlier by `ValidForBlockInclusion` (premium > cap), and
bumping the nonce round-trips fine and surfaces at the signature instead.
Only a field that is not part of an Ethereum transaction — the method — is
caught by the round-trip and nothing before it.

### A note on the ClojureScript suite

`IHttp` returns a map on the JVM and a Promise here, so assertions written
inside a `.then` run *after* `run-tests` has reported. Written the obvious
way, this suite was green on both runtimes while the ClojureScript side
asserted 10 where the JVM asserted 19. Every async test now goes through
`clojure.test/async`, and the two counts match.

## What is not here

- **BLS12-381**, so `f3` accounts cannot send. Unchanged across this family.
- **The delegated (FEVM sender) path.** `send-message` signs type 1; a message
  *from* an `f410f` account needs the RLP-encoded Ethereum transaction
  instead. See `filecoin.signature`.
- **Retries, backoff, connection pooling.** One request, one call. A caller
  who needs more can wrap `IHttp` — that is what the protocol is for.
- **Websockets.** Glif offers one; nothing here subscribes.

## Scope

**No message signed by this code has ever landed on a chain.** Two are pushed
by the probe above, both from an empty account and both rejected — that
demonstrates the signature is accepted, not that a send works end to end.
A real send needs a funded account, so the gas and nonce logic on the write
path remains argued for rather than demonstrated.
