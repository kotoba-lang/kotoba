# tech-ipfs-specs-unixfs

**UnixFS files — the balanced DAG `ipfs add` builds, in portable `.cljc`.
Byte-identical CIDs at any size, checked against kubo 0.41.**

`kotoba-lang/io-multiformats` has always addressed a single block correctly
and said where it stopped: *byte-identical to `ipfs add --cid-version=1
--raw-leaves` for single-block (≤256 KiB) inputs*, and `cid-of-file` threw
above that with `a multi-block dag-pb CID is out of scope`. This repository
is that scope — the chunker, the tree, and the UnixFS file header that turn
a 256 KiB ceiling into no ceiling.

```clojure
(require '[unixfs.file :as unixfs])

(unixfs/cid bytes)
;; => "bafkrei…" below 256 KiB, "bafybei…" above — the same string
;;    `ipfs add -Q --cid-version=1 --raw-leaves` prints

(unixfs/build bytes)
;; => {:cid "bafybei…"
;;     :blocks [{:cid … :bytes …} …]   ; leaves first, root last
;;     :size 179300}

(unixfs/read-file get-block root-cid)  ; get-block: cid -> bytes | nil
```

## The shape, which is not the obvious one

- **A file of one chunk is a bare raw block.** No dag-pb wrapper, no UnixFS
  header; the CID starts `bafkrei…`. Only from the second chunk does a root
  appear. The reference implementation special-cases this, so an encoder
  that wraps uniformly produces a valid-looking DAG that no `ipfs get` will
  ever agree with.
- **174 links per node.** `DefaultLinksPerBlock` — an 8 KiB target block
  over a ~47-byte link. It is a constant of the format, not a tuning knob:
  a file built with a different value has a different CID.
- **Levels fill left to right, and a lone remainder is still wrapped.** 175
  chunks is a root of two children — one covering a full 174, one covering
  the single leftover. Linking that leftover leaf directly would be a
  smaller, reasonable, different DAG.
- **`Tsize` and `blocksizes` are different measures** and both are in every
  node: `Tsize` is the total *encoded* size of a subtree, `blocksizes` the
  *logical* bytes each child contributes to the file.

## What it is checked against

Real CIDs from kubo 0.41 over an xorshift32 byte stream — no two chunks
alike, so links emitted in the wrong order cannot pass. The vectors cross
every boundary the format has: empty, one byte, exactly one chunk, one
chunk plus one byte, a full 174-link node, 175, 175 plus a remainder, and
30,277 chunks (three levels above the leaves).

The `--chunker=size-1024` vectors are not a separate feature. Tree shape
depends on the link ceiling and not on chunk size, so a smaller chunk
reaches the same boundaries in kilobytes instead of tens of megabytes.

Both halves of the suite were verified to discriminate: 173 links instead
of 174, and passing a lone remainder through unwrapped, each fail it.

## What is not here

Directories, HAMT shards, and `Data` inlined into a file node. Callers that
already own a tree — an application with its own folders, ACLs and versions
— want files addressed by content and nothing else; a UnixFS directory
beside that tree would be a second, competing answer to where a file lives.
The reader accepts inline `Data` when it meets it, because other
implementations write it.

## Layering

```
unixfs.file        chunker, balanced tree, UnixFS Data header
  ipld.dag-pb      the node codec (Links before Data; empty Name written)
  protobuf.wire    the Data message — ordinary, deterministic protobuf
  multiformats     raw CIDv1, sha2-256
```

## Test

```bash
kbb -M:test
```

## License

Apache-2.0.
