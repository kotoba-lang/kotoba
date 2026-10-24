# kotobase-block-codec

Deterministic compression for the bytes **inside** a kotobase block — above the
CID, below the AEAD.

Design: [ADR-2608060500](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2608060500-kotobase-block-compression-frame.edn).

```clojure
(require '[kotobase.blockcodec.core :as bc])

(bc/frame   payload)   ; bytes -> bytes.  Unary. Total. Pure.
(bc/unframe framed)    ; bytes -> bytes.  The identity on pre-codec data.
```

## Why the seam is exactly here

A kotobase block's CID is the sha2-256 of the bytes handed to the block store,
and `ipld/get-verified-block` rehashes them coming back. That single fact
places this layer:

- **Below the CID is worthless.** The stored bytes are ciphertext —
  `kotobase-peer.core/put-tx-block!` encrypts the whole quad payload,
  `arrangement.core/index-root` encrypts each leaf value. Measured, ciphertext
  deflates to **ratio 1.003**: it *grows*. A provider that compressed its BLOBs
  would burn CPU to store more.
- **Above the CID changes the CID.** Which is the constraint, not a snag: two
  writers that disagree by one byte make two blocks, and dedup and
  `kotobase-engine-prolly`'s "CID-identical to a full rebuild" quietly stop
  holding.

So the frame sits on the plaintext payload, immediately before `encrypt-fn`,
and `frame` takes **no options** — not a level, not a threshold, not an
injected codec. Every knob is a constant of the format, because a knob is a way
for two writers to disagree.

This is deliberately the opposite of the injected-`encrypt-fn` discipline
(ADR-2607051000), and the difference is the CID: that ADR chose a *random*
nonce and said so, because an AEAD's output need not be reproducible. This
codec's output is inside the content address and must be byte-identical on
every runtime, forever.

**Corollary — a host codec may not be substituted as a fast path.** DEFLATE
output is not unique, so `java.util.zip` / node `zlib` / `CompressionStream`
would each yield a valid stream with different bytes, hence a different CID.
`org-ietf-deflate` being portable `.cljc` is what makes one answer possible on
JVM and Worker alike.

## The frame

```
0x01 ++ <RFC 1950 zlib stream>   compressed
0x00 ++ <payload>                identity, escaped
<payload>                        identity, bare
```

Identity is normally written **bare**, so a payload the codec cannot shrink is
byte-identical to what the same writer produced before this library existed:
turning compression on re-addresses only the blocks it actually shrinks, and
existing history keeps its structural sharing. The `0x00` escape covers a
payload that would otherwise begin with a tag byte.

`unframe` therefore reads an untagged payload as legacy data — sound wherever
payloads are DAG-CBOR node bytes, since a node is a map and its first byte is
0xA0–0xBB. `legacy-safe?` is the assertion to run before wiring this into a
seam whose payloads are something else.

Because `unframe` is the identity on legacy data, **the read path can be
deployed before the write path**, which is the correct rollout order.

## What it actually saves

`measure` reports a real sample rather than a constant, for the same reason
`kotobase-storage-kura/effective-multiplier` does — quoting 0.10 to a consumer
whose payloads are ciphertext would be a lie about what they are buying.

| payload | raw | framed | ratio |
|---|---|---|---|
| tx block, 5 quads | 212 B | 78 B | 0.368 |
| tx block, 20 quads | 862 B | 145 B | 0.168 |
| tx block, 60 quads | 2,622 B | 316 B | 0.121 |
| tx block, 200 quads | 8,982 B | 937 B | 0.104 |
| tx block, 800 quads | 36,472 B | 3,810 B | 0.104 |
| AEAD ciphertext, 60 KB | 60,001 B | 60,001 B | **1.000** |
| mixed 20 % quads / 80 % ciphertext | 419,720 B | 258,820 B | 0.617 |

Quad payloads compress ~10x because subject and predicate strings repeat.
Ciphertext does not compress at all, and the never-expand rule means it costs
nothing to try.

CPU is the reason the level is 1 and not 6: on a 61 KB payload, level 6 buys
~13 % more shrink (ratio 0.089 vs 0.101) for ~4x the time (1050 ms vs 268 ms),
and that time is spent on a Cloudflare Worker's write path. Warmed, level 1
runs about 270 KB/s under nbb.

## `kotobase.blockcodec.node` — for blocks that are not encrypted

The frame above rides inside a byte string that was already opaque (the tx
block's ciphertext). Merkle-LSM run blocks have no such string: they are
`ipld/encode`d and stored as-is. Compressing them needs two more things.

**The block must stay valid DAG-CBOR**, because `ipld/cid` is
`cidv1-dag-cbor` and a zlib stream under that CID is a CID lying about its own
codec. So the compressed bytes go inside a node — `{"kbc" 1 "z" <framed>}` —
with a version int and two keys so `decode-node` can tell an envelope from
application data by looking at it.

**Links must stay visible to a walker that does not decompress.**
`ipld/links` is "the one generic walk hydrate loops and GC need", and a link
inside a compressed payload is a child GC is entitled to delete while its
parent still points at it. There is no clever fix, so the rule is a
precondition: **only link-free nodes are ever compressed.** `links-preserved?`
states it as a predicate and the suite asserts it both ways. Merkle-LSM
manifests and range directories are nearly all links and keep their exact
current bytes; run blocks are keys and values and do not.

```clojure
(bcn/encode-node node)   ; -> bytes, compressed iff link-free AND smaller
(bcn/decode-node bytes)  ; -> node, identity on everything written before this
```

Measured on Merkle-LSM run blocks (`merkle-lsm.core/canonical-key` shapes):
**0.080–0.108** with plaintext values, **0.41** even when every value is
ciphertext — the canonical keys are half the block and they compress ~12x.

`decode-node` being the identity on legacy blocks is load-bearing here in a
way it was not for the tx block: the Merkle-LSM producer and its readers are
separate artifacts on separate deploy cycles, so **every reader has to be
deployed before any writer emits an envelope**.

## Tests

```sh
kbb -M:test
kbb -M:lint
npm install   # optional; cljs tests use nbb + classpath git deps (io-ipld via org-nist-sha2)
kbb --backend sci --classpath "src:test:../org-ietf-deflate/src:../io-ipld/src:../io-multiformats/src:../org-ietf-cbor/src" run-tests.cljk
```

## StateSMix / Mamba research adapter

`kotobase.blockcodec.statemix` defines an opt-in JVM host contract for the
upstream StateSMix `SSM6` executable.  Its model identity includes the
Mamba-style SSM dimensions, tokenizer, arithmetic scale, and fixed seed.  The
benchmark function measures `duration_ms`, ratio, and bits/byte, then performs
an independent decode and byte comparison before setting
`:roundtrip-verified? true`.

OpenMP is forcibly fixed to one thread for both processes. StateSMix retrains
while decoding; parallel floating-point reduction order can otherwise make the
reconstructed probability sequence diverge. `benchmark!` first snapshots the
input, writes to a private candidate, runs an independent decoder, compares
every byte, and only then atomically publishes the compressed stream. A failed
decode or mismatch leaves no new output file.

It is deliberately **not** another tag in `core/frame`: upstream requires an
external tokenizer and x86-64 AVX2/FMA/OpenMP, performs floating-point online
training, and is not available in the Worker runtime.  Putting it into the CID
path would violate this repository's cross-runtime deterministic-byte
invariant.  It is a cold-path experiment until a portable format pin, golden
vectors, resource limits, and JVM/Worker parity exist.

`golden_test` pins the literal framed bytes and runs on both runtimes. It is
supposed to be annoying to change: a diff there says every `zlib-1` block from
now on has a different address than one framed before, and the way to say that
is a new tag byte, not an edit.

It has already earned its place twice. It caught a fixture that was silently
zero-filled on ClojureScript — `(map int "did")` is the code points on the JVM
and `[0 0 0]` on ClojureScript — which had made the whole ClojureScript suite
self-consistently test the wrong payload. And it caught a real defect in
`org-ietf-deflate`, whose Huffman construction tie-broke on hash-map iteration
order and so emitted *different, equally valid* streams on the two runtimes
(fixed upstream in `e755803`; that repo now has its own cross-runtime pin).

It has since earned it twice more, both times on the ClojureScript side:
`(count uint8-array)` throws `ICounted` where `(count byte-array)` works, and
`ipld.link/link-cid` read a deftype field directly — which returns nil under
nbb, so no node containing a link could be encoded at all, and two links to
one CID compared unequal while hashing equal (fixed upstream in `5d8de53`).

All four are invisible to a round-trip test on a single runtime, which is the
whole argument for pinning bytes and running both.

## Qualified read-only inflation

`install-inflate!` may install an adapter-provided synchronous RFC 1950 decoder. Installation checks exact decoded bytes across levels and rejects checksum damage and truncation before changing the active provider. Adapters must preserve the 128 MiB output limit. `nil` restores the portable decoder.

This seam is read-only: `frame` always uses the pinned portable encoder and all golden writer bytes remain unchanged. A host compressor must never be installed here or substituted into the writer.
