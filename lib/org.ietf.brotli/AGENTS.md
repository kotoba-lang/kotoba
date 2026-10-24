# AGENTS.md — org-ietf-brotli

Brotli decoding (RFC 7932) in portable `.cljc`. Zero dependencies in `src/`;
`org-ietf-deflate` appears only in `tools/` (for the CRC-32 that verifies the RFC
transcription).

## Invariants

- **No host codec.** No node `zlib.brotli*`, no npm binding, no JNI. The
  reference `brotli` binary appears in `test/brotli/oracle_test.cljk` only, as an
  oracle.
- **`src/brotli/data.cljk` is generated.** Never hand-edit it. Regenerate with
  `tools/extract_rfc_tables.cljk`, which refuses to write unless all five tables
  match the CRC-32 values the RFC publishes.
- **Decoding only.** Do not add an encoder. Brotli is deliberately
  expensive-to-encode; the compressing path in this workspace is
  `org-ietf-deflate`.
- **Every failure is an `ex-info` with `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`). The
  122,784-byte dictionary is base64 in the source and decoded with
  `java.util.Base64` / `js/atob`; keep both paths working.

## Traps

- **The tables are the risk, not the algorithm.** The bug that took longest here
  was in the *generator*: it emitted the RFC's C string literals verbatim, so
  transform 22's suffix was `\` + `n` rather than a newline. Effect: one extra
  byte per dictionary reference, which only showed up above ~76 KB at high
  qualities, as a `copy runs past the meta-block length` error several commands
  later. If a decode diverges by one byte, suspect the transforms.
- **`zero?` is not a safe loop-binding name.** `(loop [zero? true] … (zero? x))`
  calls a boolean. It cost a debugging cycle in `bits/align!`.
- **A prefix code with one used symbol consumes no bits** (§3.4 NSYM=1, and the
  single-non-zero-length case of §3.5). Treating it as a one-bit code makes every
  stream containing one fail at its first symbol — for instance a literal
  alphabet where every byte is equally likely.
- **Repeat codes 16/17 accumulate.** A second one of the same kind replaces the
  run total (`(count - 2) << extra + read + 3`) and only the *delta* is appended;
  a 16 after a 17 does not continue the run, because what matters is whether the
  repeated *length* is the same.
- **Distances are not just distances.** Sixteen symbols mean "a recent distance,
  ±1..3"; a distance beyond `min(window, bytes-produced)` is a *dictionary*
  reference; and neither a symbol-0 distance nor a dictionary distance is pushed
  into the ring buffer. Getting the pushes wrong diverges thousands of bytes later.
- **A dictionary reference can emit more bytes than the copy length** — the
  transform adds a prefix and suffix — so meta-block length checks must use the
  transformed word's length.
- **Context IDs come from the last two output bytes** regardless of how they were
  produced (literal, copy, dictionary, or a previous meta-block), so `p1`/`p2`
  must be re-read from the output buffer after every command.
- **`lut2` entries span 0..7**, not 0..3: Signed mode packs two of them as
  `(lut2[p1] << 3) | lut2[p2]`.

## Layout

| namespace | role |
|---|---|
| `brotli.core` | stream/meta-block headers, block-switch state, context maps, the command loop, output buffer |
| `brotli.prefix` | simple + complex prefix code descriptions, canonical decode |
| `brotli.dictionary` | dictionary words, the 21 elementary transforms, `word-for-distance` |
| `brotli.data` | **generated**: dictionary (base64), transformations, context LUTs |
| `brotli.bits` | forward LSB-first bit reader |
| `tools/extract_rfc_tables.cljk` | regenerates `brotli.data` from the RFC text, CRC-verified |
