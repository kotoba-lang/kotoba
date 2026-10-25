# kotoba-lang/org-7-zip-7z

Portable `.cljc` **.7z reader** (Igor Pavlov's `7zFormat.txt` from the LZMA SDK)
with a Copy-coder writer. Depends on `org-tukaani-xz` for LZMA1/LZMA2 and
`org-ietf-deflate` for CRC-32 and the Deflate coder.

Named `org-7-zip-7z` — 7-zip.org publishes the format description, the same
`org-<vendor>-<spec>` pattern as `org-pkware-zip`. Namespaces are `sevenz.*`,
because a Clojure symbol cannot start with a digit.

## Usage

```clojure
(require '[sevenz.core :as sevenz])

;; read
(def listed (sevenz/entries archive-bytes))     ; metadata only
(sevenz/names listed)
(sevenz/parse archive-bytes)                    ; every member with :bytes
(sevenz/parse archive-bytes {:verify-crc false :max-output (* 64 1024 1024)})

;; write (Copy coder — the container, not compression)
(sevenz/build [{:name "dir" :dir? true}
               {:name "dir/a.txt" :bytes bytes}])
```

Entries carry `:name :size :crc32 :dir? :empty? :folder :substream
:folder-offset :attributes :mtime` (mtime in Unix seconds).

## Why .7z is the awkward one

Two structural facts drive the whole implementation:

1. **The header is usually itself compressed.** A `kEncodedHeader` describes a
   packed stream that, once decoded, *is* the real header — so the codec has to
   run before the reader knows what the archive contains. Both plain and encoded
   headers are handled.
2. **Folders are coder graphs, not files.** Members ("substreams") are cut out of
   a folder's decoded output, and a folder may chain coders through bind pairs (a
   filter feeding a compressor). Solid archives put many members in one folder,
   so reading one member from the middle decodes the whole folder — that is the
   format, not a limitation of this reader. Folders are decoded once and cached
   per `parse` call.

Sizes and CRCs live in three places (pack info, unpack info, substreams info) and
the reader reconciles all three; CRCs are verified by default.

## Coders

| coder | status |
|---|---|
| Copy (`00`) | implemented, and what `build` writes |
| LZMA1 (`030101`) | implemented (via `org-tukaani-xz`) |
| LZMA2 (`21`) | implemented |
| Delta (`03`) | implemented |
| Deflate (`040108`) | implemented (via `org-ietf-deflate`) |
| BZip2 (`040202`) | implemented (via `org-sourceware-bzip2`) |
| PPMd, Deflate64, BCJ, BCJ2, AES-256, ARM64, RISC-V | **refused by name** (`:unsupported-coder` with `:coder`) |

Returning undecoded bytes as a member's content would be silent corruption, so an
unimplemented coder is an error. AES-256 in particular is a refusal, not a
gap-to-be-filled: this library will not decrypt.

Failures are `ex-info` with a `:reason` — `:not-7z`, `:truncated`,
`:checksum-mismatch`, `:bad-header`, `:unsupported-coder`, `:unsupported-header`,
`:too-large`, `:output-limit`.

## What `build` is and is not

`build` writes a **conformant .7z container** whose members are stored with the
Copy coder: `7z t` verifies it, `7z l` lists it and `7z x` extracts it — all
asserted by the suite. It does not compress, and there is deliberately no LZMA
encoder anywhere in this workspace (see `org-tukaani-xz`'s README for why).

One folder per member, rather than 7-Zip's solid default, so members stay
individually addressable — the right trade-off for an archive nothing compressed
anyway. Output is reproducible: no timestamps, no attributes, no clock.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against the 7z CLI
kbb -M:local:test    # …against sibling org-tukaani-xz / org-ietf-deflate checkouts
kbb --backend sci run-tests.cljk       # ClojureScript: build + read, no host codec
kbb -M:lint
```

The JVM suite drives the real `7z` binary in both directions and covers every
layout combination separately, because each is a different path through the
reader: Copy/LZMA1/LZMA2, solid and non-solid, plain and compressed header, plus
directories, empty files, Unicode names, a 1 MB solid archive, BZip2 folders in
all three layouts, and PPMd/BCJ archives to assert the remaining refusals. Then our own archive goes back through
`7z t` / `7z l` / `7z x`.
