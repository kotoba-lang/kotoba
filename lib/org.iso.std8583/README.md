# kotoba-lang/org-iso-8583

**ISO 8583 financial transaction messages — MTI, primary/secondary/tertiary
bitmaps, and BCD/ASCII field encode-decode driven by a caller-supplied data
element table — in portable `.cljc`, with no dependencies.** Structural
facts (bitmap bit numbering, BCD nibble packing, the MTI digit breakdown,
the LL/LLL length disciplines) follow ISO 8583 as commonly implemented
across the 1987/1993/2003 editions; this codec does not fix a single
edition's field table as *the* table — see below.

## What this is not

- **Not an acquirer switch, not a network client.** No sockets, no
  connection pooling, no retry/timeout policy, no ISO 8583-over-TCP or
  ISO 8583-over-TLS framing. It turns a message map into bytes and back;
  what carries those bytes is out of scope.
- **Not a fixed field table.** ISO 8583 the standard fixes very little
  about which field number means what — the 1987/1993/2003 editions
  renumber and retype fields against each other, and every acquirer
  customises further on top of whichever edition they nominally follow. A
  codec that bakes in "the" table is really baking in one bank's table.
  Every function in `iso-8583.codec` takes `field-table` as a required
  argument; `iso-8583.fields/default-1987-fields` is a working example to
  test against, not the answer.
- **No PCI scope, no HSM, no key management.** Field 52 (PIN block) and
  field 64/128 (MAC) round-trip as opaque bytes; nothing here encrypts,
  decrypts, verifies a MAC, or touches a key. That is a HSM's job, and a
  codec that pretended otherwise would be exactly the kind of thing PCI
  DSS scope reviews exist to catch.
- **No transaction semantics.** It does not know that field 4 should
  balance against field 6, that a reversal must reference the original
  STAN, or that a response code means "insufficient funds." It moves
  bytes; a switch or host application supplies the business logic.
- No I/O, no sockets, no threads. Every function is pure.

## Surface

```clojure
(require '[iso-8583.codec :as codec] '[iso-8583.fields :as fields])

(def msg {:mti "0200"
          :fields {2 "4111111111111111" 3 "000000" 4 "000000012345"
                   11 "000001" 41 "TERM0001"}})

(def bytes (codec/encode-message msg fields/default-1987-fields))
;=> [48 50 48 48 ...] -- a vector of ints 0..255

(codec/decode-message bytes fields/default-1987-fields)
;=> {:mti "0200" :fields {2 "4111111111111111" ...}}
```

| namespace | |
|---|---|
| `iso-8583.bcd` | packed decimal (BCD) and ISO/IEC 7813 track-2 nibble packing |
| `iso-8583.bitmap` | primary/secondary/tertiary bitmap <-> field-number set, binary and hex forms |
| `iso-8583.mti` | Message Type Indicator digit decomposition/recomposition |
| `iso-8583.fields` | the field-spec shape, plus `default-1987-fields` as an example table |
| `iso-8583.codec` | whole-message `encode-message`/`decode-message` |
| `iso-8583.charcode` | portable character-to-code-point conversion (see below) |

## `(int c)` is not a code point in ClojureScript

Every character-to-byte conversion in this codec goes through
`iso-8583.charcode/char-code` rather than bare `int`, for the same reason
`org-modbus`'s own README documents for `(map int "123456789")`: on the
JVM, `(int c)` on a character gives its code point (`(int \0)` is `48`).
Under ClojureScript, a Clojure character is a one-character JavaScript
string, and `int` on a *string* does numeric-string parsing —
`(int \0)` is `0`, and, worse, `(int \A)` is *also* `0` (`Number("A")` is
`NaN`, coerced to `0` by `int`'s `bit-or 0`). For the digit characters
this codec spends most of its time on, numeric-string-parsing a digit
character happens to equal that digit's value, a different number from
its code point that is nonetheless plausible enough to pass every JVM
test while silently corrupting the ClojureScript path — `mti/valid?`
accepted `"02A0"` as a well-formed MTI under cljs (the `A` parsed to `0`,
which is in the digit range) until this was caught by running the suite
on both runtimes and fixed by routing every char-to-code conversion
through one portable function.

## Bit-level, not string-shaped

Bitmaps are built and read with `bit-and`/`bit-or`/`bit-shift-left`/
`unsigned-bit-shift-right` against actual byte values — bit 1 is the
most-significant bit of the first byte, bit 64 the least-significant bit of
the eighth. BCD packs two decimal digits into one byte, most-significant
nibble first, with the same four operators; there is no shortcut through
`Integer/parseInt`/decimal arithmetic that stays correct once a byte's
high bit (0x80, the sign bit position on a signed byte) is involved.

## Bitmaps chain: primary -> secondary -> tertiary

Bit 1 of a bitmap level is never an ordinary data field: it announces
whether the *next* level is present. Primary bit 1 announces the secondary
bitmap (fields 65-128); secondary bit 1 announces the tertiary bitmap
(fields 129-192). Fields 1, 65 and 129 are therefore reserved indicator
bits, not usable data fields — supplying one as a value returns
`[:error :iso8583/reserved-field-number]`. ISO 8583 itself only
standardises the primary/secondary pair; this chained-indicator shape for
a third level is this codec's committed, documented convention, since how
(or whether) a given network extends to tertiary is itself a
customisation point.

## The length disciplines, and what "length" counts

- **`:fixed`** — exactly `:length` characters (`:n`/`:a`/`:an`/`:ans`/`:z`)
  or bytes (`:b`), no prefix.
- **`:llvar`** — a 2-digit length prefix, max 99.
- **`:lllvar`** — a 3-digit length prefix, max 999.

`:len-encoding` (`:ascii` or `:bcd`) controls how the *prefix itself* sits
on the wire, independently of `:encoding` for the *content* — a length
prefix in BCD ahead of ASCII content, or vice versa, is a real
acquirer-specific combination this table shape supports directly.
Content length that would overflow the prefix's digit budget is a named
encode-time error (`:iso8583/llvar-length-overflow`,
`:iso8583/lllvar-length-overflow`), not silent truncation.

## BCD's odd-digit-count convention is a real customisation point

A packed BCD byte cannot say by itself whether it holds one or two
significant digits — `unpack-digits` always takes the exact count from the
field's length descriptor. This codec's own convention is a **leading**
zero-nibble pad for an odd digit count (`"5"` packs as `0x05`, not
`0x50`); `pack-digits`/`unpack-digits` are exact inverses of each other
under it, and the whole codec is internally consistent end to end. Other
real implementations pad the *trailing* nibble instead. Because BCD
carries no self-describing length, this choice is not observable from the
bytes alone — confirm it against the counterparty's actual interface
specification before assuming this library's convention matches theirs.

## Errors are named, not thrown

`:iso8583/invalid-mti`, `:iso8583/message-too-short`,
`:iso8583/bitmap-too-short`, `:iso8583/invalid-bitmap-hex`,
`:iso8583/unknown-field`, `:iso8583/reserved-field-number`,
`:iso8583/field-number-out-of-range`, `:iso8583/fixed-length-mismatch`,
`:iso8583/llvar-length-overflow`, `:iso8583/lllvar-length-overflow`,
`:iso8583/invalid-length-digits`, `:iso8583/invalid-field-content`,
`:iso8583/missing-field-value`. **Those keywords are contract** — a test
asserting failure asserts the specific reason, because "it failed
somehow" is satisfied by an unrelated bug just as easily as by the one the
test is trying to catch.

## Relationship to `kotoba-lang/kotoba-iso20022`

ISO 20022 is ISO 8583's modern XML-based sibling — different message
family, different wire shape (structured XML elements vs. positional
bitmap-driven binary/BCD fields), used by different rails (SWIFT CBPR+,
domestic RTGS/ACH modernisation) than ISO 8583's card/POS/ATM authorization
world. `kotoba-iso20022` is a cleanroom XML codec + validators for that
family; this library does not duplicate it and the two do not share code,
because they do not share a wire format — the only thing in common is the
"ISO" in both standards' names.

## Test vectors

BCD packing, bitmap bit-numbering, the MTI digit table and the LL/LLL
length disciplines are structural facts of ISO 8583 as widely documented
across processor/switch integration references — textbook material, not
verbatim standard text quoted from memory. Full message byte sequences in
the test suite are `constructed, not a published spec vector`: this suite
does not have confident, verifiable recall of an exact published ISO 8583
wire dump, so it builds its own messages and proves them correct by round
trip and by hand-checked bit/nibble arithmetic, rather than claiming to
match a specification example it cannot cite.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```
