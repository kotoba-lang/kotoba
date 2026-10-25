# kotoba-lang/com-profibus-profinet

**PROFINET (PROFIBUS & PROFINET International, profibus.com) — the RT
frame layer's FrameID classification, the cyclic-data APDU trailer
(Cycle Counter / Data Status / Transfer Status) and IOxS status bytes,
and a complete DCP (Discovery and Configuration Protocol) codec — in
portable `.cljc`, with no dependencies.**

## What this is not

**A PROFINET IO controller or device stack.** No AR (Application
Relationship) establishment, no connect/parameterize/data-exchange state
machine, no GSDML parsing, no IRT (isochronous real-time) time-scheduled
transmission, no diagnosis-alarm handling beyond the FrameID
classification that tells you an alarm frame arrived. This library packs
and unpacks the wire bytes; the controller/device protocol built on top
of them is not here.

**Real-time scheduling.** RT_CLASS_3 (IRT) achieves determinism through
switch-level time-scheduled slots configured by engineering tools this
library does not implement. `profinet.rt`'s FrameID range table can tell
you a frame *claims* to be IRT; it says nothing about the scheduling
that makes that claim true.

**A network interface.** No raw sockets, no NIC driver binding (RT
traffic bypasses the normal IP stack — real controllers typically need a
driver capable of that), no threads, no IO.

**A conformance certification.** This is not a PROFINET IO conformance
test suite. The PROFINET IO specification is a paywalled PROFIBUS &
PROFINET International (profibus.com) membership document; every
structural claim in this library is cross-checked against Wireshark's
dissectors and an open-source PROFINET device stack (see "Where this
comes from" below), not against the standard's own text.

## Surface

```clojure
(require '[profinet.rt :as rt] '[profinet.dcp :as dcp] '[profinet.ethernet :as eth])

;; classify a captured FrameID
(rt/classify-frame-id 0xFEFE) ;=> :dcp-identify-request

;; a multicast DCP Identify request asking for 'all' blocks
(dcp/encode-pdu {:service-id :identify :service-type :request :xid 1
                  :blocks [{:option :all :suboption :all :value []}]})
;=> [:ok [0x05 0x00 0x00 0x00 0x00 0x01 0x00 0x00 0x00 0x04 0xFF 0xFF 0x00 0x00]]

;; the Data Status byte for "running, data valid"
(rt/pack-data-status #{:state :data-valid}) ;=> 5
```

| namespace | |
|---|---|
| `profinet.rt` | `classify-frame-id` (the full range table), `encode-frame-id`/`decode-frame-id`, `pack-data-status`/`unpack-data-status`, `encode-trailer`/`decode-trailer` (Cycle Counter/Data Status/Transfer Status), `pack-ioxs`/`unpack-ioxs` (IOPS/IOCS byte), `encode-cyclic-data`/`decode-cyclic-data` |
| `profinet.dcp` | `encode-pdu`/`decode-pdu` (full DCP header), `encode-block`/`decode-block`/`encode-blocks`/`decode-blocks` (TLV, with the odd-length pad byte), the ServiceID/ServiceType/Option/Suboption tables, `frame-id-for-service` |
| `profinet.ethernet` | the raw-Ethernet L2 envelope (dst/src MAC, optional 802.1Q, EtherType `0x8892`, FrameID) |

Bytes are `Sequential` collections of ints in 0..255, in and out. Errors
are `[:error reason ...]` tuples, never thrown; success is `[:ok value]`.

## Endianness

**Big-endian, throughout — the opposite of EtherCAT and CANopen.**
FrameID, DCP's Xid/ResponseDelay/DCPDataLength/DCPBlockLength, and Cycle
Counter are all most-significant-byte-first, matching general Ethernet/
IEEE 802.3 convention. See `org-ethercat`'s `ethercat.frame` and
`org-can-cia-canopen`'s `canopen.sdo` docstrings, each of which calls out
their own little-endian convention explicitly for the same reason this
one calls out big-endian: three fieldbuses in this workspace, three
different answers to "which byte goes first", verified for this library
against Wireshark's `packet-pn-rt.c`/`packet-pn-dcp.c` field definitions
and rt-labs' p-net (`github.com/rtlabs-com/p-net`) struct layouts, both
unambiguous about byte order in a way a written description alone can
silently get backwards.

## Three details that are usually got wrong

**A DCP TLV block's pad byte is conditional on `DCPBlockLength`'s
parity, not fixed.** Every block is padded so the *next* block starts at
an even offset from the start of the PDU's data — but the pad byte only
exists when `DCPBlockLength` is odd. A decoder that always skips a pad
byte reads one byte early on an even-length block (silently consuming
the first byte of an unrelated block's Option field); a decoder that
never skips one desyncs after the first odd-length block. `decode-block`
returns an explicit `:consumed` count for exactly this reason — the
caller never has to re-derive "was there a pad byte" itself.

**The Read-Write command asymmetry EtherCAT's working counter has
(`org-ethercat`) has a structural cousin here: Option/Suboption
numbering is not globally unique — it is only meaningful relative to its
Option.** Suboption `0x01` means `MACAddress` under Option `0x01` (IP)
but `DeviceVendor` under Option `0x02` (Device Properties). `decode-block`
resolves the suboption name only after resolving the option, via
`suboptions-by-option` — the same "a byte's meaning depends on context
established earlier in the frame" shape CANopen's SDO command-specifier
byte has (see `org-can-cia-canopen`'s README).

**FrameID is a VALUE range lookup, not a bitfield.** Unlike EtherCAT's
frame header or CANopen's COB-ID, PROFINET's FrameID does not subdivide
into named bit-position sub-fields the way those two do — the entire
16-bit value's magnitude, compared against contiguous ranges, is what
selects frame class. `classify-frame-id` walks an ordered range table
rather than masking bits, which is the correct operation here even
though it looks structurally different from every other "pull a field
out of an integer" function in this workspace's other two fieldbus
libraries.

## Errors

`:profinet/frame-id-out-of-range`, `:profinet/frame-id-wrong-length`,
`:profinet/unknown-data-status-bit`, `:profinet/cycle-counter-out-of-range`,
`:profinet/transfer-status-out-of-range`, `:profinet/trailer-wrong-length`,
`:profinet/ioxs-instance-out-of-range`, `:profinet/ioxs-out-of-range`,
`:profinet/cyclic-data-too-short`, `:profinet/unknown-dcp-option`,
`:profinet/dcp-option-out-of-range`, `:profinet/unknown-dcp-suboption`,
`:profinet/dcp-suboption-out-of-range`, `:profinet/dcp-value-too-long`,
`:profinet/dcp-block-too-short`, `:profinet/dcp-block-truncated`,
`:profinet/dcp-blocks-overran-buffer`, `:profinet/unknown-dcp-service-id`,
`:profinet/unknown-dcp-service-type`, `:profinet/dcp-xid-out-of-range`,
`:profinet/dcp-response-delay-out-of-range`, `:profinet/dcp-pdu-too-short`,
`:profinet/unknown-dcp-service-id-byte`,
`:profinet/unknown-dcp-service-type-byte`,
`:profinet/dcp-pdu-wrong-length`, `:profinet/bad-mac`. **Those keywords
are contract.**

## Verify

```sh
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk  # ClojureScript
```

Real counts as run for this README: **25 tests, 136112 assertions, 0
failures, 0 errors** on the JVM. `frame-id-encode-decode-round-trip-full-16-bit-space`
is an *exhaustive* sweep — all 65536 possible FrameID values.
`data-status-round-trip-full-byte-space` and `ioxs-round-trip-full-byte-space`
are each exhaustive over all 256 byte values.

**What is cited from public documentation, not the paywalled PROFINET IO
specification text:** the FrameID range table, the DCP PDU header layout
(ServiceID/ServiceType/Xid/ResponseDelay/DCPDataLength), the TLV block
layout including the odd-length pad rule, the ServiceID/ServiceType/
Option/Suboption value tables, and the Data Status bit table. All
cross-checked against Wireshark's `packet-pn-rt.c`/`packet-pn-dcp.c`
dissectors and rt-labs' open-source PROFINET device stack p-net
(`github.com/rtlabs-com/p-net`, `src/pf_dcp.c` and
`include/pnet_api.h`). **What is `;; constructed, not a published spec
vector`:** every concrete worked byte example in the test suite (the
Data Status/trailer/IOxS examples, both DCP block examples, the DCP
Identify-request PDU example) — hand-derived from the field layout above
and checked by hand arithmetic in the test file's own comments, not
copied from the standard.

## A trap this library's own suite fell into

`profinet.dcp/rd-u32be` (used to decode DCP's Xid) reconstructed the
32-bit value via `bit-or` of four `bit-shift-left`ed bytes — correct on
the JVM, but under ClojureScript's 32-bit *signed* bitwise operators
(JS semantics), any Xid with its top byte's high bit set (including the
round-trip test's own `0xCAFEBABE`) came back as a **negative host
number** with the correct bit pattern but the wrong sign. `clojure
-M:test` passed clean; only `kbb --backend sci .../verify-cljs.cljk` caught it. Fixed
with a final `unsigned-bit-shift-right ... 0` — see `rd-u32be`'s
docstring. The identical bug shape was independently caught the same
way in `org-can-cia-canopen`'s PDO mapping-entry codec and
`org-ethercat`'s Logical Address decode while building those two
sibling libraries — three separate 32-bit-value reconstructions, three
separate instances of the same ClojureScript-only sign bug, each only
visible by actually running the ClojureScript suite rather than trusting
that a JVM-clean run means the codec is correct everywhere.

## Discrimination check

`profinet.dcp/decode-pdu`'s total-length cross-check was verified to
actually discriminate: a passing negative test
(`negative-dcp-pdu-wrong-length`) truncates a valid PDU by one byte and
asserts the SPECIFIC reason `:profinet/dcp-pdu-wrong-length`, not merely
`:error`. To confirm this is load-bearing, the check
`(not= n (+ 10 data-length))` in `decode-pdu` was temporarily changed to
the constant `false` (never triggers), and `kbb -M:test` re-run:
`negative-dcp-pdu-wrong-length` failed as expected (the truncated PDU
was instead handed to `decode-blocks`, which itself failed with
`:profinet/dcp-block-truncated` — a *different* error than the one the
test asserts, confirming the length cross-check is what the test is
actually pinned to, not incidental downstream validation), while the
other 24 tests still passed. The change was reverted and the full suite
re-run clean (136112/136112 assertions passing) before publishing.

## Not here

**Cyclic data's per-submodule IOCR layout.** `profinet.rt/encode-cyclic-data`
models the simple case (one IO-data block, one trailing IOPS byte, one
trailing IOCS byte). Real PROFINET IOCRs interleave IOPS/IOCS bytes
throughout the data area per a configured module/submodule list — that
configuration model (derived from a GSDML file and an AR's negotiated
`IODataObject`/`IOCS` blocks) is out of scope.

**RTC3 / IRT.** FrameIDs in the `0x8000..0xBBFF` range are classified as
`:cyclic-rt-class-3`, but the time-scheduling that makes IRT
deterministic (switch-level Sync/PLL, DCP's own PTCP announce frames)
is not implemented.

**Alarm PDU contents.** `0xFC01`/`0xFE01` are classified as
`:alarm-high`/`:alarm-low` FrameIDs; the AlarmNotification PDU structure
that rides on them (AlarmType, API, Slot/Subslot, ModuleDiagData) is not
decoded here.

**DHCP-mirrored DCP suboptions (Option `0x03`).** DCP's DHCP option
reuses RFC 2132's option-number space directly rather than defining its
own; `profinet.dcp` recognises the Option byte but does not enumerate
every DHCP suboption by name the way it does for IP/Device Properties/
Control.

**Full IP suite / IP parameter block contents.** `profinet.dcp`
recognises the `:ip-parameter`/`:full-ip-suite` suboptions as named TLV
slots (Option/Suboption byte pair + opaque `:value`), not as a decoded
IP-address-plus-netmask-plus-gateway structure.
