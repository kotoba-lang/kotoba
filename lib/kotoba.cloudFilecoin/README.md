# cloud-filecoin

`filecoin.cloud.*` — a client for **Filecoin Onchain Cloud** (Synapse) as
portable `.cljc`: PieceCID v2, the deployed contracts, and calldata for PDP,
Filecoin Pay and Warm Storage.

Companion to [`io-filecoin`](https://github.com/kotoba-lang/io-filecoin)
(the chain protocol) and
[`io-filecoin-node`](https://github.com/kotoba-lang/io-filecoin-node)
(what a node is). Built on
[`org-ethereum-abi`](https://github.com/kotoba-lang/org-ethereum-abi).

| Namespace | What it owns |
|---|---|
| `filecoin.cloud.piece` | PieceCID v2 — FR32, the truncated Merkle tree, FRC-0069. |
| `filecoin.cloud.chain` | Where the contracts are, and how epochs relate to clocks. |
| `filecoin.cloud.pdp` | PDPVerifier: data sets, pieces, proofs. |
| `filecoin.cloud.pay` | Payment rails, and the operator approval that funds them. |
| `filecoin.cloud.warm` | Warm Storage, and its separate state-view contract. |
| `filecoin.cloud.provider` | The storage provider's PDP HTTP API — the transfer surface. |
| `filecoin.cloud.evm` | Calldata → a Filecoin message. Where the two halves join. |

## What Onchain Cloud is

Filecoin's original storage market is a deal: you hand data to a provider, they
seal it into a sector, and PoRep/PoSt proves the sector exists. Retrieval is
somebody else's problem, and payment is settled up front.

Onchain Cloud is a different arrangement, and the pieces here are its parts:

- **PDP** proves an *unsealed* piece is still held, every proving period, by
  answering a challenge derived from on-chain randomness. That is what makes
  the storage *warm* — provable without unsealing.
- **Filecoin Pay** streams payment along a **rail** at a rate per epoch, so a
  provider is paid for as long as they keep proving, not once in advance.
- **Warm Storage** is the *listener* joining the two: PDPVerifier tells it
  when pieces are added, removed or proven, and it decides what that means for
  the rail.

The consequence worth knowing before writing any of it: proving and paying are
separate contracts. A data set can be proven for a service that has stopped
paying, and a rail can run for a data set that has stopped being proven.

## Calling a contract

An FEVM contract is also an ordinary Filecoin actor with an `f410f…` address,
so calling it is an ordinary Filecoin message — no Ethereum transaction, no
RLP, no keccak:

```clojure
(require '[filecoin.cloud.evm :as evm]
         '[filecoin.cloud.pdp :as pdp])

(evm/call-message :calibration :pdp-verifier
                  (pdp/call :data-set-live ["42"])
                  {:from "t1…" :nonce 7 :gas-limit 20000000
                   :gas-fee-cap "1000" :gas-premium "500"})
;; => a filecoin.message, ready for signing-bytes and MpoolPush
```

```
to      the contract's f410f address     (not its 0x… form)
method  filecoin.method/invoke-contract  (FRC-0042 "InvokeEVM" = 3844450837)
params  the calldata, as a CBOR byte string
```

Three details, each of which produces a well-formed message that does the
wrong thing:

- **`params` is CBOR-wrapped, not raw.** `InvokeContract` takes
  `abi.CborBytes`. Passing the calldata unwrapped gives the actor a parameter
  block it cannot decode, and the message reverts having already paid gas.
- **`to` is the `f410f` form.** `chain/contract` returns `0x…` because that is
  what an explorer and an ABI show; a message field takes address bytes.
- **The sender decides the signature type.** An `f1` sender signs the message
  CID (secp256k1), which `io-filecoin` can produce. An `f410f` sender signs the
  **RLP-encoded Ethereum transaction** (delegated) — a different payload
  entirely, which it deliberately cannot. The native `f1` path is the one that
  works end to end.

## PieceCID v2

```clojure
(require '[filecoin.cloud.piece :as piece])

(piece/calculate my-bytes)
;; => {:cid "bafkzcibcdmbmhxp7o3q5ntjp4triphpezgi4gaonnueaqnvfzmeohbk3atjlcpy"
;;     :root [...] :height 2 :padding 27 :size 100 :padded-size 128}
```

A PieceCID is a CIDv1 with the **raw** codec and the multihash
`fr32-sha2-256-trunc254-padded-binary-tree` (`0x1011`), whose digest is not a
hash but a structure — `[padding][height][root]` — so the CID carries the
piece's exact size. That is what v2 added: the old PieceCID held only the root
and left the size to be carried alongside, and lost.

Three things in the pipeline are load-bearing and easy to skip:

1. The payload is **zero-padded to `127 × 2^n`** source bytes, because a quad
   is 127 bytes and the tree has to be complete.
2. **FR32 expansion** turns every 127 bytes into 128 by inserting two zero
   bits per 254. 254 is how many bits of a BLS12-381 field element can hold
   arbitrary data; the zero bits keep every leaf below the modulus.
3. A Merkle parent is `SHA-256(left ‖ right)` **with the top two bits of the
   last byte cleared**, for the same reason. Plain SHA-256 gives a different
   root about half the time — a piece nobody can prove, from code that looks
   right.

## Selectors

There is no keccak here. The only one in this workspace
(`eth-crypto.core/keccak256`) is JVM-only on purpose, since every JavaScript
bitwise operator truncates to 32 bits, so a selector cannot be computed on
both runtimes. They are constants, each beside the signature it came from —
and **every one is checked against the deployed ABI** in the test.

That check is not ceremony. Four wrong bytes are indistinguishable from four
right ones until a call reverts with no reason string. When these were first
written from the documentation, fifteen of thirty-one were wrong, including
`addPieces`: the plausible `addPieces(uint256,(bytes)[],bytes)` is one
argument short of the real `addPieces(uint256,address,(bytes)[],bytes)`.

## Verification

Three oracles, none of them this library:

- **PieceCIDs** from `@filoz/synapse-core/piece` — the implementation the
  providers and the contracts agree with. Twenty payload sizes, chosen at the
  boundaries where the height steps (127, 254, 508) rather than at round
  numbers.
- **Selectors** from viem's `toFunctionSelector`, applied to the canonical
  signature of every function in every deployed ABI. A signature this library
  claims that is not in that table fails as a missing entry.
- **Addresses** from `@filoz/synapse-core/chains`, as published.

Both runtimes run the whole suite. **537 assertions, green on both.**

```sh
kbb -M:test        # JVM
npm run test:cljs      # nbb
npm install && npm run vectors   # regenerate
```

## The guest layer — the same judgments as `.kotoba`

`guest/` is the **judgment half** of the Synapse flow, written in Kotoba and
compiled to native code through `amu` (`kotoba compile`), executed through
kototama-native. The byte path — FR32 expansion, the SHA-256 Merkle tree,
CBOR, signing, HTTP — stays in `src/` and in the host; the guest owns the
decisions that travel as i64 scalars, which is the boundary the native ABI
and the capability model want anyway.

| Module | Pure | What it decides |
|---|---|---|
| `filecoin.cloud.piece-plan` | PURE | Upload geometry before any byte moves: zero-padded size, height, padding, expanded size, the 65-byte floor, a 4 MiB planning ceiling, `plan-fields` folded into one ABI word (tree size low 24 bits, padding bits 24–45, height from bit 46 — padding crosses 2^16 at ~128 KiB, which broke the first 16/32-bit packing), and `plan-fields-unpacks` (decode round-trip). |
| `filecoin.cloud.clock` | PURE | The two genesis instants are THE content: `epoch->unix` / `unix->epoch` on mainnet and calibration, floor semantics (an epoch is the one that has *started*), `deadline-epoch` chaining. Wrong-genesis arithmetic is out by two years and shows no sign of it. |
| `filecoin.cloud.pay-allowance` | PURE | The funding decision before the calldata: does one month of a rate fit the lockup ceiling (`allowance-fits?`), `rate-for-budget`, `approval-rate`. Whole-balance decimal strings stay in `filecoin.cloud.pay`. |
| `filecoin.cloud.test` | — | 30 assertions, one i64 sum, expectations as literals quoting the SDK vectors and the two genesis constants. |

No capabilities: all four modules are PURE, `effects #{}`, and compile with
an empty policy — deny-by-default costs nothing when the guest carries no
authority.

### Verification (measured 2026-09-04, aarch64)

1. `amu check --jvm-free` per module and on the closed 4-module project
   route: all `{:ok true}`.
2. Golden vectors **30/30** through `kototama.native.executor/execute` —
   closed graph compiled with `kotoba.compiler/compile-project`
   (`:aarch64-kotoba-v1`), signed with a fresh Ed25519 keypair, executed
   against a measured runtime (`amu measure-runtime`,
   `runtime-sha256 1e5182a2…`) pinned in the trust policy. Driver:
   `host/verify.cljk` (the JVM is only the test driver; the guest itself is
   JVM-free).
3. Expectations cross-checked under nbb against `filecoin.cloud.piece` and
   the 20 SDK-generated vectors (`test/filecoin/cloud/vectors.cljk`) before
   the native run. Two literals taught the wrong lesson on the first pass
   and were corrected against the oracle: `zero-padded-size 4096` is 8128
   (127×2⁶ — the padding grid does not stop for round numbers), and
   `epoch->unix-mainnet 1000` is 1598336400.
4. Known runtime ceiling: the supervisor seeds the context with a hardcoded
   512 fuel (`tools/kexe_loader.c`), ignoring the artifact's sealed
   `:fuel-abi :initial` budget — a runner that recomputes the geometry per
   assertion traps `:exit 120`. The runner binds each packed word once
   (`plan-fields-unpacks`) instead. The loader/executor pair reading the
   sealed budget is owner-level work, flagged in ADR-2609500000.

The existing `.cljc` suite is untouched by this layer: 38 tests, 537
assertions, still green.

## The provider transfer surface

Everything else here is on-chain and moves no bytes. `filecoin.cloud.provider`
is the other half — an ordinary HTTP API rooted at a provider's `serviceURL`:

```
GET  pdp/ping                     is it alive
GET  pdp/piece?pieceCid=<cid>     is this piece here   (200 / 202 processing / 404)
POST pdp/piece                    begin an upload      (200 = already has it)
PUT  pdp/piece/upload/<uuid>      send the bytes
GET  piece/<cid>                  retrieve
```

**The upload carries no auth.** Authorisation is the on-chain `addPieces`,
which the client signs — a provider will park bytes for anyone, but only a
signed transaction makes them part of a data set somebody is paid to prove. So
an upload alone stores nothing durably.

**`POST pdp/piece` returning 200 means stop.** The provider already has the
piece; content addressing deduplicated it. Treating 200 as "proceed" re-sends
the whole payload for nothing, and treating a missing `Location` as success
loses the data silently.

### Always verify what a provider serves

`verify-bytes` recomputes the PieceCID from the bytes received. This is not
belt-and-braces. Measured against mainnet on 2026-07-30, for one piece the
PDPVerifier says is live:

| providers reporting `:present` | 13 |
|---|---|
| served a 27-byte nginx placeholder as `application/octet-stream`, status 200 | 1 |
| served an identical **wrong** 81,918 bytes | 10 |
| served the real 204,898 bytes | **2** |

Eleven of thirteen looked like a success at the HTTP layer. Only recomputing
the CID tells them apart.

`scripts/probe-provider.cljs` in `io-filecoin-transport` runs that loop:
chain `getPieceCid` → `ping` → `find` → `GET piece/<cid>` → recompute.

### Binary transfer boundary

`filecoin.protocols/IHttp` now allows byte request bodies and an opt-in
`:response-type :bytes`. `filecoin.transport` sends byte PUTs and returns
unmodified byte GET bodies; `get-piece-request` selects that response type.
The transport's loopback test covers `00 7f 80 ff` on the JVM and under
ClojureScript. A caller must still calculate and check the returned PieceCID.
The existing live probe uses its own `arrayBuffer` path; this transport change
does not establish a provider upload, on-chain `addPieces`, or retrieval of our
own archive.

## What is not here

- **Signing and transport.** No keys, no sockets. These namespaces return
  calldata and messages; signing and sending are yours.
- **Gas and nonce.** `evm/invoke` carries whatever you give it.
  `gas-limit`/`gas-fee-cap`/`gas-premium` come from
  `Filecoin.GasEstimateMessageGas` and `nonce` from `Filecoin.MpoolGetNonce`
  — both are calls, and nothing here makes calls. `filecoin.rpc` builds the
  request bodies.
- **Proof generation.** Answering a PDP challenge means holding the data and
  producing Merkle paths into it. This library computes the commitment, not
  the proofs.
- **Event log decoding.** Indexed topics hash dynamic types instead of storing
  them, and reading a hash as a value is worse than not reading it.
- **End-to-end provider custody.** Request builders exist, but this library
  does not operate a signer, storage contract, or retrieval workflow.
- **Large pieces.** `calculate` is byte arithmetic over Clojure vectors: fine
  for a manifest or a test fixture, not for a 32 GiB sector. The size math
  (`height-for`, `padded-size`) is cheap at any size; only the hashing is not.

## Scope — read this before using it

**No transaction built here has been sent to a network.** The selectors and
addresses are checked against what FilOzone publishes, and the encodings
against viem, but nothing in this repository has called a contract. The
distance between correct calldata and a working client is a signer and a
transport, and neither is here.
