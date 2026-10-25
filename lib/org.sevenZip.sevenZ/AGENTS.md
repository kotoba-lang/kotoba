# AGENTS.md — org-7-zip-7z

The .7z container in portable `.cljc`. Two dependencies: `org-tukaani-xz`
(LZMA1/LZMA2) and `org-ietf-deflate` (CRC-32, Deflate coder). Namespaces are
`sevenz.*` — a Clojure symbol cannot start with a digit.

## Invariants

- **No host codec, no shell.** The `7z` binary appears in
  `test/sevenz/oracle_test.cljk` only, as an oracle.
- **Never return undecoded bytes as a member's content.** An unimplemented coder
  raises `:unsupported-coder` *with the coder's name*. This is the whole reason
  the coder table lists formats it cannot decode.
- **BZip2 (`040202`) is implemented** via `org-sourceware-bzip2` (2026-07-30); it
  was a refusal only because the codec did not exist in the workspace. When a new
  codec lands, check this table for a refusal it turns into an implementation —
  the archive format does not care which codecs you have.
- **No decryption.** AES-256 archives are refused. Do not add a password option.
- **CRCs are verified by default** (`:verify-crc false` for salvage). 7-Zip
  always records them, so a missing CRC is itself suspicious.
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **The header is usually LZMA-compressed** (`kEncodedHeader`). Reading it means
  running the folder decoder before you know anything about the archive, and its
  CRC must be checked before parsing the result.
- **FILETIME does not fit an exact integer.** 7-Zip always writes mtime as
  100-nanosecond ticks since 1601 (~1.3e17), past 2^53. Refusing it — which the
  strict `rd-u64` used for *structural* fields does — makes every real archive
  unreadable. `rd-filetime` reads it as a double on purpose; a microsecond of
  rounding in a timestamp is not a correctness problem, a wrong offset would be.
  This cost a debugging cycle.
- **Every FilesInfo property carries its size**, and the loop skips to
  `start + size` regardless of how much it read. That is what makes unknown
  properties (kDummy, kStartPos, vendor extensions) harmless — do not "optimise"
  it into sequential reads.
- **Substream sizes omit the last one per folder**: it is the folder's total minus
  the others. Getting this wrong shifts every member after the first.
- **A single-substream folder may carry its CRC in UnPackInfo rather than
  SubStreamsInfo**, so the digest lists are not simply concatenated — see
  `assemble-entries`.
- **`kEmptyStream` marks entries with no data; `kEmptyFile` then distinguishes an
  empty file from a directory** among *those* entries only. Two bit vectors of
  different lengths, indexed differently.
- **Bit vectors are MSB-first** and padded to a byte.
- **The number encoding is not LEB128.** The leading byte's *high* bits count the
  extra little-endian bytes and its low bits are the value's high part. Sizes of
  128, 16384 and 2097152 are the boundaries where an encoder/decoder pair
  disagrees; the portable suite tests either side of each.

## Layout

| namespace | role |
|---|---|
| `sevenz.core` | signature header, (encoded) header parsing, StreamsInfo/FilesInfo, folder coder graph, `entries`/`parse`, Copy-coder `build` |

One namespace on purpose: the header structures are mutually recursive enough
that splitting them would mean either circular requires or a `declare` maze.
