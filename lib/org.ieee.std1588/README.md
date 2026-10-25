# kotoba-lang/org-ieee-1588

**PTPv2 (Precision Time Protocol) message codec — IEEE 1588-2019 / IEEE
802.1AS — in portable `.cljc`, with no dependencies.**

The common 34-byte header, the seven message bodies this workspace has any
use for (Sync, Follow_Up, Delay_Req, Delay_Resp, Pdelay_Req, Pdelay_Resp,
Announce), the 80-bit Timestamp, the 64-bit scaled-nanoseconds
correctionField, and the offsetFromMaster / meanPathDelay arithmetic from
t1..t4.

## What this is not

**A clock servo.** This library does the byte-level codec and the four-
timestamp offset/delay *arithmetic* clause 11.3 defines; it does not
discipline a local clock, run the Best Master Clock Algorithm, decide when
to send a Delay_Req, or filter a noisy series of offset measurements into a
stable frequency correction. Those are a PTP *daemon*'s job (ptp4l, ptpd);
this is the wire format underneath one.

**A network stack.** No sockets, no UDP port 319/320, no Ethernet
multicast, no hardware timestamping. Bytes in, bytes out.

## Surface

```clojure
(require '[ptp.message :as msg] '[ptp.header :as header]
         '[ptp.timestamp :as ts] '[ptp.offset :as offset])

(def clock-id [0x00 0x1B 0x21 0xFF 0xFE 0x3C 0x9A 0x01])

(msg/encode {:message-type :sync
             :domain-number 0
             :flags #{:two-step}
             :correction 0
             :source-port-identity {:clock-identity clock-id :port-number 1}
             :sequence-id 42
             :log-message-interval 0
             :body {:origin-timestamp {:seconds 1735689600 :nanoseconds 0}}})
;=> [:ok [0x00 0x02 0x00 0x2C 0x00 0x00 0x02 0x00 ...]]  ; 44 bytes

(offset/offset-from-master t1 t2 t3 t4)  ; nanoseconds, from clause 11.3
```

| namespace | |
|---|---|
| `ptp.header` | `encode-header`/`decode-header` (the 34-byte common header), `message-types`, `control-field-for`, `flag-bits`, `encode-flags`/`decode-flags`, `encode-port-identity`/`decode-port-identity` |
| `ptp.timestamp` | `encode-timestamp`/`decode-timestamp` (80-bit), `encode-correction`/`decode-correction` (64-bit scaled nanoseconds) |
| `ptp.message` | `encode`/`decode` — header + body together, for Sync, Follow_Up, Delay_Req, Delay_Resp, Pdelay_Req, Pdelay_Resp, Announce |
| `ptp.offset` | `offset-from-master`, `mean-path-delay` — pure arithmetic on four timestamps |

Bytes are `Sequential` collections of ints in 0..255, in and out. Errors are
`[:error reason ...]` tuples, never thrown; a keyword `reason` like
`:ptp/short-header` or `:ptp/message-length-mismatch` is the contract a
caller matches on. Success is `[:ok value]`.

## Two details that are usually got wrong

**correctionField is nanoseconds × 2^16, not nanoseconds.** Clause
13.3.2.6 calls it a "scaled nanoseconds" value; the low 16 bits are
sub-nanosecond precision most stacks fill with zero. Writing the raw
nanosecond count into that field produces a correction off by exactly a
factor of 65536 — for a few-hundred-nanosecond residence time that reads
back as either "basically zero" or "several minutes" depending on which
side of the wire got it wrong, and both are plausible-looking numbers that
corrupt every downstream offset calculation silently.

**A 48-bit seconds field and a 64-bit correctionField are not one number
you can shift.** `bit-shift-left`/`bit-and`/`unsigned-bit-shift-right` are
exact for values up to 32 bits, and ClojureScript's are *signed 32-bit*
underneath — `(bit-shift-left 0xFF 24)` is a negative number in
ClojureScript and a positive 4278190080 on the JVM's 64-bit longs.
`ptp.timestamp` extracts and places these fields one byte at a time with
real `bit-and`/`bit-or`/`bit-shift-left` (always exact for a single byte)
and crosses byte boundaries wider than 32 bits with plain
multiplication/`quot`/`rem` instead of a wide shift. See that namespace's
docstring; `org-modbus`'s README documents the same class of JVM/cljs
divergence catching a UTF-8 encoder.

## Errors

`:ptp/short-header`, `:ptp/unknown-message-type-code`,
`:ptp/unknown-message-type`, `:ptp/missing-message-length`,
`:ptp/missing-source-port-identity`, `:ptp/missing-sequence-id`,
`:ptp/missing-log-message-interval`, `:ptp/bad-clock-identity-length`,
`:ptp/bad-timestamp-length`, `:ptp/seconds-out-of-range`,
`:ptp/nanoseconds-out-of-range`, `:ptp/bad-correction-length`,
`:ptp/correction-must-be-integer-nanoseconds`,
`:ptp/correction-out-of-range`, `:ptp/message-length-mismatch`,
`:ptp/unsupported-message-type`, `:ptp/short-body`. **Those keywords are
contract.**

## Verify

```sh
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk  # ClojureScript
```

Real counts as run for this README: **24 tests, 1030 assertions, 0
failures, 0 errors** — identically on both runtimes.

There is no worked byte-for-byte frame example in the IEEE 1588 text the
way Modbus's Annex has one, so every concrete byte vector in the test
suite is labeled `;; constructed, not a published spec vector` — built
from the field widths and semantics the specification defines (10-byte
Timestamp, 8-byte correctionField scaled by 2^16, 34-byte header), not
copied from a worked example. What **is** taken directly from the
specification, not constructed: the messageType nibble assignments
(clause 13.3.2.2 — 0x0 Sync, 0x8 Follow_Up, 0xB Announce, etc.), the
controlField derivation (clause 13.3.2.14), and every field width in the
header layout. The whole-message round trip is swept 25 times per message
type with randomised timestamps, sequence IDs, correction values and port
identities (`whole-message-round-trip-sweep`), not asserted once.

Discrimination of the negative-test suite was checked by hand: the
short-header length guard in `ptp.header/decode-header` was changed from
`(< (count bs) 34)` to `(< (count bs) 33)`, which makes a 33-byte input
fall through into field extraction that indexes past the end of the
vector. `kbb -M:test` then failed with exactly one test —
`short-header-is-refused` — via a `java.lang.IndexOutOfBoundsException`
at the changed line, and every other test still passed. The change was
reverted and the full suite re-run clean before publishing.

## Not here

**Pdelay_Resp_Follow_Up, Signaling, Management.** They are in the
specification and nothing in this workspace uses them yet; adding untested
code paths for completeness is how a protocol library acquires bugs nobody
finds (the same call `org-modbus`'s README makes about function codes 0x18
and up).

**Sub-nanosecond correctionField precision on encode.** `encode-correction`
only accepts whole nanoseconds. `decode-correction` still reports a
sub-nanosecond-fractional value it receives — as `:nanoseconds nil` rather
than silently truncating it — since a real peer's correctionField is not
obligated to be a clean multiple of 2^16.

**Clock synchronization state, the Best Master Clock Algorithm, and any
notion of "current time."** `ptp.offset` computes the two clause-11.3
formulas from four timestamps a caller already has; it has no opinion on
where those four timestamps came from or what to do with the answer.
