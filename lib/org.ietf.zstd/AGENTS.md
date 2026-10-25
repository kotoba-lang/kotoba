# AGENTS.md — org-ietf-zstd

Zstandard decoding (RFC 8878) in portable `.cljc`. Zero dependencies: both
entropy coders and XXH64 are implemented here.

## Invariants

- **No host codec.** No `java.util.zip`, no node `zlib.zstd*`, no npm binding.
  The `zstd` binary appears in `test/zstd/oracle_test.cljk` only, as an oracle.
- **Dictionaries are refused, not guessed at.** A frame with a dictionary ID
  raises `:dictionary-required`.
- **Checksums verified by default**, `:verify-checksum false` for salvage.
- **Every failure is an `ex-info` with `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).
- **Read the RFC, do not recall it.** Every table in `zstd.fse` is transcribed
  from RFC 8878 §3.1.1.3.2.2 and §4.2. See the first trap below for what
  happens otherwise.

## Traps (all three cost a debugging cycle here)

1. **The match-length predefined distribution has *seven* low-probability
   entries** (codes 46–52), not five. A wrong split still sums to 64, so the
   table builds without complaint, decodes correctly for most inputs, and
   produces confident nonsense only when a state in the affected range comes
   up. Recalled-from-memory tables are not acceptable in this repo.
2. **Huffman codes are distributed starting from the *lowest* weight**
   (RFC 8878 §4.2.1.3). Filling from the highest weight also produces a valid
   prefix code — just a different one — so the table looks healthy and every
   literal decodes to the wrong byte.
3. **An FSE table description's end offset is absolute.** `zstd.bits/fwd-reader`
   starts at `from * 8`, so `fwd-bit-pos` already includes it; adding `from` back
   double-counts and shifts every subsequent bitstream.

Also worth knowing:

- **Two bit readers, opposite directions.** Table descriptions are read forward,
  LSB-first; all *data* is read backward, MSB-first from the end of its section,
  and the last byte's highest set bit is a padding marker that must be skipped.
- **"Exhausted" and "overflow" are different.** An FSE weight stream ends when
  consumption *exceeds* the available bits (`rev-overflow?`); stopping when the
  bits are exactly consumed drops the final weight. Huffman literal streams, by
  contrast, terminate on a *count*, never on the reader looking empty — the last
  symbol may finish precisely on the final bit.
- **Sequence field order is not the state-update order.** Extra bits are read
  offset → match length → literal length; the states then update literal
  length → match length → offset. The last sequence updates nothing.
- **Repeat offsets are stateful across sequences *and* blocks** within a frame,
  and the literal-length-zero case shifts every offset code by one
  (`apply-offset`).
- **Never `bit-shift-left` past 31 bits.** Offset code 31's baseline is 2^31,
  negative in int32. `zstd.fse` and `zstd.xxhash` use power tables and
  multiplication.
- **XXH64 needs 64-bit wrapping arithmetic**, which ClojureScript does not have:
  `[hi lo]` halves, and the multiply uses `mod`/`quot` because its partial
  products reach ~1.7e10 and a bitwise op would truncate them to int32.

## If you add an encoder

Don't add a naive one. `compress` writing raw blocks is honest and correct; a
greedy zstd encoder would be worse than gzip on every axis that matters. The
order to do it in, if ever: literal Huffman construction → FSE table
construction and normalisation → match finder → block-strategy pricing, with the
oracle asserting `zstd -d` accepts the output at every step.
