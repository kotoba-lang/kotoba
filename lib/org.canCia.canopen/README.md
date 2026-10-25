# kotoba-lang/org-can-cia-canopen

**CANopen (CiA 301) over CAN — the 11-bit COB-ID predefined connection
set, NMT node control/state/heartbeat, SDO expedited and segmented
transfer, PDO mapping-entry and bit-packed process-data, and EMCY frames
— in portable `.cljc`, with no dependencies.**

## What this is not

**A CAN driver.** No SocketCAN, no vendor CAN-FD/USB-CAN adapter binding,
no arbitration, no bus timing. This library takes and produces plain
integers (an 11-bit COB-ID) and byte vectors (an 8-byte CAN payload);
what puts those on a physical bus is a driver this library does not have
an opinion about.

**A master/slave stack.** There is no SDO client/server state machine
here beyond the pure `check-toggle` helper — deciding when to send a
segment, retry a timed-out transfer, or walk an Object Dictionary is a
CANopen master/slave implementation's job, built on top of this codec,
not this codec's.

**Real-time scheduling.** SYNC period, PDO transmission type (cyclic,
event-driven, RTR-only), heartbeat/node-guarding timeout policy — all out
of scope. This library encodes and decodes the frames; when to send them
is a separate concern.

**A network interface.** No sockets, no threads, no IO of any kind.

**A conformance certification.** This is not a CiA 301 conformance test
suite and makes no claim of interoperability certification. CiA 301
itself is a paywalled CAN in Automation membership document; every
structural claim in this library is cross-checked against open-source
CANopen stacks (see "Where this comes from" below), not against the
standard's own text.

## How this relates to `org-sae-j1939`

Both are CAN application layers in this workspace, and both start from
"how is the identifier composed", but the two protocols answer that
question in incompatible ways and this library does not depend on or
reuse `org-sae-j1939`'s identifier code:

|  | CANopen (this library) | SAE J1939 (`org-sae-j1939`) |
|---|---|---|
| CAN frame | 11-bit **standard** (base) frame | 29-bit **extended** frame |
| Identifier shape | 4-bit Function Code + 7-bit Node-ID | Priority(3)+EDP(1)+DP(1)+PF(8)+PS(8)+SA(8) |
| Addressing | fixed per-object base + node-id (predefined connection set) | PGN derived from PF/PS with a PDU1/PDU2 split |
| Object model | Object Dictionary, index:subindex | Suspect Parameter Numbers within a Parameter Group |
| Transfer protocol | SDO (expedited + segmented, toggle-bit) | Transport Protocol (BAM/RTS-CTS, sequence numbers) |

The two libraries are siblings, not a hierarchy — CANopen never widens
into 29 bits, and J1939 has no COB-ID/function-code concept at all.
Nothing here imports `org-sae-j1939`, and nothing there imports this.

## Surface

```clojure
(require '[canopen.cob-id :as cob] '[canopen.nmt :as nmt] '[canopen.sdo :as sdo]
         '[canopen.pdo :as pdo] '[canopen.emcy :as emcy])

;; SDO expedited write: 4 bytes to Object 0x2000:00
(sdo/encode-download-request {:index 0x2000 :subindex 0 :data [0xDE 0xAD 0xBE 0xEF]})
;=> [:ok [0x23 0x00 0x20 0x00 0xDE 0xAD 0xBE 0xEF]]

;; the SDO-tx COB-ID for node 5 (server -> client responses)
(cob/object->cob-id :sdo-tx 5) ;=> [:ok 0x585]

;; a heartbeat announcing Operational state
(nmt/encode-heartbeat {:state :operational}) ;=> [:ok [0x05]]
```

| namespace | |
|---|---|
| `canopen.cob-id` | `pack-cob-id`/`unpack-cob-id` (11-bit CAN ID), the predefined connection set, `object->cob-id`/`cob-id->object` |
| `canopen.nmt` | `encode-command`/`decode-command` (Start/Stop/Enter-Pre-Operational/Reset-Node/Reset-Communication), `encode-heartbeat`/`decode-heartbeat`, `boot-up?` |
| `canopen.sdo` | expedited download/upload request+response, segmented download/upload with toggle bit, `check-toggle`, abort |
| `canopen.pdo` | `pack-mapping-entry`/`unpack-mapping-entry` (index:subindex:length-bits), `pack-fields`/`unpack-fields` (contiguous LSB-first bit packing of PDO data) |
| `canopen.emcy` | `encode`/`decode`, error-code classification, error-register bit flags |

Bytes are `Sequential` collections of ints in 0..255, in and out. Errors
are `[:error reason ...]` tuples, never thrown; success is `[:ok value]`.

## Endianness

**Little-endian, throughout every multi-byte CANopen field** — the
Object Dictionary index in an SDO frame, the segmented-transfer size, the
abort code, the PDO mapping entry's *bytes-on-the-wire* (though the
32-bit *value itself* is composed big-endian-within-the-word: index in
the high 16 bits — see `canopen.pdo`'s docstring for that distinction).
This is the same direction as EtherCAT (see `org-ethercat`) and the
opposite of PROFINET (see `com-profibus-profinet`) — verified for this
library against CANopenNode's struct layouts (`301/CO_SDOserver.h`) and
python-canopen's explicit `struct.pack('<...')` format strings, both of
which are unambiguous about byte order in a way a written description
alone can silently get backwards.

## Three details that are usually got wrong

**SYNC and EMCY share function code `0001` but are addressed
differently.** SYNC is a pure broadcast fixed at COB-ID `0x080` (its
node-id field is always 0 — CANopen node-ids start at 1, so this is
unambiguous). EMCY uses the *same* function code but *is* node-addressed,
`0x081`..`0x0FF`. An implementation that assumes "same function code
means same addressing rule" derives a wrong node-id the moment it tries
to interpret `0x080` itself as an EMCY frame — `canopen.cob-id` gives
this exact case its own test
(`sync-and-emcy-share-function-code-but-differ-in-addressing`).

**The SDO command-specifier byte's field widths change between frame
kinds.** The Initiate Download/Upload frame's `n` (unused-byte count) is
2 bits wide (max 4 data bytes fit); the Segment frame's `n` is 3 bits
wide (max 7 data bytes fit) and sits at a different bit offset. Treating
both as "the same n field" misdecodes the toggle bit's position.

**A repeated toggle bit is a protocol violation, not a retransmit.**
`canopen.sdo/check-toggle` treats `[:error :canopen/sdo-toggle-mismatch
...]` as the answer whenever the received toggle does not match what the
session expects next — including a faulty peer that resends the *same*
toggle instead of alternating. This is deliberately NOT folded into
"maybe it's a duplicate, ignore it": CANopen defines the toggle as
strictly alternating, and this library reports the deviation rather than
guessing at recovery.

## Errors

`:canopen/function-code-out-of-range`, `:canopen/node-id-out-of-range`,
`:canopen/cob-id-out-of-range`, `:canopen/unknown-object`,
`:canopen/cob-id-not-node-addressed`, `:canopen/unknown-function-code`,
`:canopen/unknown-nmt-command`, `:canopen/unknown-nmt-command-specifier`,
`:canopen/nmt-command-wrong-length`, `:canopen/unknown-nmt-state`,
`:canopen/unknown-nmt-state-byte`, `:canopen/heartbeat-wrong-length`,
`:canopen/index-out-of-range`, `:canopen/subindex-out-of-range`,
`:canopen/expedited-data-too-long`, `:canopen/sdo-frame-wrong-length`,
`:canopen/unexpected-command-specifier`, `:canopen/sdo-segment-too-long`,
`:canopen/sdo-toggle-not-a-bit`, **`:canopen/sdo-toggle-mismatch`**,
`:canopen/unknown-abort-code`, `:canopen/length-bits-out-of-range`,
`:canopen/mapping-entry-out-of-range`,
`:canopen/pdo-mapping-value-count-mismatch`,
`:canopen/pdo-value-does-not-fit-width`,
`:canopen/pdo-mapping-exceeds-frame`, `:canopen/pdo-data-too-short`,
`:canopen/emcy-error-code-out-of-range`,
`:canopen/emcy-error-register-out-of-range`,
`:canopen/emcy-manufacturer-data-too-long`,
`:canopen/emcy-frame-wrong-length`. **Those keywords are contract.**

## Verify

```sh
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk  # ClojureScript
```

Real counts as run for this README: **40 tests, 26110 assertions, 0
failures, 0 errors** on the JVM. `pack-unpack-round-trip-full-11-bit-space`
is an *exhaustive* sweep — all 2048 possible COB-ID values (16 function
codes × 128 node-ids), not a sample. `mapping-entry-round-trip-sweep` and
`bit-packing-round-trip-sweep` are randomised (2000 and 3000 iterations
respectively) over the full 32-bit mapping-entry space and randomly-sized
bitfield layouts.

**What is cited from public documentation, not the paywalled CiA 301
text:** the COB-ID/predefined-connection-set bit layout and base values,
the NMT command-specifier and state byte values, the SDO
command-specifier bit layout (ccs/scs, e/s/n, t/c), the PDO
mapping-entry field layout, and the EMCY error-code-class/error-register
tables. All cross-checked against CANopenNode (`301/CO_NMT_Heartbeat.h`,
`301/CO_SDOserver.h`, `301/CO_Emergency.h`), python-canopen
(`canopen/nmt.py`, `canopen/sdo/`, `canopen/emcy.py`), and Wireshark's
`packet-canopen.c` dissector. **What is `;; constructed, not a published
spec vector`:** every concrete worked byte example in the test suite
(the SDO expedited-write examples, the PDO mapping-entry and bit-packing
examples, the EMCY example) — there is no worked byte-for-byte frame
example available outside CiA 301's own paywalled text, so these are
hand-derived from the field layout above and checked by hand arithmetic
in the test file's own comments, not copied from the standard.

## A trap this library's own suite fell into

`canopen.pdo/pack-mapping-entry`'s u32 composition (`bit-or` of three
shifted fields) returned a **negative host number under ClojureScript**
whenever `:index` had its own top bit set (`>= 0x8000`, making the packed
word's bit 31 come out set too) — correct bit pattern, wrong sign,
because ClojureScript's bitwise operators are 32-bit *signed* (JS
semantics), unlike Clojure's, which promote to 64-bit `Long` and never
flip sign for a value this small. `unpack-mapping-entry`'s
`unsigned-bit-shift-right`/`bit-and` field extraction was already
sign-agnostic and worked fine — but its *entry range check*,
`(<= 0 entry 0xFFFFFFFF)`, rejected the negative representation outright,
even though it was a perfectly valid mapping entry. `kbb -M:test`
passed clean; only `kbb --backend sci .../verify-cljs.cljk` caught it, failing
`mapping-entry-round-trip-sweep` on roughly half its 2000 random 32-bit
samples (every one with the top bit set). Fixed by normalising both the
packed output and the unpacked input with `unsigned-bit-shift-right ...
0` — see the docstrings on both functions. The identical shape of bug
(a full 32-bit field reconstructed via `bit-shift-left`/`bit-or` rather
than extracted from one) was also caught and fixed the same way in
`org-ethercat`'s `rd-u32le` (Logical Address) and
`com-profibus-profinet`'s `rd-u32be` (DCP Xid) while building those two
sibling libraries — this is why `org-modbus`'s README calls the
"JVM green, ClojureScript catches it" pattern out explicitly, and why
every one of these three libraries' `deps.edn`/CI story keeps both
runners.

## Discrimination check

`canopen.sdo/check-toggle`'s toggle-mismatch detection was verified to
actually discriminate, not just "fail somehow": a passing negative test
(`negative-sdo-toggle-mismatch`) constructs a session where the first
segment's toggle (0) is accepted and the expected next toggle becomes 1,
then feeds a second segment whose toggle is *still* 0 (a faulty peer
repeating instead of alternating). The test asserts the SPECIFIC returned
reason is `:canopen/sdo-toggle-mismatch`, not merely `:error`. To confirm
this assertion is load-bearing rather than dead code, `check-toggle`'s
comparison `(= expected toggle)` was temporarily changed to the constant
`true` (always "matches"), and `kbb -M:test` re-run: exactly
`negative-sdo-toggle-mismatch` failed (expected `:error
:canopen/sdo-toggle-mismatch`, got `:ok 0` — the corrupted toggle was
silently accepted as valid), while all 39 other tests still passed. The
change was reverted and the full suite re-run clean (26110/26110
assertions passing) before publishing.

## Not here

**LSS (Layer Setting Services, CiA 305)** — dynamic node-id/bit-rate
configuration. Nothing in this workspace has needed it yet.

**CiA 402 (drives and motion control) or any other device profile.**
This library implements CiA 301's communication layer only; the meaning
of any particular Object Dictionary index (e.g. 0x6040 Controlword) is a
device-profile concern this library does not encode. The 0x6040 example
in the SDO test suite uses that index's well-known byte pattern purely
as a recognisable 2-byte payload, not as a claim of CiA 402 support.

**PDO Communication Parameter objects (0x1400-0x1403/0x1800-0x1803)** —
inhibit time, event timer, transmission type. `canopen.pdo` handles the
Mapping Parameter (which OD entries occupy a PDO and at what bit
offsets) and the data bit-packing itself, not the parameters that decide
*when* a PDO is sent.

**LSS, node-guarding (the pre-heartbeat, deprecated error-control
protocol), and RTR-triggered PDOs** — all legacy or narrow-use corners
CiA 301 still technically defines but which no CANopen stack checked
during development actively documents using.
