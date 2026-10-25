# kotoba-lang/org-dicomstandard-dicom

**DICOM (NEMA PS3, the medical imaging standard) — the Part 10 file
structure and Part 5 data element encoding — in portable, dependency-free
`.cljc`.**

This workspace has `com-dicomweb`, a repo *named* for DICOM whose actual
contents (audited before this repo was written) are a ~190-line CRUD REST
facade — `entity-specs`, `routes`, `POST /v1/...` — with zero byte
operations. It does not implement DICOM. This repo is the real thing: an
actual codec for the wire bytes a PACS, modality, or viewer exchanges.

## What this is

- **PS3.10 §7.1**: the Part 10 file structure — 128-byte preamble, the
  4-byte `"DICM"` magic, and the File Meta Information group (tag group
  `0002`), which PS3.10 fixes to always be encoded in Explicit VR Little
  Endian regardless of what transfer syntax the file meta group itself
  goes on to declare for the rest of the file.
- **PS3.5 §7.1**: data element encoding in **both** header shapes —
  **Explicit VR** (`tag + VR + length`, where the VR determines whether
  the length field is 16 or 32 bits) and **Implicit VR** (`tag + length32`
  always, VR resolved from a data dictionary) — and **both** byte orders
  (little endian, the default, and big endian, retired but still legal to
  encounter).
- **PS3.5 §6.2 Table 6.2-1**: all 28 named VRs — `AE AS AT CS DA DS DT FL
  FD IS LO LT OB OD OF OW PN SH SL SQ SS ST TM UI UL UN US UT` — including
  the short-form (16-bit length) / long-form (32-bit length, 2 reserved
  bytes) split, and the padding rule (space for text, NULL for `UI` and
  `OB`).
- **PS3.5 §7.5**: `SQ` (Sequence) nesting, with both **defined length**
  (read exactly N bytes) and **undefined length** (`0xFFFFFFFF`, read
  until a delimiter pseudo-element: `FFFE,E000` Item, `FFFE,E00D` Item
  Delimitation, `FFFE,E0DD` Sequence Delimitation) forms, for both the
  sequence itself and its items independently.
- **PS3.5 Annex A.4**: encapsulated (compressed) Pixel Data framing — the
  Basic Offset Table + fragment Items + Sequence Delimitation Item
  structure that wraps a JPEG/JPEG2000/RLE bitstream, without decoding
  the compressed payload itself.

## What this is not

- **No image decoding.** This library frames the bytes of a compressed
  Pixel Data fragment (or hands back a flat native-form byte array); it
  does not decode JPEG, JPEG 2000, or RLE pixel data into pixels. That is
  a different, much larger job (an image codec, not a wire-format codec)
  and out of scope by the task that produced this repo.
- **No network.** DICOM's network protocol (DIMSE, Association
  negotiation, C-STORE/C-FIND/C-MOVE over the upper-layer protocol,
  PS3.7/PS3.8) is not here — only the *file* encoding (PS3.10) and the
  data element encoding it shares with the network protocol (PS3.5).
- **No IO, no sockets, no threads.** Every function is pure:
  bytes/values in, bytes/values (or a named error) out.
- **No extended character sets.** Text decoding assumes the DICOM
  default repertoire (US-ASCII); `Specific Character Set (0008,0005)`
  and its ISO 2022 escape sequences are not implemented — a byte >= 0x80
  in a text value is a named error, not a guess.
- **Not the full PS3.6 data dictionary.** `dicom.dictionary` ships a
  small hand-picked subset (the tags this library's own logic and test
  fixtures need) with an overridable `resolve-vr` protocol, not the
  thousands-of-entries standard registry. See `dicom.dictionary`'s
  docstring.
- **Not the full PS3.5 Annex A transfer syntax table.** `dicom.transfer-
  syntax` covers the three uncompressed syntaxes plus a representative
  handful of compressed ones (enough to prove encapsulated-framing
  detection works); it is not exhaustive.

## Surface

```clojure
(require '[dicom.file :as file] '[dicom.dataset :as ds])

(def record
  {:file-meta [{:tag {:group 0x0002 :element 0x0002} :vr :UI
                :value ["1.2.840.10008.5.1.4.1.1.7"]}
               {:tag {:group 0x0002 :element 0x0003} :vr :UI
                :value ["1.2.3.4.5.6.7.8.9"]}
               {:tag {:group 0x0002 :element 0x0010} :vr :UI
                :value ["1.2.840.10008.1.2.1"]}]
   :transfer-syntax-uid "1.2.840.10008.1.2.1"
   :dataset [{:tag {:group 0x0010 :element 0x0010} :vr :PN :value ["DOE^JOHN"]}
             {:tag {:group 0x0028 :element 0x0010} :vr :US :value [512]}]})

(def bytes (file/encode record))
(file/decode bytes)
;=> [:ok {:transfer-syntax-uid "1.2.840.10008.1.2.1" :dataset [...] ...}]
```

| namespace | |
|---|---|
| `dicom.bytes` | byte-order-explicit u16/u32 read/write, ASCII<->bytes, portable `char-code` |
| `dicom.vr` | the 28-VR table, short-form/long-form classification |
| `dicom.tag` | `(group,element)` tag read/write, item/delimiter pseudo-tags |
| `dicom.numeric` | signed 16/32-bit conversion, IEEE-754 float encode/decode |
| `dicom.dictionary` | tag -> VR lookup for Implicit VR (overridable, `:UN` fallback) |
| `dicom.element` | single data-element header + value encode/decode, both VR modes |
| `dicom.dataset` | dataset (element list) + `SQ` item/nesting recursion |
| `dicom.pixel-data` | encapsulated Pixel Data fragment framing |
| `dicom.transfer-syntax` | Transfer Syntax UID -> `{:vr-mode :endian}` |
| `dicom.file-meta` | Part 10 preamble + magic + File Meta Information group |
| `dicom.file` | top-level Part 10 file decode/encode |

## Two details that are usually got wrong

**Explicit VR has two header shapes, and which one a VR gets is a fixed
property of the VR — never inferred from the value's actual size.**
`AE AS AT CS DA DS DT FL FD IS LO LT PN SH SL SS ST TM UI UL US` use
`tag + VR(2) + length(16-bit)`; `OB OD OF OW SQ UN UT` use `tag + VR(2) +
reserved(2, must be 0) + length(32-bit)`. A codec that always writes the
16-bit form works fine until the first `OB` (a private blob, an overlay)
or `SQ` shows up, at which point it either truncates a length over 65535
or writes stray length bytes into the reserved field and desynchronises
everything after it — a failure invisible against your own output, since
your own decoder made the same mistake symmetrically. `dicom.vr`'s
round-trip test therefore sweeps every VR against Explicit VR x Implicit
VR x little x big endian (108 cases), not just the ones a first pass
happened to exercise.

**Implicit VR has no VR field at all — every length is 4 bytes,
regardless of what the VR would imply in Explicit VR — and the VR must
come from a data dictionary keyed on the tag.** Treating Implicit VR as
"Explicit VR but always read a 2-byte length" silently misparses roughly
half the DICOM files a decoder will ever see in practice (Implicit VR
Little Endian, `1.2.840.10008.1.2`, is DICOM's *default* transfer syntax
when nothing else is negotiated). `dicom.dictionary/resolve-vr` falls
back to `:UN` for any tag it doesn't recognise, per PS3.5 §6.2.2 — not a
guess this library invents, the standard's own answer for "VR unknown".

## A cross-runtime bug this library's own suite caught

`(map int "PN")` gives the ASCII code points `[80 78]` on the JVM and
**`[0 0]`** under ClojureScript, where a Clojure character is a
one-character JS string and `int` of a non-numeric string goes through
JS's `ToInt32` coercion (`NaN` -> `0`), not a code-point extraction. Every
VR code, every ASCII text value, and every hand-built test fixture that
used `(int \X)`-style byte construction in this repo's own draft was
silently building all-zero VR codes and all-zero string bytes under cljs
— which round-tripped clean against a decoder with the exact same bug,
and only surfaced as `:dicom/unknown-vr` and empty decoded values once
the ClojureScript suite (not the JVM one) actually ran. `dicom.bytes/
char-code` is the reader-conditional fix (`.charCodeAt` on cljs), used
throughout `dicom.vr/vr->code` and `dicom.bytes/ascii->bytes`. This is
the same trap this workspace's `org-modbus` README documents hitting
three times in one day across three different libraries — a fourth,
independent occurrence, caught by following the same "run both runtimes"
discipline that caught the first three.

A second, narrower cross-runtime trap fixed along the way: Java's
`String.trim()` strips every character with code point <= `U+0020`
(which includes NUL, `UI`'s pad byte); JavaScript's `.trim()` strips only
Unicode whitespace, which does **not** include NUL. `dicom.element`'s
text padding strip is therefore done at the byte level (removing the
specific pad bytes `0x20`/`0x00` before ASCII conversion) rather than via
a generic string-trim call, which would have silently left a trailing
NUL on decoded UIDs under cljs only.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule:
`:dicom/bad-magic`, `:dicom/truncated-file`, `:dicom/unknown-vr`,
`:dicom/unknown-transfer-syntax`, `:dicom/non-ascii-byte`/
`:dicom/non-ascii-char`, `:dicom/unexpected-undefined-length` (a
non-`SQ`, non-Pixel-Data element claiming undefined length — only `SQ`
and encapsulated `OB`/`OW` Pixel Data may legally do that), `:dicom/
expected-item-tag`, `:dicom/element-overruns-container`, `:dicom/item-
overruns-container`, `:dicom/missing-group-length`, `:dicom/bad-preamble-
length`. **Those keywords are contract.**

### Proof these negative tests discriminate

During development, two guards were deliberately broken, one at a time,
to confirm the corresponding test fails for the *named* reason and not
merely "something broke":

1. **`dicom.file-meta/decode-header`'s magic check** — replaced
   `(if (not= magic-bytes magic) ...)` with `(if false ...)`, so a
   corrupted-magic file would be accepted. Result: exactly
   `file-meta-bad-magic-is-a-named-error` failed (all other 40 tests
   stayed green), with the assertion showing the corrupted bytes decoded
   as `[:ok {...}]` instead of `[:error :dicom/bad-magic]`. Restored;
   suite back to 0 failures.
2. **`dicom.dataset/decode-element`'s undefined-length guard** — replaced
   the `(= length vr/undefined-length)` cond clause (guarding against a
   plain, non-`SQ`/non-Pixel-Data VR claiming undefined length) with
   `false`. Result: exactly `unexpected-undefined-length-on-plain-vr-is-
   a-named-error` failed — not with a wrong value, but with an **uncaught
   `java.lang.ArithmeticException: integer overflow`** from
   `dicom.bytes/slice` trying to read `0xFFFFFFFF` bytes past a buffer
   end. This is a stronger discrimination result than a value mismatch:
   removing the guard doesn't just return the wrong thing, it crashes,
   which is exactly the failure mode the guard exists to convert into a
   named, catchable error. Restored; suite back to 0 failures.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both: **41 tests, 1849 assertions, 0 failures.**

Test vectors are cited to the specific PS3.5/PS3.10 section next to each
assertion. DICOM's freely-published standard (dicomstandard.org /
dicom.nema.org) describes the wire format precisely in prose and tables,
but — unlike e.g. Modbus's V1.1b3 Annex worked examples — does not ship a
byte-for-byte annotated sample file in the normative text itself. Every
normative rule cited in this codebase's docstrings and tests was fetched
from the current online edition of the standard during development and
quoted at the point of use; the specific hand-built byte sequences that
exercise those rules are marked `;; constructed, not a published spec
vector` where that distinction matters. A few well-known, non-DICOM-
specific constants (the IEEE 754 binary32 bit patterns for 1.0/-2.0/0.0)
are cited to their own well-known source rather than to DICOM.

The round-trip property test (`decode(encode(x)) == x`) sweeps all 27
non-`SQ` VRs (`SQ`'s value isn't scalar, so it gets its own nested-
dataset tests) x Explicit/Implicit VR x little/big endian — 108 cases —
plus dedicated tests for `SQ` defined- and undefined-length nesting,
item undefined-length nesting, encapsulated Pixel Data, the full Part 10
file (three transfer syntaxes), and the File Meta Information header.
