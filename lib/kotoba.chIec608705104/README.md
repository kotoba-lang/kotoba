# kotoba-lang/ch-iec-60870-5-104

**IEC 60870-5-104 ("Telecontrol equipment and systems — Part 5-104") APCI
and ASDU wire codec — a useful subset — in portable `.cljc`, with no
dependencies.**

Named the same way this workspace names spec-origin repos: reverse-DNS of
the specifying body's domain (the IEC is `iec.ch`), not a language suffix
— see this repo's sibling `kotoba-lang/org-dnp3` (DNP3/IEEE 1815, the
other major electric-grid SCADA telecontrol protocol), both modeled on
`kotoba-lang/org-modbus`'s structure and CRC/verification discipline.

## What this is

A codec: bytes in, structured data out, and back, for the two layers a
104 master or outstation exchanges over TCP:

- **APCI** (`iec60870.apci`) — the frame envelope: start byte `0x68`, a
  length octet, and four control-field octets in one of three formats
  (I: numbered information transfer, S: numbered supervisory
  acknowledgement, U: unnumbered STARTDT/STOPDT/TESTFR).
- **ASDU** (`iec60870.asdu`) — the payload an I-format frame carries: type
  ID, variable structure qualifier, cause of transmission, common address,
  and one or more information objects, for a SCADA-common type-ID subset:
  single-point information (M_SP_NA_1, type 1), measured value normalized
  (M_ME_NA_1, type 9), single command (C_SC_NA_1, type 45), interrogation
  command (C_IC_NA_1, type 100), and measured value short floating point
  with a CP56Time2a time tag (M_ME_TF_1, type 36).

`iec60870.float32` and `iec60870.time` are the two supporting codecs
type 36 needs: IEEE 754 binary32 wire assembly and the seven-octet
CP56Time2a timestamp. `iec60870.frame` wires APCI and ASDU together for
the common case of "one I-format frame, one ASDU."

## What this is not

**Not a master or an outstation.** No polling loop, no point database, no
transmission-timer (t1/t2/t3) state machine, no k/w window bookkeeping for
how many unacknowledged I-frames may be outstanding — those belong to a
station implementation built *on* this codec, not in it.

**Not a TCP stack.** This library takes and returns byte vectors; opening
a socket on port 2404, buffering a partial TCP read, or reconnecting after
a drop is the caller's job — the same division `org-modbus`'s `tcp.cljc`
draws for Modbus TCP's MBAP header.

**Not the whole ASDU type-ID space.** IEC 60870-5-101/104's companion
tables define dozens of types (double-point information, step position,
bitstring, integrated totals, protection events, file transfer, and their
several time-tagged variants). This repo implements the common SCADA
subset named above. Extending `iec60870.asdu/element-codecs` with a new
type-ID entry is the extension point when another one is needed.

## Surface

```clojure
(require '[iec60870.apci :as apci] '[iec60870.asdu :as asdu]
         '[iec60870.frame :as frame] '[iec60870.float32 :as float32]
         '[iec60870.time :as time])

;; A single-point-information spontaneous report, wrapped in an I-frame
(:bytes (frame/encode-i-asdu
          {:send-seq 3 :recv-seq 0}
          {:type-id 1 :sq false :cot {:cause :spontaneous :test false :negative false}
           :common-address 1
           :objects [{:ioa 100 :element {:spi true :quality {}}}]}))

;; Round-trip back
(frame/decode-i-frame *1)
```

| namespace | |
|---|---|
| `iec60870.apci` | frame envelope — `encode-i` `encode-s` `encode-u` `decode` |
| `iec60870.asdu` | ASDU header + information objects — `encode-asdu` `decode-asdu`, `element-codecs` keyed by type id |
| `iec60870.float32` | IEEE 754 binary32 ↔ 4 little-endian wire bytes |
| `iec60870.time` | CP56Time2a, the 7-octet absolute time tag |
| `iec60870.frame` | APCI(I) + ASDU wired together — `encode-i-asdu` `decode-i-frame` |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus` and `org-dnp3`.

## Three details that are usually got wrong

**There is no CRC.** Unlike DNP3's data-link layer (a per-16-byte-block
CRC-16/DNP) or Modbus RTU (a whole-frame CRC-16/MODBUS), IEC 60870-5-104
carries no checksum of its own — the same reasoning `org-modbus`'s
`tcp.cljc` gives for Modbus TCP's MBAP header: TCP already guarantees
byte-stream integrity, so a link-layer-style CRC on top of it would be
redundant. (This is exactly the axis on which 104 differs structurally
from `org-dnp3`, its serial-heritage sibling, which layers over both TCP
*and* serial and so does need its own checksum.)

**A 15-bit sequence number is not a plain 16-bit little-endian integer.**
N(S) and N(R) are packed across two octets with the *low* octet's bit 0
reserved as the I/S/U format discriminator — encoding is `n << 1` into the
low octet and `n >> 7` into the high octet, not a bare `le16`. Treating it
as an ordinary 16-bit field silently doubles every sequence number a peer
reads back.

**VSQ's SQ bit changes what the information-object address field means,
not just how many objects follow.** With `SQ=0` every object carries its
own 3-byte address; with `SQ=1` only the *first* does, and the rest are
implicitly consecutive (`ioa`, `ioa+1`, `ioa+2`, …) — decoding a `SQ=1`
ASDU as though it were `SQ=0` reads the second object's element bytes as
if they were an address, and everything after is shifted.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule —
`:bad-start-byte`, `:length-too-small`/`:length-too-large`,
`:send-seq-out-of-range`/`:recv-seq-out-of-range`, `:asdu-too-long`,
`:unknown-u-function` (APCI); `:unknown-type-id`,
`:common-address-out-of-range`, `:object-count-out-of-range` (ASDU).
**Those keywords are contract**, the same discipline `org-modbus` and
`org-dnp3` hold to — a test that only checks "decoding failed somehow" is
worthless, because a bug in a completely different layer can also make
decoding fail somehow.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

IEEE 754 binary32 is checked against values that follow directly from the
format's own definition (1.0 = `0x3F800000`, 2.0 = `0x40000000`, 0.5 =
`0x3F000000` — sign/exponent/mantissa, not a recollection of protocol
spec text), then round-tripped through the wire assembly for a spread of
values including ones smaller and larger than float32's ~7-significant-
digit precision.

Every negative-path test asserts the **specific** `:reason` keyword, not
merely that `:status` came back `:error`, and each was proven to
discriminate during development by temporarily disabling the check it
guards, confirming the *targeted* test failed and no other test masked
it, then restoring the check.

## Honesty about test vectors

IEEE 754 binary32's well-known constants are the one set of vectors here
independently verifiable from first principles. The APCI/ASDU framing
*mechanics* — start byte, Length semantics, the I/S/U discriminator bits,
VSQ's SQ bit and consecutive-address encoding, the 3-byte little-endian
information-object address — are this session's confident recollection of
widely documented IEC 60870-5-104 structure, exercised for round-trip
correctness. The specific numeric assignments — cause-of-transmission
codes, quality-descriptor bit positions, the SCO (single command) field
layout, QOI values — are marked `;; constructed, not a published spec
vector` in `iec60870.apci`/`iec60870.asdu`/`iec60870.time` rather than
presented as verbatim quotations of the standard's own tables, which this
session has not cross-checked against the paid IEC text.

## Not here

**Redundancy/failover (dual-master, standby link).** A station-level
concern, not a codec one.

**Files, counters, protection events, double-point and step-position
information, and the rest of the type-ID space** beyond the SCADA-common
subset named above. Nothing in this workspace exercises them yet, and
adding untested decoders for objects nobody sends is how a protocol codec
acquires bugs nobody finds — the reasoning `org-modbus` and `org-dnp3`
both give for the object-library subsets they stop at.

**Timing.** t1 (send/confirm), t2 (acknowledge-without-data), t3
(test-frame keep-alive), and the k/w window parameters govern *when* to
send an S-frame or a TESTFR — none of that is a byte-codec concern.
