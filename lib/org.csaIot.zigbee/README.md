# kotoba-lang/org-csa-iot-zigbee

**The IEEE 802.15.4 MAC frame, and the Zigbee (Connectivity Standards
Alliance, csa-iot.org) NWK and APS headers that ride inside it — in
portable `.cljc`, with no dependencies.**

## What this is not

A codec, not a stack. There is no radio, no PHY, no CSMA-CA, no
association/orphan procedures, no security (AES-CCM* key transport and
frame protection are not implemented — see "Not here"), no ZDP/ZCL cluster
library beyond the bare frame header, and no coordinator/router/end-device
role logic. Nothing here opens a socket, touches a radio, or spawns a
thread. It turns Clojure maps into byte sequences and back, and reports
malformed input as a named `[:error reason ...]` — never a thrown
exception, never silent success on bad input.

## Surface

```clojure
(require '[ieee802154.mac :as mac]
         '[zigbee.nwk :as nwk]
         '[zigbee.aps :as aps])

(mac/encode {:frame-type :data :dest-addr-mode :short :src-addr-mode :short
             :pan-id-compression? true :frame-version :v2006 :seq-num 0x42
             :dest-pan-id 0x1234 :dest-addr 0xBEEF
             :src-pan-id 0x1234 :src-addr 0xCAFE :payload nwk-bytes})
;=> [:ok [0x41 0x88 0x42 0x34 0x12 0xEF 0xBE 0xFE 0xCA ...]]

(mac/decode bytes)
;=> [:ok {:fcf {...} :seq-num 0x42 :dest-pan-id 0x1234 ...}]
;;  | [:error :ieee802154/reserved-frame-type 6]
```

| namespace | scope |
|---|---|
| `ieee802154.mac` | Frame Control Field (frame type, security/pending/ack-request/PAN-ID-compression bits, addressing modes, frame version), sequence number, and the addressing fields whose presence/width the FCF determines |
| `zigbee.nwk` | NWK Frame Control, destination/source 16-bit addresses, radius, sequence number, optional IEEE (EUI-64) addresses, multicast control, AODV-style source-route subframe |
| `zigbee.aps` | APS Frame Control, destination endpoint / group address, cluster ID, profile ID, source endpoint, APS counter — Data, Command and Ack frame types |

Bytes are `Sequential` collections of ints in 0..255, in and out — this
workspace's `org-modbus` convention.

## The addressing-fields trap (`ieee802154.mac`)

Whether a MAC frame carries a Destination PAN ID, a Destination Address (2
or 8 bytes), a Source PAN ID, and a Source Address (2 or 8 bytes) at all is
not fixed by frame type — it is computed from four FCF bits a decoder must
parse *before* it can find the byte offset of anything that follows. This
library's `decode` always parses the FCF first (`addressing-shape`) and
uses that single derivation for both `encode` and `decode`, so the two
paths can never disagree about frame layout — a bug class this repo's test
suite sweeps all 18 `{none,short,extended} × {none,short,extended} ×
{compression on,off}` combinations to catch (`ieee802154.mac-test/
addressing-mode-sweep`).

**PAN ID Compression** (the 2006-era rule — the one Zigbee actually relies
on; 802.15.4e's 2015 revision replaced this with a larger table this
library does not implement): when both addresses are present and the bit
is set, the Source PAN ID is omitted from the wire and understood to equal
the Destination PAN ID.

## Provenance — read this before trusting a byte offset

**IEEE 802.15.4 itself is an IEEE standard, not a freely republished
document; the Zigbee Specification is a CSA member document.** Nothing
here is a spec quotation. The structural knowledge — FCF bit positions,
frame-type/addressing-mode/frame-version code tables, and the Zigbee
NWK/APS field layouts — comes from cross-checking three independent
open-source implementations that publicly agree with each other: Wireshark
(`packet-ieee802154.c`, `packet-zbee-nwk.c`, `packet-zbee-aps.c`), Zephyr's
`subsys/net/l2/ieee802154`, Contiki-NG's `os/net/mac/framer/
frame802154.c`, and `zigpy` (`zigpy/zigbee/apsde.py`,
`zigpy/zigbee/nwk.py`). **Every concrete byte sequence in this library's
tests is `;; constructed, not a published spec vector`** — none is a
worked example lifted from the IEEE/CSA text, because that text was not
consulted.

**Least confident value**: `zigbee.nwk`'s Multicast Control byte split
(Mode:2 / NonmemberRadius:3 / MaxNonmemberRadius:3). The field's presence
and byte position are corroborated by all three sources above; the exact
three-way bit split inside the byte is reconstructed from a single source
(`packet-zbee-nwk.c`'s bitmask table) and is the one thing in this repo
furthest from independent corroboration.

## Errors

Returned, never thrown. Every reason is a namespaced keyword naming the
specific rule that failed — `:ieee802154/reserved-frame-type`,
`:ieee802154/reserved-addressing-mode`, `:ieee802154/reserved-frame-
version`, `:ieee802154/sequence-number-out-of-range`, `:ieee802154/frame-
too-short`, `:zigbee.nwk/reserved-frame-type`, `:zigbee.nwk/relay-index-
out-of-range`, `:zigbee.aps/endpoint-out-of-range`, and so on (see each
namespace's docstring). Every test that exercises a rejection asserts the
specific reason keyword, not merely that *some* error came back — "it
failed somehow" would pass on a different bug.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Bitwise arithmetic here is confined to 16 bits (the FCF) and the 8-bit
subfields inside it — well within the range where the JVM's 64-bit signed
`bit-*` operations and ClojureScript's 32-bit signed ones agree — **except**
the 64-bit extended (EUI-64) addresses, which is exactly why `u64le`/
`rd-u64le` in `ieee802154.mac`/`zigbee.nwk` use `quot`/`mod`/`+'`/`*'`
rather than `bit-shift`, following `org-lora-alliance-lorawan/lorawan.
bytes`'s precedent — and why the ClojureScript run exists as a real gate,
not a formality: an extended address round trip that only ever ran on the
JVM would never have exercised the branch that matters.

## Not here

**AES-CCM\* frame security.** Zigbee's frame protection is built on
AES-128-CCM\*; `kotoba-lang/org-nist-aes` has AES but not yet CCM\* mode
on top of it. Adding it here would mean re-deriving CCM\* from scratch or
blocking on that gap — out of scope for a framing library.

**FCS/MFR trailer.** IEEE 802.15.4's MAC footer (a CRC-16-CCITT frame
check sequence) is commonly computed/verified by radio hardware, not
software; adding an unverified CRC variant here risked getting the
polynomial/init wrong with no way to check it against a real device.

**ZCL (Zigbee Cluster Library).** Endpoint/cluster/profile addressing
(`zigbee.aps`) is in scope; the ZCL frame format that rides inside an APS
payload, and the cluster-specific command sets, are not — a second layer
of scope this repository's budget did not reach.

**Beacon payload, GTS, superframe structure, association/orphan/
disassociation MAC commands.** 802.15.4 features Zigbee's stack does not
route application data through.
