# kotoba-lang/org-dnp3

**DNP3 (IEEE Std 1815-2012, "Distributed Network Protocol") data link,
transport-function and application-layer wire codec — a useful subset — in
portable `.cljc`, with no dependencies.**

Named the same way this workspace names spec-origin repos: reverse-DNS of
the specifying body's domain (`dnp.org`), not a language suffix — see this
repo's sibling `kotoba-lang/org-modbus`, which this repo's structure and
CRC-testing discipline are directly modeled on.

## What this is

A codec: bytes in, structured data out, and back, for the parts of DNP3
that show up in real electric-grid SCADA traffic — data link framing with
its per-16-byte-block CRC, transport-function segmentation, and application
object headers for binary input (group 1/2), analog input (group 30/32),
control relay output block (group 12 var 1), and the zero-length class-data
polling objects (group 60).

## What this is not

**Not a master or an outstation.** There is no polling loop, no point
database, no event buffer, no unsolicited-response state machine — those
belong to a station implementation built *on* this codec, not in it.

**Not a TCP or serial transport.** DNP3 usually rides on TCP port 20000 (or
a serial line, in which case the data link layer itself has no distinct
concept of "port" — it's the same framing either way). This library takes
and returns byte vectors; opening a socket, buffering a partial read, or
reading a serial port is the caller's job.

**Not the whole object library.** IEEE 1815 Part 4 defines dozens of
groups (counters, frozen counters, double-bit binary, string objects, file
transfer, secure authentication...). This repo implements the common SCADA
point subset named above. Extending `dnp3.objects/point-codecs` with a new
`[group variation]` entry is the extension point when another one is
needed — not a reason to consider this "incomplete" for what it claims.

## Surface

```clojure
(require '[dnp3.dl :as dl] '[dnp3.transport :as transport]
         '[dnp3.app :as app] '[dnp3.objects :as objects] '[dnp3.crc :as crc])

;; Application layer: a "read class 0/1/2/3" integrity poll
(:bytes (app/encode-request
          {:fir true :fin true :con false :uns false :sequence 3 :function :read
           :object-groups [{:group 60 :variation 1 :qualifier-kind :no-range}
                            {:group 60 :variation 2 :qualifier-kind :no-range}
                            {:group 60 :variation 3 :qualifier-kind :no-range}
                            {:group 60 :variation 4 :qualifier-kind :no-range}]}))
;=> [0xC3 0x01 0x3C 0x01 0x06 0x3C 0x02 0x06 0x3C 0x03 0x06 0x3C 0x04 0x06]

;; Transport function: split that fragment into ≤249-byte segments...
(def segs (transport/segment app-fragment-bytes))

;; ...and frame each segment as a data-link frame
(:bytes (dl/encode {:dir true :prm true :fcb false :fcv false
                     :function :unconfirmed-user-data :destination 4 :source 1}
                    (:bytes (first segs))))
```

| namespace | |
|---|---|
| `dnp3.crc` | CRC-16/DNP: `crc16`, `crc16-bitwise`, `crc16-bytes` |
| `dnp3.dl` | data link framing — `encode` `decode`, the control-byte codec, per-block CRC |
| `dnp3.transport` | transport-function segmentation — `segment` `decode-segment` `reassemble` |
| `dnp3.objects` | object payload codecs — `point-codecs`, keyed `[group variation]` |
| `dnp3.app` | APCI, IIN, object headers, `encode-request` `decode-request` `encode-response` `decode-response` |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus`.

## Three details that are usually got wrong

**DNP3's CRC is not one CRC over the whole frame.** Unlike Modbus RTU,
where a single CRC-16/MODBUS covers the entire message, DNP3's data link
layer runs CRC-16/DNP **once per 16-byte data block**, each with a fresh
`init` of 0x0000 — there is no running CRC carried from one block to the
next. `dnp3.dl` gets this wrong exactly once, in the sense that it would be
easy to write a whole-frame CRC and have every round-trip test still pass,
because encode and decode would still agree with each other. It only fails
against a real device, or against `dnp3.crc`'s check-value test.

**The header CRC covers the two sync bytes.** `0x05 0x64` isn't outside the
checksum's scope the way, say, an HDLC flag byte would be — corrupting the
sync pattern itself is detectable.

**CRC-16/DNP init is 0x0000, not 0xFFFF.** It's tempting to copy
CRC-16/MODBUS's parameters (init 0xFFFF, no final xor) since both are
reflected width-16 CRCs with a similarly-shaped polynomial family — DNP3's
is a different member of that family: init 0x0000, and the result is
**complemented** (`xorout` 0xFFFF) before it goes on the wire.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule —
`:crc-mismatch`-shaped names (`:header-crc-mismatch`, `:block-crc-mismatch`),
`:bad-start-byte-1`/`:bad-start-byte-2`, `:length-too-small`,
`:user-data-too-long`, `:unknown-function-code` (both link-layer and
application-layer, in their respective namespaces), `:missing-fir`,
`:sequence-gap`, `:missing-fin`, `:segment-after-fin`,
`:unknown-group-variation`, `:unknown-qualifier-kind`. **Those keywords are
contract**, the same way they are in `org-modbus` — a test that only checks
"decoding failed somehow" is worthless, because a different bug in a
different layer can also make decoding fail somehow.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

The CRC is checked three ways, same discipline as `org-modbus`:

1. The CRC RevEng catalogue check value, `0xEA82` for `"123456789"`.
2. `crc16` (nibble table) against `crc16-bitwise-complemented` (the
   definition) over **all 65,536 two-byte inputs**.
3. Every single-bit error across a 20-byte frame is caught.

Every negative-path test asserts the **specific** `:reason` keyword, not
merely that `:status` came back `:error` — and each was proven to
discriminate during development by temporarily disabling the check it
guards (commenting out the CRC compare, the sequence-gap compare, etc.),
confirming the *targeted* test failed and no other test masked it, then
restoring the check.

## Honesty about test vectors

The CRC check value and the structural shape of the data-link header
(start bytes, `Length` semantics, per-block CRC) are the two facts this
suite treats as externally verified — the former against the CRC RevEng
catalogue, the latter against this session's confident recollection of
IEEE 1815 §9.2. The application-layer function-code numbers, IIN bit
positions, and CROB field layout are internally consistent and exercised
for round-trip correctness, but are marked `;; constructed, not a
published spec vector` in `dnp3.objects` and `dnp3.app` rather than
presented as verbatim quotations of the standard's own tables, which this
session has not cross-checked against the paid IEEE text.

## Not here

**Secure Authentication (IEEE 1815 Part 5/Annex).** A separate, much
larger surface (HMAC challenge-response, key management) that nothing in
this workspace currently needs.

**Counters, frozen counters, double-bit binary, file transfer, and the
rest of the object library** beyond the SCADA-common subset named above.
Nothing in this workspace exercises them yet, and adding untested decoders
for objects nobody sends is how a protocol codec acquires bugs nobody
finds — the same reasoning `org-modbus`'s README gives for leaving out
Modbus's file-record and FIFO functions.

**Timing.** Like Modbus RTU's inter-frame silence, nothing about *when* to
retransmit, how long to wait for a confirmation, or link-layer keep-alive
is a byte-codec concern.
