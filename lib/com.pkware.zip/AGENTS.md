# AGENTS.md — org-pkware-zip

ZIP container read + write (PKWARE APPNOTE.TXT) in portable `.cljc`. One
dependency, `org-ietf-deflate`, and nothing else — ever.

## Invariants

- **No host codec.** `java.util.zip` is forbidden in `src/`; it appears in
  `test/zip/*_test.clj` only, as a conformance oracle. Compression comes from
  `org-ietf-deflate`, which is itself host-free.
- **Read from the central directory, not by scanning for local headers.** A ZIP
  with prepended data (a self-extracting stub, a concatenated payload) is valid
  and common; local-header scanning finds members the directory does not list.
  Local headers are only consulted for the `name+extra` length that locates a
  member's data.
- **Never return undecoded bytes as content.** If the method is not 0, 8 or 12,
  raise `:unsupported-method`. The original decoder passed the compressed bytes
  through, which silently corrupted anything reading a bzip2 or LZMA member.
- **Method 12 (bzip2) is implemented in both directions** via
  `org-sourceware-bzip2` (added 2026-07-30). `java.util.zip` cannot be its oracle
  and neither can macOS `unzip`, which is built without bzip2 and *skips* such
  members; python's `zipfile` is, and `test/zip/bzip2_interop_test.cljk` adapts to
  an unzip that lacks the method instead of asserting something it cannot check.
- **Verify CRC-32 and size on read**, with `:verify-crc false` as the explicit
  recovery opt-out. Do not weaken the default.
- **Writes are reproducible.** MS-DOS epoch timestamps, constant
  version-made-by / external attributes, no host state. If you add a field, it
  must be a pure function of the entry data — a content-addressed `.epub`
  depends on it.
- **Sizes and CRCs are known before the local header is written**, so no data
  descriptors are emitted. Keep it that way: descriptors are the part of the
  format oldest readers get wrong.
- **The portable suite must pass under both runtimes** (`kbb -M:test` and
  `kbb --backend sci run-tests.cljk`). nbb has no dependency resolver, so `nbb.edn` points at
  the siblings `../org-ietf-deflate/src` and `../org-sourceware-bzip2/src` — the
  layout west already produces.

## Layout

| namespace | role |
|---|---|
| `zip.core` | public surface: `entries`, `read-entry`, `parse`, `names`, `entry`, `build` |
| `zip.write` | local headers, central directory, EOCD, ZIP64 record + locator |
| `zip.bytes` | little-endian ints, UTF-8 ⇄ string, MS-DOS date/time |

## Traps

- **Two copies of every size/CRC.** The local header and the central directory
  each carry them, and they may legally disagree in the data-descriptor case.
  The directory is authoritative for reading; the writer writes both from the
  same computed values, and `ZipInputStream` in the test suite is what catches a
  drift between them.
- **ZIP64 fields are positional but conditional.** The `0x0001` extra field
  contains only the values whose 32-bit slot is saturated, in a fixed order —
  so parsing must be driven by which slots read `0xFFFFFFFF`, not by the field's
  length. (`zip.core/apply-zip64-extra`; Python's `zipfile` does the same.)
- **Names are UTF-8 only when general-purpose flag bit 11 says so**, otherwise
  CP437/Latin-1. The writer sets bit 11 whenever a name has a byte above 0x7F.
- **`u64` refuses values past 2^53** rather than rounding them on a JavaScript
  runtime. An in-memory reader cannot hold such an archive anyway; do not
  "fix" this by dropping the check.
- **A directory entry is a member whose name ends in `/`** with no data. Do not
  try to decompress one, and keep it in the entry list — consumers use it.

## Changing pins

`deps.edn` pins `org-ietf-deflate` by sha and `:local` overrides it with the
sibling checkout. After changing the deflate side, run `-M:local:test` here
before advancing either pin, then advance `manifest/west.yml` in the superproject
with a single-entry commit. `kasane` consumes this repo, so run its suite too.
