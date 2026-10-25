# kotoba-lang/org-ethercat

**EtherCAT (ETG.1000) — the raw-Ethernet frame header, the addressed
read/write datagram (APRD/APWR/APRW/FPRD/FPWR/FPRW/BRD/BWR/BRW/LRD/LWR/
LRW/ARMW/FRMW), multi-datagram frame chaining, and the working-counter
increment rules as pure functions — in portable `.cljc`, with no
dependencies.**

## What this is not

**An EtherCAT master or slave stack.** No real-time cyclic scheduling, no
distributed-clock synchronisation, no slave state machine (Init/
Pre-Op/Safe-Op/Op via the AL Control/Status registers), no ESI/EtherCAT
Slave Information XML parsing, no FMMU/SyncManager configuration. This
library packs and unpacks the wire bytes of a frame; deciding what
address, command and cadence to send them at is a master implementation
built on top of this codec.

**A real-time scheduler.** EtherCAT's whole selling point is
sub-millisecond cyclic determinism achieved by dedicated master
software talking to a real-time-capable NIC. Nothing about achieving
that determinism lives here.

**A network interface.** No raw sockets, no NIC driver binding
(EtherCAT typically needs one that bypasses the normal OS network stack
entirely — e.g. IgH's `ec_generic`/`ec_e1000e` kernel modules, or SOEM's
raw-socket approach on a non-real-time OS), no threads, no IO.

**A conformance certification.** This is not an ETG.1000/1500
conformance test suite. ETG.1000/1500 are paywalled EtherCAT Technology
Group membership documents; every structural claim in this library is
cross-checked against open-source EtherCAT master implementations (see
"Where this comes from" below), not against the standard's own text.

## Surface

```clojure
(require '[ethercat.frame :as frame] '[ethercat.datagram :as dg]
         '[ethercat.wkc :as wkc] '[ethercat.ethernet :as eth])

;; APRD reading 2 bytes (AL Status) from the slave at position 0
(dg/encode-datagram {:command :aprd :index 1 :adp 0 :ado 0x0130 :data [0 0]})
;=> [:ok [0x01 0x01 0x00 0x00 0x30 0x01 0x02 0x00 0x00 0x00 0x00 0x00 0x00 0x00]]

;; the frame header for a 14-byte datagram
(frame/encode-header {:length 14}) ;=> [:ok [0x0E 0x10]]

;; working counter: a read-write command where only the write succeeded
(wkc/slave-contribution :aprw {:read-ok? false :write-ok? true}) ;=> 2
```

| namespace | |
|---|---|
| `ethercat.frame` | `encode-header`/`decode-header` (11-bit Length + 4-bit Type), `encode-frame`/`decode-frame` (chains multiple datagrams, stamps the More bit automatically) |
| `ethercat.datagram` | `encode-datagram`/`decode-datagram` (all 14 commands, both addressing modes), `pack-position-address`/`unpack-position-address` (auto-increment addressing) |
| `ethercat.wkc` | `slave-contribution`, `expected-wkc`, `classify-single-slave-wkc` — the working-counter arithmetic, as pure functions |
| `ethercat.ethernet` | the raw-Ethernet L2 envelope (dst/src MAC, optional 802.1Q, EtherType `0x88A4`) |

Bytes are `Sequential` collections of ints in 0..255, in and out. Errors
are `[:error reason ...]` tuples, never thrown; success is `[:ok value]`.

## Endianness

**Little-endian, throughout the wire format** — the frame header's
Length/Type word, a datagram's ADP/ADO or 32-bit Logical Address, the
Len/flags word, IRQ, and WKC are all least-significant-byte-first. This
is the same direction as CANopen (see `org-can-cia-canopen`) and the
*opposite* of PROFINET (see `com-profibus-profinet`) — three fieldbuses
built on the same idea (short frames carrying packed integers) that do
not agree on byte order, verified for this library against SOEM's
(`github.com/OpenEtherCATsociety/SOEM`) struct definitions in
`ethercattype.h`, which are unambiguous about wire layout in a way a
written description alone can silently get backwards.

## Three details that are usually got wrong

**Auto-increment addressing counts DOWN, encoded as two's complement —
not up, not signed-magnitude.** To address the Nth slave from the master
(0-indexed), the ADP field carries `(-N) mod 65536`, not `N` itself; each
slave decrements the field by one as the frame passes through and the
one that sees it reach zero is addressed. `pack-position-address`/
`unpack-position-address` isolate this so a caller never has to hand-roll
16-bit two's complement.

**The write half of a read-write command's working counter contribution
is +2, not +1.** A plain read or write command contributes 0 or 1. A
read-write command (APRW/FPRW/BRW/LRW) contributes 0, 1, 2, or 3 — with
the write's success weighted +2 specifically so all four outcomes (both
failed / read only / write only / both succeeded) are distinguishable
from the returned counter value alone, without inspecting the Data
payload. Weighting both halves +1 would make "write only" (1) and "read
only" (1) indistinguishable. See `ethercat.wkc`'s docstring and
`wkc-read-write-command-contribution-is-not-symmetric`.

**Logical addressing (LRD/LWR/LRW) does NOT split its 4-byte Address
field into two 16-bit halves the way every other command does.** APRD/
FPRD/BRD/etc. address bytes 2..5 as ADP(2)+ADO(2); LRD/LWR/LRW treat the
same four bytes as ONE 32-bit Logical Address. `ethercat.datagram`'s
`decode-datagram` deliberately returns EITHER `:adp`/`:ado` OR
`:logical-address` — never both, never neither — so a caller cannot
accidentally read a stale field left over from assuming the wrong shape.

## Errors

`:ethercat/length-out-of-range`, `:ethercat/type-out-of-range`,
`:ethercat/reserved-not-a-bit`, `:ethercat/header-wrong-length`,
`:ethercat/frame-has-no-datagrams`, `:ethercat/frame-too-short`,
`:ethercat/frame-truncated`, `:ethercat/datagram-header-truncated`,
`:ethercat/datagram-truncated`, `:ethercat/unknown-command`,
`:ethercat/index-out-of-range`, `:ethercat/data-too-long`,
`:ethercat/wkc-out-of-range`, `:ethercat/nop-has-no-datagram-payload`,
`:ethercat/device-addressing-requires-adp-ado`,
`:ethercat/adp-out-of-range`, `:ethercat/ado-out-of-range`,
`:ethercat/logical-addressing-requires-logical-address`,
`:ethercat/logical-address-out-of-range`, `:ethercat/position-out-of-range`,
`:ethercat/datagram-too-short`, `:ethercat/unknown-command-byte`,
`:ethercat/datagram-wrong-length`, `:ethercat/nop-has-no-wkc-semantics`,
`:ethercat/bad-mac`. **Those keywords are contract.**

## Verify

```sh
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk  # ClojureScript
```

Real counts as run for this README: **23 tests, 6772 assertions, 0
failures, 0 errors** on the JVM. `header-round-trip-full-length-space-both-reserved-values`
is an *exhaustive* sweep — all 2048 possible Length values × both
reserved-bit values (4096 combinations). `position-address-round-trip-and-worked-examples`
sweeps positions 0..999. `wkc-classify-is-the-inverse-of-contribution`
exhaustively covers all 14 addressed commands × both `read-ok?`/`write-ok?`
booleans.

**What is cited from public documentation, not the paywalled ETG.1000/
1500 text:** the frame header's 11/1/4 bit split, the datagram command
codes (`EC_CMD_*`), the Len/flags word's 11/3/1/1 split, the
auto-increment decrement-to-zero addressing convention, and the
working-counter +1/+1/(+1,+2) increment rule. All cross-checked against
SOEM (`soem/ethercattype.h`, `soem/ethercatmain.c`), IgH EtherCAT Master
(`master/ethernet.h`, `master/datagram.c`), and Wireshark's
`packet-ecatmb.c` dissector, plus the working-counter split specifically
against vendor application notes (Beckhoff InfoSys "Working Counter")
and the etherlab.org FAQ. **What is `;; constructed, not a published
spec vector`:** every concrete worked byte example in the test suite
(the APRD worked example, the position-address examples) — hand-derived
from the field layout above and checked by hand arithmetic in the test
file's own comments, not copied from the standard.

## A trap this library's own suite fell into

`ethercat.datagram/rd-u32le` (used to decode a Logical Address for LRD/
LWR/LRW) reconstructed the 32-bit value via `bit-or` of four
`bit-shift-left`ed bytes — correct on the JVM (Clojure's bitwise
operators promote to 64-bit `Long`), but under ClojureScript, whose
bitwise operators are 32-bit *signed* (JS semantics), any Logical Address
with its top byte's high bit set (>=0x80000000 — half the address space,
including the test suite's own `0xDEADBEEF` worked example) came back as
a **negative host number** with the correct bit pattern but the wrong
sign. `kbb -M:test` passed clean; only
`kbb --backend sci .../verify-cljs.cljk` caught it. Fixed with a final
`unsigned-bit-shift-right ... 0` — see `rd-u32le`'s docstring. The
identical bug shape was independently caught the same way in
`org-can-cia-canopen`'s PDO mapping-entry codec and
`com-profibus-profinet`'s DCP Xid decode while building those two
sibling libraries.

## Discrimination check

`ethercat.wkc/classify-single-slave-wkc`'s command-kind-specific range
check was verified to actually discriminate: a passing negative test
(`negative-wkc-out-of-range-for-command-kind`) feeds a plain read command
(`:aprd`, whose only valid WKC values are 0 or 1) the value 3 and asserts
the SPECIFIC reason `:ethercat/wkc-out-of-range`, not merely `:error`. To
confirm this is load-bearing, the `:read` branch's range check
`(cond (= wkc 0) ... (= wkc 1) ... :else [:error ...])` was temporarily
changed to accept any non-negative integer as valid (returning
`{:read-ok? true :write-ok? nil}` for anything `>= 0`), and `clojure
-M:test` re-run: exactly `negative-wkc-out-of-range-for-command-kind`
failed (expected `:error :ethercat/wkc-out-of-range`, got `:ok
{:read-ok? true :write-ok? nil}` — a WKC value no `:aprd` frame can
actually produce was silently accepted as "read succeeded"), while all
22 other tests still passed. The change was reverted and the full suite
re-run clean before publishing.

## Not here

**Distributed Clocks (DC)** — the `ARMW`/`FRMW` command codes are
implemented as datagram byte-packing (this library can encode/decode
their frames), but the DC synchronisation algorithm itself (drift
compensation, propagation-delay measurement) is not.

**FMMU and SyncManager configuration** — how a slave's `Logical Address`
range maps onto its local physical memory (the mechanism that makes
LRD/LWR/LRW meaningful in practice) is slave-side configuration state,
not a codec detail.

**Mailbox protocols** (CoE — CANopen over EtherCAT, SoE, EoE, FoE, AoE)
— EtherCAT's higher-layer application protocols, several of which reuse
CANopen's SDO shape (see `org-can-cia-canopen`) inside an EtherCAT
mailbox datagram. Out of scope for this library, which stops at the
datagram layer itself.

**ESI (EtherCAT Slave Information) XML** — the vendor-supplied slave
description format. Not a wire protocol, not implemented here.
