# io-filecoin-node

`filecoin.node.*` — the **node side** of Filecoin as portable `.cljc`: block
headers, tipsets, message admission, and the base fee. The other end of the
network from [`io-filecoin`](https://github.com/kotoba-lang/io-filecoin),
which is what a *client* says to a node.

Sibling of [`io-storj-node`](https://github.com/kotoba-lang/io-storj-node).
Companion to [`cloud-filecoin`](https://github.com/kotoba-lang/cloud-filecoin)
(Onchain Cloud: PDP, Filecoin Pay, Warm Storage).

| Namespace | What it owns |
|---|---|
| `filecoin.node.block` | The 16-field header, its CID, and **the bytes a miner signs**. |
| `filecoin.node.tipset` | Why an epoch has several blocks, and the order they go in. |
| `filecoin.node.mpool` | Every reason a well-formed message still gets refused. |
| `filecoin.node.basefee` | Both fee mechanisms — utilisation, and the current one. |
| `filecoin.node.actors` | The singletons that exist because the network does. |
| `filecoin.node.rpc` | Chain-facing Lotus methods, and header ⇄ JSON. |
| `filecoin.node.protocols` | The seams: blockstore, verifier, beacon, chain store. |

## Usage

```clojure
(require '[filecoin.node.block :as block]
         '[filecoin.node.tipset :as tipset]
         '[filecoin.node.basefee :as basefee]
         '[filecoin.node.mpool :as mpool]
         '[filecoin.node.rpc :as nrpc])

(def h (nrpc/json->block-header lotus-json))

(block/cid h)                ; => "bafy2bzace…" — what peers call this block
(block/signing-bytes h)      ; the header with BlockSig null, as CBOR

(def ts (tipset/tipset headers))
(tipset/key-of ts)           ; block CIDs in ticket order — the TipSetKey

(basefee/next-base-fee-from-premium "3588272" premium-at-80th-percentile)

(mpool/check-valid-for-block-inclusion! msg min-gas network-version)
;; throws with the reason, or returns the message
```

## Design

**Three signing rules, and only one of them is the obvious one.** A secp256k1
message signature covers BLAKE2b-256 of the message's CID; a BLS message
signature covers that CID directly; a **block** signature covers the header's
own CBOR, with `BlockSig` set to null. So `filecoin.node.block/signing-bytes`
returns several hundred bytes where `filecoin.message/signing-bytes` returns
38. Carrying the message habit over produces a signature over the wrong
preimage, and the failure looks like a bad key.

**A link is not a byte string.** A CID inside CBOR is tag 42 over a byte
string that begins with a `0x00` identity-multibase prefix. Dropping the
`0x00` shortens every link by one byte and changes the header's CID, so the
block ends up addressed by a name no peer has. `unlink` refuses both a bare
byte string and a tagged one missing the prefix, rather than reading past it.

**Ordering is identity.** A tipset key is its blocks' CIDs *in ticket order*,
so a tipset assembled in the wrong order names nothing. The comparison is
BLAKE2b-256 of the ticket's VRF proof, bytewise, tie-broken on the **binary**
CIDs — comparing the base32 strings is a different order, because base32 does
not preserve the ordering of what it encodes.

**Nullable is a slot, not an absence.** Four of the sixteen fields become
CBOR null when empty. The array is sixteen long either way; omitting one
shifts everything after it, and the result decodes as a different header
rather than failing.

## What is not here

This is a protocol core, not a node. Nothing here has ever spoken to a peer.

- **Proofs.** No PoRep, no WindowPoSt, no proof verification of any kind. The
  header's `win-post-proof` is carried as opaque bytes because that is all
  this library can honestly do with it.
- **BLS12-381.** Which means block signatures cannot be verified here, and
  `bls-aggregate` is bytes. `IVerifier` is the seam; there is no
  pairing-friendly curve anywhere in this workspace to put behind it.
- **The FVM.** No execution, no gas metering, no receipts. `min-gas` is a
  parameter to `check-valid-for-block-inclusion!` rather than something this
  library computes, because computing it means pricing the message.
- **State.** No HAMT, no AMT, no actor state. `parent-state-root` is a CID
  this library can put in a header and read back out, and nothing more.
- **libp2p, Graphsync, drand.** Networking, block sync and randomness are all
  seams (`IBlockstore`, `IChainStore`, `IBeacon`).
- **Consensus.** No leader election, no chain weight, no fork choice. Weight
  needs the power table, which is state.

The base fee is the sharpest edge of this: both formulas are here and both
are checked against lotus's own tables, but **gathering their inputs is not**.
The utilisation form needs every message in the tipset deduplicated by CID
and the premium form by (sender, nonce), and that is a blockstore walk.

## Verification

The header vectors are **mainnet's**. `testdata/gen_block_vectors.cljk`
snapshots a whole tipset — nine blocks from nine miners — with the CID the
chain gave each header and the tipset key in the order the chain returned it.
The suite recomputes both from the JSON alone.

That is two independent things proved at once. Re-deriving each CID exercises
the entire header codec: the nullable slots, the tagged links with their
prefix, sign-magnitude `ParentWeight` and `ParentBaseFee`, signature byte
strings, the beacon and PoSt sub-arrays, and all sixteen fields in order.
Re-deriving the key proves the *ordering* — that the comparison is over
BLAKE2b-256 of the VRF proof and over binary CIDs — which no single header
could show.

The base fee tables are **lotus's own**, transcribed from
`chain/store/basefee_test.go`: `TestBaseFee`, `TestNextBaseFeeFromPremium` and
`TestWeightedQuickSelect`. A fee formula that agrees only with itself is worth
nothing.

The admission rules are transcribed from `chain/types/message.go` rather than
inferred, and the tests name the version boundaries — the zero address from
nv7, `f4` from nv18 — on both sides.

Both runtimes run the whole suite. **163 assertions, green on both.**

```sh
kbb -M:test                 # JVM
npm run test:cljs               # nbb
npm run vectors                 # re-snapshot a tipset (not run in CI)
```

The header vectors are deliberately **not** regenerated in CI: the chain
moves, so a diff would always fail. They are a permanent snapshot — mainnet
history does not change.

## Scope — read this before using it

**Nothing in `src/` has opened a socket**, because nothing in `src/` can. The
mainnet tipset was fetched by a generator script. `filecoin.node.rpc` builds
request bodies for a transport you supply, and whether that transport reaches
a node is not something this suite knows.
