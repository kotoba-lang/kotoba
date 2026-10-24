# io-ipld-car

**CARv1 and CARv2 — where a block *is*, in portable `.cljc`.**

[`kotoba-lang/io-ipld`](https://github.com/kotoba-lang/io-ipld) answers what a
CID names. This repository answers the other half of a read: **at which byte
range of which object those bytes live**. That is the only question a range
request can act on, and until now nothing in this stack could answer it — the
block plane was one object per CID, so the answer was always "its own object,
one round trip away".

```clojure
(require '[ipld.car.v2 :as v2]
         '[ipld.core :as ipld])

(def blocks [(ipld/node->block {"kind" "leaf" "v" 1})
             (ipld/node->block {"kind" "leaf" "v" 2})])

(def packed (v2/pack {:roots [] :blocks blocks}))
;; => {:bytes <archive> :data-offset 51 :data-size n :index-offset n
;;     :entries [{:cid "bafy…" :file-offset 110 :frame-length 141
;;                :block-offset 147 :block-length 104} …]}

;; A client that holds only the index and one CID:
(def hdr  (v2/parse-header (:bytes packed)))
(def recs (v2/read-index    (:bytes packed)))
(v2/locate hdr recs (:cid (first blocks)))    ;=> {:file-offset 110}
(v2/range-header (first (:entries packed)))   ;=> "bytes=110-250"

;; …fetches that range, and proves it:
(v2/read-frame range-response-body 0)         ;=> {:cid "bafy…" :bytes …}
                                              ;   throws on a CID mismatch
```

## What the layer is for

`kotobase`'s canonical route is a signed immutable CID commit DAG over
untrusted transports, and its cost is **round trips, not bytes**. Production
`kotobase.net` answers a query in ~2.5 s of which 92 % is hydration
(root ADR-2607310900 訂正3), and 97 % of hydration's *sequential* term is the
novelty cons-chain — a width-1 pointer chase whose next CID does not exist
until the previous block is decoded (root ADR-2608021000). No amount of
parallelism touches that shape while each block is its own object.

Packing changes the shape rather than the constant. Blocks that are written
together — a commit's transaction blocks, a prolly-tree page and its children,
a whole unfolded novelty chain — land in **one** archive, so a client fetches
one range and walks the chain locally. The chain stays sequential; the
*network* stops being.

This library does not decide what to pack together. That is a database
question, and it belongs to `kotobase`, not to a spec mirror.

## Three namespaces

| ns | owns |
|---|---|
| `ipld.car` | CARv1 — header, frames, offsets, verified `stream-encode!` |
| `ipld.car.v2` | the pragma + 40-byte header, `pack`, `locate`, `range-header`, `read-frame` |
| `ipld.car.index` | `MultihashIndexSorted` (multicodec `0x0401`) |
| `ipld.car.trustless` | bounded IPLD selector/path execution → root-first CARv1 proof payload |

Two offset vocabularies exist and are deliberately never merged: the CARv2
index stores a **payload offset** (relative to the CARv1 payload, pointing at
the frame's length varint), while a range request needs a **file offset**.
Conflating them is the bug this format reliably produces, so `pack` returns
both under different names and `locate` only ever returns the file offset.

Nothing here fetches. The byte source is the caller's — the same code runs in
a Cloudflare Worker, a browser and a JVM test.

For a large block set, `ipld.car/stream-encode!` takes an ordered, reducible
block source and writes one verified CARv1 frame at a time. Its `write!` sink
must synchronously consume each byte container and return the exact byte count.
Supply a positive `max-bytes` ceiling for the whole archive. The result gives
the total byte count and block count; `on-entry!` can record offsets separately
without retaining the archive or its index in memory. Write to a temporary
target and discard it if any call fails, since a failed write can leave a
partial CAR. Every declared root must be among the written blocks.

For CIDv0 sources, convert each CID to its equivalent CIDv1 dag-pb identity
before calling this writer. It accepts CIDv1 blocks with sha2-256 multihashes,
checks their digests against the original bytes, and rejects other hashes. A
CAR file alone does not establish Filecoin custody or retrieval: the caller
still needs an external archive digest, provider handoff, and retrieval proof.

## Trustless selection and pathing

`ipld.car.trustless/path-car` connects the selector engine in `io-ipld` to the
CAR writer. Every fetched block is CID-verified, traversal requires explicit
block/byte/depth/match limits, and the response contains exactly the unique
root-first blocks touched while resolving the logical Data Model path. A Null
value remains distinguishable from a missing path.

This is the verifiable payload core, not the entire IPFS HTTP Gateway spec.
The edge adapter still owns URL/path escaping, query parameters, redirects,
status codes, caching, Range handling, and content negotiation. Likewise,
GraphSync framing can consume the same ordered block selection without making
CAR the GraphSync wire protocol.

## What is verified, and by whom

Everything in `test/ipld/car_test.cljk` is this library agreeing with itself,
which a writer and a reader built from the same misreading would also do.
`test/interop/reference_car.cljk` is therefore the suite that counts: it hands
the bytes to implementations that never read this source.

| check | judged by |
|---|---|
| we parse their roots, order and block bytes | `@ipld/car` (JS reference) writes, we read |
| **our buffered and streamed CARv1 are byte-identical to theirs** | same fixture, all three writers |
| a CARv2 we packed reads back block-for-block | `@ipld/car` reads |
| `car inspect --full` accepts the archive and names `car-multihash-index-sorted` | `go-car` |
| `car get-block` returns that block's exact bytes | `go-car`, via our index |
| **a one-byte shift in every index offset is rejected** | `go-car` — the negative control |

That last row is the one that makes the row above it mean anything. Without
it, `get-block` succeeding proves only that go-car can scan an archive, which
every CAR reader can do. Shifting the offsets makes the index the only thing
that changed, so a reader that still answered correctly would be a reader that
never consulted it. It fails, with `invalid cid: expected 1 as the cid version
number, got: 113`.

When the go-car CLI is not on `PATH`, that section prints `SKIP` and the
summary ends `1 SKIPPED — not verified: …`. A skipped check never reads as a
passed one.

```bash
kbb --backend sci --classpath "$(kbb -Spath)" run-tests.cljk
go install github.com/ipld/go-car/cmd/car@latest
kbb --backend sci --classpath "$(kbb -Spath)" test/interop/reference_car.cljk
```

The suite prints the current test and assertion counts. The optional go-car
checks report SKIP when the CLI is unavailable.

## What packing is worth, counted (2026-08-19)

`script/round_trips.cljk` answers the homework in superproject ADR-2608198000
and cloud-itonami-app ADR-0057: a block-per-object store issues **one request
per block**, and what that costs was written down for one large file and never
for the shape an agent actually writes — a tree of many small ones.

```bash
npm install
kbb --backend sci --classpath "src:<unixfs>/src:<io-ipld>/src:<io-multiformats>/src:<dev-protobuf>/src:<org-ietf-cbor>/src" \
  script/round_trips.cljk <dir> [--cap=<bytes>]
```

Nothing talks to a network: the request count of a block-per-object store is a
function of the block set, so counting blocks is exact rather than estimated.
It is **not** a latency measurement; ADR-2608198000 says the indicator is the
number of round trips and this reports that and nothing else.

Measured on two real work trees:

| tree | files | bytes | blocks | block-per-object | packed |
|---|---:|---:|---:|---:|---:|
| `cloud-itonami/cloud-itonami-app` | 497 | 7.6 MiB | 510 | **510 PUTs** | **2 PUTs** |
| `kotoba-lang/kekkai-node` | 75 | 353 KiB | 75 | **75 PUTs** | **1 PUT** |

Two, not one, for the larger tree: a pack is an object like any other and
`kotobase.archive-put/max-object-bytes` is 4 MiB. The first version of this
script reported `1 request` for a 7.7 MiB pack — a number the archive would
have refused. `--cap=` is the ceiling and it is applied, not assumed.

Index cost lands where `io-ipld-car` already claims: 20.0 KiB across 510
blocks, 3.0 KiB across 75 — about 40 bytes an entry.

Two results worth not over-reading:

- **Dedup within one tree is zero.** 510 blocks, 510 distinct CIDs. Content
  addressing pays across commits and across agents holding the same base, not
  inside a single snapshot, and a measurement of one tree cannot see that.
- **Almost every file is one block.** 492 of 497 are under the 256 KiB chunk
  size, so per-file reads are one GET either way; what packing buys on the read
  side is the *whole-tree* fetch, which is the operation an agent materialising
  a base actually performs.

Three exit codes, because "measured" and "could not measure" must not look
alike: `0` answered, `2` nothing to measure (empty tree), `3` refused — the
grouping estimate produced a pack over the ceiling, so the request count would
be one the object plane never agreed to. Unreadable files are counted and
printed rather than skipped; a tracked tree with 231 of them (`inga`, whose
`node_modules` is committed but absent locally) reports that instead of
quietly measuring a third of itself.

## Deliberate limits

- **CIDv1 only.** A CIDv0 block is recognised so it can be rejected by name;
  read as v1 it would misparse every following frame instead of failing.
- **Offsets are bounded at 2^53-1.** The format permits a full uint64 and a
  JavaScript host cannot hold one exactly, so encoding one here would produce
  a file whose offsets differ by runtime. `u64-le` refuses rather than round.
- **Streaming write, buffered decode.** `stream-encode!` writes a CARv1 frame
  at a time; `decode` still takes the whole archive. A caller that holds only
  a range uses `v2/read-frame`, which never assumes it has the rest. CARv2
  `pack` still buffers its payload and index.
- **The "fully indexed" characteristic bit is left clear.** This library does
  not promise that property, so it does not assert it.
- Only `MultihashIndexSorted` (`0x0401`) is written or read. `IndexSorted`
  (`0x0400`) is refused by codec rather than guessed at.

## The representation seam

`multiformats.base32/decode` returns a `byte[]` on the JVM and a Clojure
vector on ClojureScript. Both are right for their callers; a byte format
cannot be written against two shapes, and `.length` on a vector is `undefined`
— which silently allocates a zero-length buffer instead of failing. Every
foreign value entering `ipld.car.bytes` is normalised once, at
`as-bytes`, rather than by a convention each call site is expected to
remember. The nbb suite failed exactly this way before that existed.

Design: root `90-docs/adr/2608160100-kotobase-physical-plane-ipld-carv2-pack.edn`.
