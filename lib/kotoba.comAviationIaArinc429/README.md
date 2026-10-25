# kotoba-lang/com-aviation-ia-arinc-429

**A codec for the ARINC 429 32-bit word — Label, SDI, Data (BNR/BCD),
SSM and odd Parity — in portable `.cljc`, published by SAE ITC / AEEC
(store: aviation-ia.com).**

## What this is not

This is a *codec*: it packs and unpacks the bit pattern of a single
32-bit ARINC 429 word. It is **not** a bus controller, not a line
driver, has **no IO, no threads, no timing**, does not arbitrate the
physical two-wire differential bus, does not implement the electrical
characteristics (voltage levels, rise/fall times) the standard also
specifies, and makes **no airworthiness or certification claim of any
kind**. ARINC 429 is used in safety-critical flight-deck systems; this
library is a piece of software for reasoning about word bit patterns
in a test bench, simulator, or ground-support tool, and nothing here
should be read as validated for use in or near an actual aircraft
system.

## Provenance — read this before trusting a number here

**This implementation has not seen the paid AEEC/ARINC 429 standard
text.** ARINC specifications are sold through aviation-ia.com and are
not freely available. Everything in this library's bit-layout and
field-semantics is reconstructed from **publicly available secondary
sources**: general-aviation "ARINC 429 Tutorial" style application
notes and PDFs distributed by avionics bus-analyser/test-equipment
vendors (the kind published by companies like Excalibur Systems,
AIM-Online, and Condor Engineering/GE describing the protocol to their
customers), which describe the word layout, the label reversal, the
BNR/BCD data conventions and the SSM table in terms that are widely
repeated and largely consistent with each other, but are **not** a
citation of the standard's own wording.

Every concrete worked value in the test suite that is not an
**exhaustive sweep of the entire space** is commented
`;; constructed, not a published spec vector` — invented, round
numbers chosen to exercise the code, not values copied from a real
Interface Control Document (ICD) for a real aircraft parameter.

**Least-confident value in this library: the exact sign polarity of
the BCD SSM row** (`arinc429.ssm/bcd-table`, which pattern means "plus"
vs "minus"). The *codes themselves* (which 2-bit values belong to which
data type's SSM row) are corroborated across several independent public
sources; the BCD sign assignment specifically is the one place this
implementation is least sure it matches the real standard, and it says
so at the point of definition, not just here.

## Surface

```clojure
(require '[arinc429.word :as word]
         '[arinc429.label :as label]
         '[arinc429.bnr :as bnr]
         '[arinc429.bcd :as bcd]
         '[arinc429.ssm :as ssm])

(label/label->octal-str 131)                          ;=> "203"
(word/pack-word {:label 0203 :sdi 1 :data 12345 :ssm 3})
;=> [:ok 3770738113]   ;; a non-negative 32-bit integer on BOTH runtimes

(word/unpack-word 3770738113)
;=> [:ok {:label 131 :sdi 1 :data 12345 :ssm 3}]

(bnr/encode 12.5 {:sig-bits 12 :resolution 0.25})      ;=> [:ok 6400]
(bnr/decode 6400 {:sig-bits 12 :resolution 0.25})      ;=> [:ok 12.5]

(bcd/encode-value 4523)                                ;=> [:ok 17699]
(ssm/interpret 3 :bnr)                                 ;=> [:ok :normal-operation]
```

| namespace | |
|---|---|
| `arinc429.bits` | portable bit primitives: `u32` (the ClojureScript-negative-number fix), `popcount32`, `reverse-byte`, `field` |
| `arinc429.label` | the octal label / wire-byte reversal — encode, decode, string parse/print |
| `arinc429.word` | the full 32-bit word: `pack-word`/`unpack-word`, odd parity computed and checked |
| `arinc429.bnr` | BNR (two's-complement numeric) data-field encode/decode with caller-supplied significant-bits + resolution scaling |
| `arinc429.bcd` | BCD (5-digit, 4+4+4+4+3 bit) data-field encode/decode |
| `arinc429.ssm` | the Sign/Status Matrix table, per data type (`:bnr` `:bcd` `:discrete`) |

Bytes/fields are plain non-negative integers in and out; words are the
canonical **unsigned** 32-bit integer (see `arinc429.bits/u32`) on both
runtimes.

## The single most common ARINC 429 bug — the label reversal

Every ARINC 429 word is transmitted **least-significant-bit first**:
word bit 1 goes out on the wire first, bit 32 (parity) last, uniformly
across the whole word — Label, SDI, Data and SSM are all read that way.

The trap is that the Label (word bits 1-8) is **conventionally printed
as a 3-digit octal number** using the opposite convention: bit 8 as
the octal number's most-significant bit, bit 1 as its least-significant
bit. Concretely, octal label `203` is binary `10000011` written the
normal way — but the byte that actually goes out on the wire, bit 1
first, is `11000001`, the **mirror image** of that byte, which prints
as octal `301`. Read the wire byte back as if it were already the
printed label and you get `301` where `203` was meant — not garbage,
not an error, a different, equally plausible-looking label. This is
exactly the shape of `org-modbus`'s reflected CRC polynomial (`0xA001`
vs `0x8005`, documented in that library's own README): one field in
the protocol is bit-mirrored relative to every other field in the same
word, and treating it uniformly is the classic wrong-and-plausible
bug. `arinc429.label/octal-label->wire-byte` / `wire-byte->octal-label`
share the single `reverse-byte` primitive precisely so the two
directions can't drift apart, and the test suite round-trips **all 256
possible labels** through it exhaustively.

## Two more details this library got right (or is honest about)

**Parity is computed over the whole 32-bit word, and the parity bit
(bit 32) is set on close to half of all real words.** Under
ClojureScript, `bit-or`/`bit-and`/`bit-shift-left` coerce to a
**signed** 32-bit integer (`ToInt32`); a word with bit 32 set comes
back as a **negative number** unless it is explicitly re-canonicalised
to unsigned (`arinc429.bits/u32`, i.e. `x >>> 0`). This is not a
theoretical concern — see "Verify" below for the actual demonstration
of this bug being introduced and caught.

**BCD's fifth (most-significant) digit only gets 3 bits, not 4** — four
4-bit digits plus one 3-bit digit exactly fills the 19-bit Data field
(4×4+3=19), and that last digit can only hold 0-7, never 8 or 9.
`arinc429.bcd/encode-digits` rejects 8 or 9 in that position with a
named error (`:arinc429/bcd-digit-out-of-range`) rather than silently
truncating or wrapping it.

## Errors

Returned as `[:error keyword ...]`, never thrown:
`:arinc429/label-out-of-range`, `:arinc429/sdi-out-of-range`,
`:arinc429/data-out-of-range`, `:arinc429/ssm-out-of-range`,
`:arinc429/parity-mismatch`, `:arinc429/not-octal`,
`:arinc429/unknown-data-type`, `:arinc429/unknown-status`,
`:arinc429/bnr-sig-bits-out-of-range`,
`:arinc429/bnr-value-out-of-range`, `:arinc429/bcd-digit-count`,
`:arinc429/bcd-digit-out-of-range`, `:arinc429/bcd-value-out-of-range`.
**Those keywords are contract** — the test suite asserts the specific
keyword, not just that *some* error came back.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

21 tests, 66,342 assertions, on both runtimes. Exhaustive sweeps: all
256 possible labels (through `reverse-byte`'s involution, through
`label`'s octal round trip, and through a full word pack/unpack); the
word round trip additionally sweeps every label × every SDI × every SSM
× 4 representative data bit patterns (16,384 packed words, each checked
non-negative and round-tripped); BCD sweeps **all 80,000** representable
values (`00000`-`79999`) end to end.

This library's own suite was used to demonstrate, not just assert, the
ClojureScript-negative-word bug this README warns about: temporarily
replacing `arinc429.bits/u32` with the identity function reproduces
exactly the failure the code exists to prevent — under
`kbb --backend sci scripts/verify-cljs.cljk`, `word-round-trips-exhaustively` fails
with `expected: (>= word 0), actual: (not (>= -2147483648 0))` (and
many more negative words like it) while the identical suite stays
green under `kbb -M:test`, because the JVM's `bit-or` operates on
64-bit longs and never needed the fix. The same technique was used
against `arinc429.word/parity-ok?` (inverting `odd?` to `even?`):
`word-parity-mismatch-is-detected` then fails with
`expected: (= :ok (first (word/unpack-word good))), actual: (not (= :ok :error))`
— a validly-parity'd word gets rejected — proving the negative test
actually discriminates on the parity check specifically, not on some
unrelated failure. Both breaks were reverted before this repo was
published; `git diff` against the commit shows no trace of either.

## Not here

**Sockets, buses, and the physical layer.** ARINC 429 is a
point-to-point differential pair with defined voltage levels and rise
times; nothing here touches a wire.

**Discrete-word bit meanings.** A Discrete data word's 19 Data bits
each mean something different per-parameter, per the aircraft's ICD —
that mapping cannot be implemented generically. `arinc429.word` hands
back the raw 19-bit integer; picking bits apart per-parameter is the
caller's job.

**Per-parameter BNR/BCD characteristics tables** (which real label uses
how many significant bits, at what resolution). Those numbers belong to
a specific piece of equipment's ICD and are not invented here — see
"Provenance" above. `arinc429.bnr`/`arinc429.bcd` take `sig-bits`/
`resolution` (BNR) as parameters rather than hardcoding a table.

## Naming

`com-aviation-ia-arinc-429` is the reverse-DNS of the label's publisher
(SAE ITC / AEEC, standards sold at aviation-ia.com), per this
workspace's origin-domain naming convention. `manifest/origin-domains.edn`
in the parent workspace does not currently record an origin for this
repo, so this name was chosen rather than looked up — if that file is
later updated with an authoritative origin, this repo's name should
follow it.
