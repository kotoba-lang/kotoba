# kotoba-lang/org-sourceware-bzip2

Zero-dependency portable `.cljc` **bzip2**, both directions — decompression and
real compression. Named for bzip2's home at
[sourceware.org/bzip2](https://sourceware.org/bzip2/), the same
`org-<project>-<format>` pattern as `org-tukaani-xz` and `org-7-zip-7z`.

```clojure
(require '[bzip2.core :as bzip2])

(bzip2/compress bytes)             ; => .bz2 stream (level 9)
(bzip2/compress bytes {:level 1})  ; level 1-9 = 100,000-byte blocks x level
(bzip2/decompress bz2-bytes)
(bzip2/bzip2? bytes)               ; signature sniff
```

Bytes in and out are vectors of unsigned 0-255 integers — the convention shared
by every codec repo here, so the same calls work on the JVM and on ClojureScript.

## Why this repo exists

Two shipped repos were refusing bzip2 by name: `org-7-zip-7z` (the BZip2 coder)
and `org-pkware-zip` (method 12). `.tar.bz2` is also still everywhere. And of
the compression formats left unimplemented, bzip2 is the one where **writing is
tractable**: there is no match finder to price. The pipeline is

    RLE1 -> BWT -> MTF -> RLE2 -> multi-table Huffman

and every stage is decided by counting rather than searching. So this is the
second format in the workspace that can actually compress, after DEFLATE.

## Both directions, and how that is checked

- **We read what the reference writes** — every level 1-9 over ten input shapes.
- **The reference reads what we write** — `bunzip2 -c` returns our input, and
  `bunzip2 -t` runs libbzip2's own integrity check over our stream.
- **Ratio is compared, not assumed.** The four-iteration table assignment is
  implemented, so our output is measured against `bzip2 -9` with a 1.1x bound.
  Measured on this machine: 0.96x-1.00x of the reference, i.e. the same size or
  slightly smaller.
- **A real `.tar.bz2`** built from `org-ieee-tar` + this repo is extracted by
  system `tar -xjf` in the suite. bzip2 does not archive and tar does not
  compress; the composition is shown rather than hidden behind an option.

## Traps this format sets

- **Bits are packed most-significant-first** — the opposite of DEFLATE, where
  data elements are LSB-first. One bit order here, and mixing them up produces a
  stream only your own decoder can read.
- **The CRC-32 is not gzip's CRC-32.** Same polynomial, *unreflected*: bits
  enter at the top of the register and nothing is bit-reversed. It lives in its
  own namespace for that reason. Our implementation matches the CRC catalogue's
  published check value for CRC-32/BZIP2 (`0xFC891918` for `123456789`).
- **The stream CRC is a rotate-then-XOR fold**, not a plain XOR, so two blocks
  in a different order do not collide.
- **Block CRCs cover the bytes before RLE1**, not the run-coded form.
- **A run of four equal bytes plus its count byte is indivisible.** Split that
  group across a block boundary and the next block's first byte is read as a
  count — silent corruption rather than an error.
- **Randomised blocks are refused by name.** The feature was deprecated in
  bzip2 0.9.5 and nothing has written one since; decoding it wrong quietly is
  worse than refusing it.

## Performance

`inverse` (the BWT used when reading) is O(n) and fine on real archives.
`forward` sorts rotations by **prefix doubling** — O(n log n) comparisons over
O(log n) rounds — which produces the same permutation as bzip2's tuned
radix/quicksort hybrid but is materially slower: roughly 170 KB in 8 s under nbb,
faster on the JVM. Compressing hundreds of megabytes is not what this is for.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against bzip2/bunzip2
kbb -M:local:test    # ...with sibling checkouts
kbb --backend sci run-tests.cljk       # ClojureScript: the portable suite, recorded fixtures
kbb -M:lint
```

The portable suite carries reference streams recorded from the `bzip2` binary, so
ClojureScript asserts real conformance rather than self-consistency. Regenerate
them with:

```sh
kbb --backend sci tools/record_fixtures.cljk   # verifies each stream through bunzip2 before writing
```

## Not supported

No streaming (whole buffer in, whole buffer out; `:max-output` bounds a hostile
input). No randomised blocks. No `bzip2recover`-style salvage of a damaged
stream. `bzip2` the *file* utility — `.bz2` naming, permissions, stdin/stdout
plumbing — is out of scope; this is the codec.
