# AGENTS.md — org-ieee-tar

tar (POSIX.1 ustar + PAX + GNU extensions) in portable `.cljc`. Zero
dependencies in `src/`, and it stays that way: tar does not compress, so nothing
here needs a codec.

## Invariants

- **No compression, ever.** `.tar.gz` / `.tar.xz` are compositions the *caller*
  makes with `org-ietf-deflate` / `org-tukaani-xz`. Do not add a `:gzip?` option
  — that would drag a dependency into an archiver and hide which layer failed.
- **No filesystem.** This library maps bytes ⇄ entry maps. Extraction is a
  policy decision (path traversal, symlink targets, permissions, ownership) that
  belongs to the caller, and a library that quietly writes files is a library
  that quietly writes `../../etc/passwd`.
- **Unsigned bytes in, vectors of unsigned bytes out.**
- **Every failure is an `ex-info` with `:reason`.**
- **Writes are reproducible**: mtime/uid/gid default to 0, uname/gname empty,
  and no clock or environment is read.
- **Both runtimes are gated**: `kbb -M:test` and `kbb --backend sci run-tests.cljk`.

## Traps

- **`()` and quoted lists do not behave under SCI (nbb).** `(or (seq out) '(48))`
  worked on the JVM and threw `ja.call is not a function` on every
  ClojureScript call. Use vectors in `.cljc` that must run on nbb — this cost a
  debugging cycle in `tar.bytes/octal-field`.
- **Header fields are bytes, not ASCII.** Decoding a name as Latin-1 turns a
  Japanese filename into mojibake while the *contents* round-trip perfectly —
  the failure looks like a rendering problem, not a bug. `tar.bytes/read-str`
  decodes UTF-8.
- **Numeric fields have two encodings.** Octal ASCII normally; GNU base-256 when
  the high bit of the first byte is set, in which case the value is a big-endian
  two's-complement integer whose *sign* is bit 0x40 (0x80 is only the escape
  marker) — and it must be accumulated with multiplication, not shifts, to stay
  exact past 32 bits on a JavaScript runtime.
- **The checksum field is read as spaces while checksumming**, and historic tars
  disagreed on whether the bytes are signed. Accept either sum.
- **A PAX/GNU extension entry is not an entry.** `x`, `g`, `L`, `K` modify the
  *next* header; `entries` consumes them and surfaces what they carried on the
  real entry's `:pax`. Never report them as members.
- **ustar cannot express every name.** A single 150-byte path component has no
  split point — python's `tarfile` raises rather than write it. That is why the
  writer escalates to PAX, and why the oracle test only feeds that case to the
  GNU and PAX fixtures.
- **Two zero blocks end the archive**, but one at EOF is common enough that the
  reader accepts it; anything after the terminator is ignored.

## Layout

| namespace | role |
|---|---|
| `tar.core` | headers, PAX records, `entries`/`read-entry`/`parse`, `build` |
| `tar.bytes` | octal + base-256 numerics, NUL-terminated UTF-8 fields, UTF-8 ⇄ string |

`tar.bytes` duplicates the UTF-8 helpers that `zip.bytes` also carries. That is
deliberate (ADR-2607082500's layering principle): a two-function copy is cheaper
than a dependency between two leaf spec repos.

## Test oracle

`test/tar/oracle_test.cljk` shells out to python3 (`tarfile` writes GNU, ustar and
PAX on demand) and to the system `tar`. It **skips loudly** when python3 is
missing rather than passing silently. Keep it that way: a conformance suite that
quietly does nothing is worse than no suite.
