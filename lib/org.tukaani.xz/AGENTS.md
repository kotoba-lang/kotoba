# AGENTS.md — org-tukaani-xz

LZMA/LZMA2 decompression + the .xz and .lzma containers, portable `.cljc`. One
dependency (`org-ietf-deflate`, for CRC-32).

## Invariants

- **No host codec.** No `java.util.zip`, no `XZInputStream`, no npm `lzma`. The
  JVM suite shells out to python3/`xz` **as an oracle only**.
- **`xz.lzma` mirrors `LzmaSpec.cpp`.** State transitions, distance slots, the
  literal matched-byte loop and the length coder are deliberately structured like
  the reference so the two can be diffed by eye. If you refactor for elegance and
  the oracle tests still pass, you have probably still made the next bug harder
  to find.
- **Checks are verified by default**, SHA-256 included (`org-nist-sha2`).
  `:verify-check false` exists for salvage, and `:sha256` overrides the bundled
  hash for a caller with its own. **No hash is implemented in this repo** — that
  is a dependency, not a refusal, since 2026-07-30.
- **Every failure is an `ex-info` with `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **Never `bit-shift-left` a value that can reach 32 bits.** Distance slot 63
  computes `3 << 30`, which is *negative* in int32 and silently corrupts every
  long distance on ClojureScript. The range coder's `range`/`code` have the same
  problem. Use `*` and `mod 4294967296`.
- **Rotate the four recent distances by *which slot* was selected, never by
  comparing values.** All four start at 0, so value-matching rotates the wrong
  one and the stream diverges much later, on some inputs only. This was a real
  bug caught before landing.
- **`.xz` block flags: bits 0-1 hold (filter count − 1).** Writing `0x02` for one
  filter makes every reader see three filters and walk off the header — the first
  bug this repo had.
- **The literal coder after a match is context-dependent**: for `state >= 7` the
  bits are coded against the byte at the last distance, and once a coded bit
  disagrees with the match byte the remaining bits switch to the plain tree. Get
  this wrong and short files still decode.
- **LZMA2 resets are cumulative and directional**: control bits say reset
  state / new properties / reset dictionary, and an uncompressed chunk always
  invalidates the probability model. `dict-start` (not 0) is what bounds legal
  distances and drives the `pb`/`lp` position contexts.
- **The .xz index is not decoration.** It repeats every block's unpadded and
  uncompressed size; disagreement means corruption, so the reader checks it.
- **python3's `lzma` module is liblzma.** It is the only oracle that can produce
  arbitrary presets, dictionary sizes, `lc`/`lp`/`pb`, filter chains and both
  container formats on demand. Keep the fixtures generated, never checked in.

## Layout

| namespace | role |
|---|---|
| `xz.core` | .xz container (header/blocks/index/footer), .lzma alone, Delta filter, the uncompressed-chunk writer |
| `xz.lzma` | range decoder, probability model, LZMA1 symbol loop, LZMA2 chunk framing |
| `xz.buffer` | growable byte buffer that doubles as the dictionary window |
| `xz.crc64` | CRC-64/XZ as 32-bit halves |

## If you add an encoder

Do not add a naive one. A greedy LZMA encoder is *worse* than the current
uncompressed-chunk writer in every respect that matters (it is slower, the output
is barely smaller, and it introduces a whole class of "only our decoder reads it"
bugs). The order to do it in: range encoder → price model → optimal parse, with
the oracle asserting `xz -d` accepts every level at every step.
