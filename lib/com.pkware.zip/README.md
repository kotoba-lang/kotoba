# kotoba-lang/org-pkware-zip

Zero-dep-beyond-`org-ietf-deflate` portable `.cljc` **ZIP reader and writer**
(PKWARE APPNOTE.TXT). Named `org-pkware-zip` — PKWARE still publishes and
maintains APPNOTE.TXT, the same `org-<vendor>-<spec>` pattern as
`org-adobe-tiff`/`org-compuserve-gif` (a published spec exists even though the
publisher is a vendor rather than a formal standards body).

Extracted from `kotoba-lang/kasane` (kasane.zip, ADR-2606272100) as a decoder.
Sketch (`.sketch`), OOXML (`.docx`/`.xlsx`/`.pptx`), ODF and EPUB are all ZIP
containers — downstream consumers like `org-w3-epub` and `org-oasis-odf` take
this repo's entry table and do their own semantic (JSON/XML) parsing.

Writing, ZIP64, CRC-32 verification, the separated list/extract API and the
strict error paths were added in ADR-2607300400, alongside the compressor in
`org-ietf-deflate` that makes writing possible without a host zlib.

## Usage

```clojure
(require '[zip.core :as zip])

;; read — the central directory only, nothing decompressed
(def listed (zip/entries archive-bytes))
(zip/names listed)                         ; => ["a.txt" "dir/" "dir/b.json"]
(zip/read-entry archive-bytes (zip/entry listed "a.txt"))
;; => {:name "a.txt" :method 8 :size 5 :bytes [...] :crc32 ... :mtime {...} ...}

;; read everything at once (the original eager API)
(zip/parse archive-bytes)                  ; => [{:name :method :size :bytes ...} ...]

;; write
(zip/build [{:name "a.txt" :bytes (b/str->utf8 "hello")}
            {:name "dir/" :bytes []}
            {:name "dir/big.bin" :bytes payload :level 9}
            {:name "raw.bin" :bytes payload :method :stored}]
           {:comment "archive comment"})
;; => vector of unsigned bytes
```

Entries carry `:name :comment :method :method-name :size :compressed-size
:crc32 :flags :encrypted? :dir? :mtime :offset :zip64?`. Options: `:verify-crc`
(default true) and `:max-output` on reads; `:level`, `:method`, `:mtime`,
`:comment`, `:zip64` on writes.

Archives are **reproducible** — timestamps default to the MS-DOS epoch
(1980-01-01) and every other header field is a constant, so the same entries
always produce the same bytes. That is what makes a content-addressed
`.docx`/`.epub` possible.

## Strictness

The previous decoder returned *compressed* bytes as a member's content when it
met a method it did not implement, ignored CRC-32 entirely, and would hand back
ciphertext for an encrypted member. All three are now errors, because each is a
silent-corruption path:

| condition | `:reason` |
|---|---|
| method other than stored/deflate/bzip2 | `:unsupported-method` (with `:method-name`) |
| encrypted member | `:encrypted` |
| CRC-32 or size disagrees with the directory | `:checksum-mismatch` / `:size-mismatch` |
| no end-of-central-directory record | `:not-a-zip` |
| bad local or central signature | `:bad-local-header` / `:bad-central-header` |
| data or directory past the end of the archive | `:truncated` |
| split/multi-disk archive | `:split-archive` |
| 64-bit field beyond 2^53 | `:too-large` |
| `:zip64 false` on an archive that needs it | `:zip64-required` |

Reading is driven by the central directory, never by scanning for local
headers, which is what makes it agree with `unzip` on archives with prepended
data. ZIP64 is supported in both directions: saturated 32-bit fields are widened
from the `0x0001` extra field on read, and the writer emits the ZIP64 record and
locator when a count, size or offset no longer fits (or when `:zip64 true`).

**Method 12 (bzip2) is implemented in both directions**, via
`org-sourceware-bzip2` — pass `:method :bzip2` to `build`. It was refused by name
until that codec existed; the archive format does not care which codec you have,
so the fix was a codec rather than a special case here. python's `zipfile` reads
our bzip2 members and we read its own, which is the oracle for it: Info-ZIP's
`unzip` is frequently built *without* bzip2 (macOS ships it that way) and skips
such members rather than verifying them.

Not implemented: encryption, split archives, and compression methods other than
stored, deflate and bzip2 — LZMA (14), zstd (93), xz (95) and PPMd (98) are named
in errors but not decoded.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against java.util.zip
kbb -M:local:test    # …against a sibling org-ietf-deflate checkout
kbb --backend sci run-tests.cljk       # ClojureScript: build + read an archive, no host codec
kbb -M:lint
```

`java.util.zip` appears only in `test/zip/*_test.clj`, as an oracle in both
directions. `us → reference` is the direction that matters for a writer: a
header field at the wrong offset round-trips perfectly through our own reader and
fails in every other tool, so the suite reads our archives back with both
`ZipFile` (central directory) and `ZipInputStream` (local headers), including a
65600-entry archive that forces ZIP64.
