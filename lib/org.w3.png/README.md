# kotoba-lang/org-w3-png

Zero-dep-beyond-`org-ietf-deflate` portable `.cljc` PNG decoder **and encoder** (W3C
Recommendation, also ISO/IEC 15948). Named `org-w3-png` — same
`org-w3-<spec>` pattern as `org-w3-svg`/`org-w3-woff` (PNG's canonical spec
home is `w3.org/TR/png`).

Extracted from `kotoba-lang/kasane` (kasane.png, ADR-2606272100). Chunk
structure is a small EDN grammar interpreted by a self-contained copy of the
generic binary-grammar decode engine (`png.decode`, duplicated from
kasane.decode so this repo has no back-dependency on kasane); IDAT payloads
are zlib, decoded via `org-ietf-deflate`; scanlines are unfiltered per PNG
§9 (None/Sub/Up/Average/Paeth). R0 supports bit-depth 8/16; sub-byte depths
and Adam7 interlace are not yet unfiltered.

## Usage

```clojure
(require '[png.core :as png] '[png.grammar :as g])

(png/parse g/grammar png-bytes)
;; => {:ihdr {:width :height :bit-depth :color-type ...} :chunks [...] :pixels [...]}
```

`png.grammar/grammar` is `resources/png/grammar.edn` as a requireable value
(since 2026-09-25), for callers with no classpath-resource loader -- a
library running under kbb cannot guess a path to the resource. The resource
file stays the source of truth: `png.grammar-test` asserts the two are equal
on both runtimes.

## Test

Both runtimes, and both are load-bearing.

```sh
kbb -M:test    # kbb (ClojureScript on Node): core, encode, grammar; the javax.imageio ns is #?(:clj) and skipped
```

The JVM half (including `png.encode-jvm-test`, the javax.imageio oracle) runs
through a JDK oracle runner that mirrors `.cljk` to `.cljc` (as
kotoba-lang/image's `scripts/jvm_test.cljk` does). 2026-09-25: kbb 13 tests /
35 assertions, JVM 15 tests / 43 assertions, 0 failures.

`png.encode-test` is `.cljc` and `png.encode-jvm-test` is not, deliberately.
Until 2026-08-19 the writer's whole suite was `.clj`, and under ClojureScript
`(int c)` over a string gives 0 -- so every chunk type was written as four
zero bytes, and every PNG this repository produced outside the JVM was
unreadable. The file still had a signature, a plausible length and a correct
CRC over the zeroed type, so nothing said so until a reader ran off the end of
the data. **An assertion parked in a `.clj` file is an assertion ClojureScript
never makes.** `png.core-test` was JVM-only until 2026-09-25 (its zlib came
from `java.util.zip.Deflater`, so `kbb -M:test` died loading it); it now
writes its streams with org-ietf-deflate and runs on both.

## Encoding (`png.encode`)

The decoder has been here since the `kasane` extraction and nothing could
write one. That asymmetry only shows up when something already holds pixels
and needs a browser to see them — a PDF image XObject decodes to raw samples,
and raw samples are not a picture anyone can display.

```clojure
(require '[png.encode :as encode])
(encode/encode pixels {:width 640 :height 480 :color :rgb})
;; => PNG bytes
```

Bit depth 8, colour types `:gray :gray-alpha :rgb :rgba`, no interlace, one
`IDAT`, filter type 0 on every scanline. That is exactly what `png.core/parse`
can read back — R0 there does not unfilter sub-byte depths or Adam7 — so the
pair round-trips and a writer that emitted something its own reader could not
take would be a writer nobody could check. 16-bit is refused rather than
truncated; a sample count that does not fit the geometry is refused rather
than padded, because padding produces a file that opens and is wrong (the
image skewed diagonally, which is what a row-length error always looks like
and never says).

Per-line filter selection is deliberately absent — see the ns docstring. The
tests check the output against `javax.imageio` as well as against `png.core`,
because a writer checked only by its own reader can be wrong in the same
direction twice.
