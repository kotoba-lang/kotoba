# kotoba-lang/org-sae-j1939

**SAE J1939 over CAN — the 29-bit extended identifier, PGN derivation, the
Transport Protocol (TP.CM/TP.DT) reassembly, and a small SPN decode helper
— in portable `.cljc`, with no dependencies.**

## What this is not

**A CAN driver.** No SocketCAN, no vendor CAN-FD/USB-CAN adapter binding,
no arbitration, no bus timing. This library takes and produces plain
integers (a 29-bit identifier) and byte vectors (an 8-byte CAN payload);
what puts those on a physical bus, or reads them off one, is a driver this
library does not have an opinion about.

**A general SPN/PGN database.** SAE J1939-71 defines several hundred
Suspect Parameter Numbers across dozens of Parameter Groups. `j1939.spn`
decodes exactly two PGNs — 61444 (EEC1) and 65262 (ET1) — and only the
fields this library is confident are correct, not a from-memory
reconstruction of the whole standard. See that namespace's docstring for
which fields and why.

**A J1939/NMEA 2000 entity model.** This is a bit-level identifier and
PGN codec, not CRUD over a schema of vehicles/sessions/trips. (This
caveat exists because a sibling repo in this workspace, `com-nmea2000-marine`,
turned out to carry an EV-charging `ChargeSession`/`Connector`/`Trip`
schema copied from an unrelated OCPP template — J1939 and NMEA 2000 are
close cousins, both CAN-based, and this library is deliberately the
opposite of that: bytes and bit positions, no entities.)

## Surface

```clojure
(require '[j1939.identifier :as id] '[j1939.tp :as tp] '[j1939.spn :as spn])

;; PGN 61444 (EEC1), broadcast (PDU2), priority 3, source address 0:
(id/pack-identifier {:priority 3 :edp 0 :dp 0 :pf 240 :ps 4 :source-address 0})
;=> [:ok 0x0CF00400]

(id/identifier->pgn 0x0CF00400) ;=> [:ok 61444]

(spn/decode-eec1 [0x00 0xA5 0x96 0x20 0x4E 0xFF 0xFF 0xFF])
;=> [:ok {:driver-demand-percent-torque 40 :actual-engine-percent-torque 25
;         :engine-speed-rpm 2500.0}]
```

| namespace | |
|---|---|
| `j1939.identifier` | `pack-identifier`/`unpack-identifier` (29-bit CAN ID), `pgn-of`/`pgn->fields`/`identifier->pgn`, `pdu1?`, `destination-address` |
| `j1939.tp` | `encode-bam`/`decode-bam`, `encode-rts`/`decode-rts`, `encode-cts`/`decode-cts`, `encode-end-of-msg-ack`/`decode-end-of-msg-ack`, `encode-abort`/`decode-abort`, `decode-tp-cm` (dispatches by control byte), `encode-data-transfer`/`decode-data-transfer`, and the reassembly state machine `start-session`/`add-data-transfer`/`session-complete?`/`session-data` |
| `j1939.spn` | `decode-eec1` (PGN 61444), `decode-et1` (PGN 65262) |

Bytes are `Sequential` collections of ints in 0..255, in and out. Errors
are `[:error reason ...]` tuples, never thrown; success is `[:ok value]`.

## The one detail that is usually got wrong: PDU1 vs PDU2

The 29-bit identifier is Priority(3) | EDP(1) | DP(1) | PF(8) | PS(8) |
SA(8) (clause 5.2). **`PS` means two different things depending on `PF`,
and the PGN is built differently in each case:**

- **PF < 240 (PDU1, "peer-to-peer"):** PS is a **destination address**.
  It is NOT part of the PGN — two frames with the same PF but different
  PS carry the *same* PGN, just addressed to different receivers.
- **PF >= 240 (PDU2, "broadcast"):** PS is a **group extension** and IS
  part of the PGN. There is no destination address in a PDU2 frame —
  every PDU2 message is, structurally, a broadcast.

Folding PS into the PGN unconditionally (or never folding it in) produces
a PGN lookup that is correct for half of all traffic and silently wrong
for the other half — the kind of bug that passes testing against one ECU
and fails against a different message set, and the reason `j1939.identifier`
gives this its own pair of tests
(`pdu1-ps-is-a-destination-address-not-part-of-the-pgn` /
`pdu2-ps-is-a-group-extension-and-is-part-of-the-pgn`) rather than one
generic round-trip check.

TP.CM's message-size and PGN fields are **little-endian** — the opposite
byte order from every big-endian field in `org-ieee-1588` and from Modbus.
`j1939.tp` calls this out explicitly rather than assuming byte order
carries over from the last protocol library written.

## Errors

`:j1939/priority-out-of-range`, `:j1939/edp-not-a-bit`,
`:j1939/dp-not-a-bit`, `:j1939/pf-out-of-range`, `:j1939/ps-out-of-range`,
`:j1939/source-address-out-of-range`, `:j1939/id-out-of-range`,
`:j1939/bad-tp-cm-length`, `:j1939/not-a-bam-frame`,
`:j1939/not-a-rts-frame`, `:j1939/not-a-cts-frame`,
`:j1939/not-an-end-of-msg-ack-frame`, `:j1939/not-an-abort-frame`,
`:j1939/unknown-tp-cm-control-byte`, `:j1939/sequence-number-out-of-range`,
`:j1939/data-transfer-payload-out-of-range`, `:j1939/bad-tp-dt-length`,
`:j1939/tp-sequence-gap`, `:j1939/tp-too-many-packets`,
`:j1939/tp-short-data-transfer`, `:j1939/bad-eec1-length`,
`:j1939/bad-et1-length`. **Those keywords are contract.**
`:j1939/tp-sequence-gap` fires both on a dropped packet and on a
duplicate/reordered one — either means the reassembly buffer can no
longer be trusted to be contiguous, so both are refused the same way.

## Verify

```sh
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk  # ClojureScript
```

Real counts as run for this README: **25 tests, 15087 assertions, 0
failures, 0 errors** — identically on both runtimes. The bulk of the
assertion count is `full-29-bit-identifier-space-round-trip-sweep`: 5000
randomly sampled 29-bit identifiers, unpacked and re-packed, required to
come back byte-identical.

**What is cited from the specification, not constructed:** the 29-bit
field layout and bit positions (clause 5.2), the PF=240 PDU1/PDU2 split,
PGN 61444 (EEC1) and PGN 65262 (ET1) (both given in the task brief this
library was built from and cross-checked here — see
`eec1-pgn-decomposes-to-pdu2-pf-240-ps-4` /
`et1-pgn-decomposes-to-pdu2-pf-254-ps-238`, which derive PF=240/PS=4 and
PF=254/PS=238 from those two PGN numbers by arithmetic, not by assertion),
the SPN 110/174/190/512/513 scaling formulas in `j1939.spn` (linear
`raw * resolution + offset`, all-1-bits = "not available" — J1939-71's
universal convention for these fields), and the TP.CM/TP.DT byte layouts
and PGNs 60416/60160 in `j1939.tp`. **What is `;; constructed, not a
published spec vector`:** every concrete example identifier, PGN pairing,
and TP.CM/TP.DT frame byte-sequence in the test suite — there is no
worked byte-for-byte frame example in the J1939-21 text the way Modbus's
Annex has one, so these are built from the field widths/semantics above,
not copied from the standard.

Discrimination of the negative-test suite was checked by hand: the
sequence-number check in `j1939.tp/add-data-transfer` —
`(not= sequence-number (:next-sequence session))` — was replaced with a
hardcoded `false`, so any sequence number (including a gap or a repeat)
would be silently accepted into the reassembly buffer. `kbb -M:test`
then failed with exactly the two tests that exercise this path —
`tp-sequence-gap-is-refused` and
`tp-sequence-gap-also-catches-a-duplicate-packet` — both showing the
corrupted session map (with the wrong bytes silently merged into
`:buffer`) instead of the expected `:j1939/tp-sequence-gap`, and every
other test still passed. The change was reverted and the full suite
re-run clean before publishing.

## Not here

**Extended Transport Protocol (ETP, PGNs 0xC800/0xC700)**, used for
messages longer than 1785 bytes (255 packets × 7 bytes) — the ceiling on
what TP.CM/TP.DT (this library) can carry. Nothing in this workspace has
needed a message that large yet.

**Address claiming (PGN 60928) and the network-management layer** —
deciding what source address a node uses, negotiating conflicts, and so
on (clause 4, Address Claim Procedure) is a stateful protocol of its own,
not a codec detail.

**Flow-control policy** — when to send a CTS, how many packets to grant,
retry/timeout behavior. `j1939.tp` computes what a well-formed sequence of
TP.CM/TP.DT frames means; deciding when to send which frame is a
transport-driver's job built on top of this codec, not this codec's.
