# kotoba-lang/org-hl7-v2

**HL7 Version 2.x messaging — the ER7 (pipe-delimited) encoding, MLLP wire
framing, and general acknowledgment construction — in portable `.cljc`, with
no dependencies.** Targets the encoding rules of the HL7 v2 Messaging
Standard as codified from v2.3 through v2.5.1 (ER7 §2.6/§2.7 have not
changed shape across that range; this library does not validate against a
specific version's table of allowed trigger events or segment cardinality).

## What this is not

- **Not an interface engine.** No routing, no transformation engine, no
  MLLP *server*, no queueing, no retry policy. It reads and writes bytes
  and strings; what a caller does with a socket around it is out of scope.
- **Not a validating parser.** It structurally decodes any well-formed ER7
  message — including Z-segments, which by definition have locally-defined
  field meanings this library cannot know — without checking that a given
  segment is legal in a given trigger event, that a field's content type
  matches its data type, or that required fields are present. That is the
  job of a conformance profile, which is site- and version-specific.
- **No PHI handling policy, no persistence, no audit trail.** No file I/O,
  no sockets, no threads. Every function here is pure: bytes/strings in,
  data out (or a named `[:error ...]`), nothing else touched.
- **No terminology service.** Coded values (LOINC, SNOMED, HL7 tables) pass
  through as opaque strings; this is a wire codec, not a code-set validator.

## Surface

```clojure
(require '[hl7-v2.delimiters :as delimiters]
         '[hl7-v2.parser :as parser]
         '[hl7-v2.segments :as segments]
         '[hl7-v2.mllp :as mllp]
         '[hl7-v2.ack :as ack])

(def msg (parser/parse-message raw-er7-text))
;=> {:delimiters {:field \| :component \^ ...} :segments [{:id "MSH" :fields {...}} ...]}

(segments/get-value msg "PID" 5)   ;=> "EVERYMAN" (PID-5.1, patient name)
(parser/encode-message msg)        ;=> raw-er7-text back, byte for byte

(def framed (mllp/wrap (parser/encode-message msg)))     ; 0x0B ... 0x1C 0x0D
(mllp/unwrap framed)                                       ;=> {:message ...}

(def ok (ack/build-ack {:original msg :ack-code "AA"
                         :control-id "ACK0001" :timestamp "20260829120000"}))
(parser/encode-message ok)
```

| namespace | |
|---|---|
| `hl7-v2.delimiters` | read MSH-1/MSH-2 from the message itself — never assume `\|^~\&` |
| `hl7-v2.escape` | `\F\` `\S\` `\T\` `\R\` `\E\` `\Xdd..\` escape sequences |
| `hl7-v2.parser` | `parse-field`/`encode-field`, `parse-segment`/`encode-segment`, `parse-message`/`encode-message`, plus `field`/`repeated` builders |
| `hl7-v2.segments` | field-number → name maps and accessors for MSH, EVN, PID, NK1, PV1, OBR, OBX |
| `hl7-v2.mllp` | 0x0B/0x1C 0x0D framing, string- and byte-vector-level |
| `hl7-v2.ack` | general acknowledgment (MSH+MSA) construction, AA/AE/AR/CA/CE/CR |

## The delimiters are read from the message, not assumed

MSH-1 is not a field like the others — it *is* the field separator, the
character sitting right after the literal text `MSH`. MSH-2 is the four (or
more) characters that follow it: component, repetition, escape and
subcomponent separators, conventionally `^~\&`. A parser that hardcodes `|`
and `^~\&` works on every message until it meets the one interface that
runs with different characters (rare, but real — some legacy interfaces use
non-default delimiters specifically to avoid colliding with `^` or `~` in
free-text fields), and then it silently mis-splits every field past MSH-2.
`hl7-v2.delimiters/parse` reads them at runtime from every message.

## Field values: usually a string, sometimes three layers of nesting

Most fields in a real message are plain scalars — one repetition, one
component, one subcomponent. `parse-field` collapses that common case to a
plain unescaped string. A field that actually has structure — PID-3's
`~`-repeated identifier list, an OBR-4 coded element's `^`-separated
identifier and text — comes back as `[[[sub sub] [sub]] [[sub]]]`: a vector
of repetitions, each a vector of components, each a vector of unescaped
subcomponent strings. `encode-field` accepts both shapes and is the exact
inverse of `parse-field` — it only writes a separator where more than one
element is actually present, which is what makes it the *inverse* rather
than merely *a* correct encoding of the same field.

`hl7-v2.parser/field` and `repeated` build the nested shape from plain
strings for hand-constructed messages (used by `hl7-v2.ack`), so callers
don't have to write `[[["ADT"] ["A01"]]]` by hand.

## MSH is special

Splitting `"MSH|^~\&|ADT1|..."` on `|` gives `["MSH" "^~\&" "ADT1" ...]` —
index 1 of that split is MSH-**2**, not MSH-1, because MSH-1 never appears
as delimited text; it *is* the character used to do the splitting.
`parse-segment` synthesises MSH-1 as that literal character and — critically
— keeps MSH-2 as a **raw, unparsed string**. Running `parse-field` on `^~\&`
using `^~\&` as the delimiter set would shred it into four single-character
components; MSH-2 is data about the delimiters, not itself delimited data.

## Errors are named, not thrown

Every parse function returns `[:error <reason>]` on malformed input, never
an exception: `:hl7/not-msh-segment`, `:hl7/msh-too-short`,
`:hl7/msh2-truncated`, `:hl7/segment-too-short`, `:hl7/empty-message`,
`:hl7/mllp-frame-too-short`, `:hl7/mllp-missing-start-block`,
`:hl7/mllp-missing-end-block`, `:hl7/ack-bad-code`, `:hl7/ack-missing-msh`.
**Those keywords are contract** — a test asserting failure asserts the
specific reason, because "it failed somehow" is satisfied by an unrelated
bug just as easily as by the one the test is trying to catch.

## An escape-sequence subtlety the test suite documents rather than hides

`\.br\` (line break) and `\Zxxx\` (site-defined private codes) are not in
this codec's recognised escape set (`F`/`S`/`T`/`R`/`E`/`X` — HL7 v2.x
§2.7.3). `unescape` passes an unrecognised sequence through unchanged
rather than guessing at it. That means **wire text containing an
unrecognised escape sequence does not round-trip through a single
unescape→escape pass** — the literal backslash characters left behind are,
correctly, indistinguishable at that point from a literal backslash a
caller put in real data, and get re-escaped as `\E\` on the way back out.
What the codec does guarantee, and is the property that actually matters
for a caller building a leaf value from a raw string, is the *data-side*
round trip: `unescape(escape(x)) == x` for any `x`, including one
containing a literal backslash. `hl7-v2.core-test/unrecognised-escape-is-
only-stable-across-two-passes` proves both halves of this rather than
letting `field-corpus-round-trip` produce a wrong-and-plausible pass.

## MLLP framing

`0x0B` start block, message bytes, `0x1C` `0x0D` end block — no length
prefix. There is no way to observe TCP's own segmentation from inside a
pure codec, so `mllp/unwrap` (and `unwrap-bytes`) take a buffer the caller
has already delimited by finding the end block on the wire; a caller
reading a real socket owns that scanning. Byte-vector functions treat each
character as one byte (Latin-1/ASCII code point) — correct for the 7-bit
ASCII ER7 defaults to, and a documented simplification for the rarer case
of a declared multi-byte character set (MSH-18).

## Test vectors

The sample ADT^A01 message in the test suite is a structurally standard
transcription of the kind published across HL7 v2 tutorial and
interface-engine documentation (HL7 v2.5.1 Chapter 3 ADT examples, HAPI's
own fixtures, Corepoint/Caristix public sample-message pages) — not
verbatim text copied from the base standard itself. Escape-sequence
mappings (`\F\`/`\S\`/`\T\`/`\R\`/`\E\`) are transcribed from HL7 v2.x
§2.7.3. Vectors without a standard behind them are marked `constructed,
not a published spec vector` in the test source, per this workspace's
honesty-over-vector-count rule.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```
