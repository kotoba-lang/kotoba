# kotoba-lang/org-threadgroup-thread

**Thread's (Thread Group, threadgroup.org) 6LoWPAN adaptation layer — RFC
6282 IPHC header compression, RFC 4944 fragmentation and mesh addressing
— in portable `.cljc`.**

## What this is not

A codec, not a stack. There is no radio, no MLE (Mesh Link Establishment),
no commissioning, no border router, no full IPv6 stack, no reassembly
buffer (fragment headers are encoded/decoded; *holding* fragments until a
datagram is complete is a stateful concern this library deliberately
leaves to a caller — see "Not here"), and no security. Nothing here opens
a socket or spawns a thread. It turns Clojure maps into byte sequences and
back, and reports malformed input as a named `[:error reason ...]` —
never a thrown exception, never silent success.

## Surface

```clojure
(require '[thread.dispatch :as dispatch]
         '[thread.frag :as frag]
         '[thread.mesh :as mesh]
         '[thread.iphc :as iphc])

(dispatch/classify first-byte)
;=> [:ok :iphc] | [:ok :mesh] | [:ok :frag1] | ... | [:error :thread.dispatch/reserved b]

(iphc/encode {:tf :elided :nh :inline :next-header 17 :hlim :hop-64
              :sac? false :sam 0 :src-addr link-local-addr
              :dac? false :m? false :dam 0 :dst-addr link-local-addr
              :payload udp-bytes})
;=> [:ok bytes]

(iphc/decode bytes {})
;=> [:ok {:hop-limit 64 :next-header 17 :src-addr [...] :dst-addr [...] :payload [...]}]
```

| namespace | scope |
|---|---|
| `thread.dispatch` | The 6LoWPAN dispatch byte — which header shape follows (RFC 4944 §5.1 + RFC 6282's IPHC dispatch) |
| `thread.iphc` | LOWPAN_IPHC (RFC 6282) — TF/NH/HLIM/CID bitfields, stateless and stateful (context-based) unicast address compression, stateless multicast address compression |
| `thread.frag` | FRAG1/FRAGN fragmentation headers (RFC 4944 §5.3) |
| `thread.mesh` | Mesh Addressing header (RFC 4944 §5.2) — originator/final addresses, hop count, the Deep Hops Left extension |

IPv6 addresses are 16-byte `Sequential` collections of ints in 0..255,
**big-endian** — the opposite convention from the little-endian IEEE
802.15.4 MAC frame this payload rides inside on the wire. Getting this
backwards is the kind of bug this workspace's `org-modbus`/
`org-lora-alliance-lorawan` READMEs warn about by name for their own
protocols' byte orders; Thread has both orders present in the same stack,
one layer apart, which is worse.

## The shared 802.15.4 layer — used, and how

**This repository does not re-derive the IEEE 802.15.4 MAC frame.** It
depends on `kotoba-lang/org-csa-iot-zigbee`'s `ieee802154.mac` (a real git
dependency in `deps.edn`, pinned to a commit on that repo's default
branch, verified reachable with `gh api .../commits/main --jq .sha`
before pinning) for it, because that repository built the MAC layer once
and correctly, and Zigbee and Thread both actually put the same MAC frame
shape on the air. `test/thread/integration_test.cljk` proves this is real
rather than aspirational: it builds an `thread.iphc`-compressed payload,
classifies its dispatch byte, wraps it in a real `ieee802154.mac/encode`
frame, and decodes the whole thing back — end to end, on both the JVM and
under nbb (the git dependency has to actually resolve and run under nbb
for the ClojureScript suite to pass at all).

**Matter (`kotoba-lang/org-csa-iot-matter`) does not depend on this
layer.** Matter's message framing (session/message counters, exchange
IDs, TLV payload) is transport-independent — it rides over BLE, Wi-Fi/IP,
or Thread without ever touching an 802.15.4 MAC frame directly in its own
specified scope — so wiring a dependency there would be decorative, not
load-bearing.

## Provenance — read this before trusting a byte offset

**RFC 4944 and RFC 6282 are IETF RFCs, freely published, with the kind of
worked byte-level detail (dispatch patterns, header bit layouts, the
Traffic-Class/Flow-Label packing tables, the address-compression mode
tables) that a paywalled standard does not offer.** This is the
highest-confidence provenance of the three repositories built alongside
this one — every dispatch pattern, fragmentation header field, and IPHC
bitfield here is reconstructed from RFC text recalled directly, not from
a third-party dissector. **It is still reconstructed from memory, not
copy-verified against the RFC text in this session, so every concrete
byte sequence in this library's tests is still marked `;; constructed,
not a published spec vector`.**

**Least confident value in this repository**: `thread.mesh`'s `V`/`F` bit
polarity (which value, 0 or 1, selects the 16-bit vs. 64-bit address
form). The Mesh Addressing header's *existence*, byte layout, and Deep
Hops Left extension are well-attested; this one bit's specific polarity
is this library's own documented choice (`v? true`/`f? true` = 16-bit
short), stated explicitly in `thread.mesh`'s namespace docstring so it
can be checked against a real capture and flipped in one place if wrong.

## The address-compression scope line

RFC 6282 §3.2.3 has a context-based (stateful, `DAC=1`) multicast
compression form this library does not implement — `encode`/`decode`
return `[:error :thread.iphc/multicast-context-compression-not-
implemented]` for it rather than silently mishandling the bytes. Every
other combination of stateless/stateful × unicast/multicast × the four
address modes is implemented and swept by
`thread.iphc-test/stateless-unicast-sam-dam-sweep`,
`stateful-context-sweep`, and `multicast-dam-sweep`.

`encode` **refuses to compress an address it cannot losslessly
reconstruct.** Every address-packing function checks the requested mode
against the address's actual bytes and returns
`:thread.iphc/prefix-mismatch` or `:thread.iphc/address-not-elidable`
rather than silently truncating a 128-bit address that does not actually
match the elided pattern the caller claimed.

## Errors

Returned, never thrown. Reasons are namespaced keywords —
`:thread.dispatch/reserved`, `:thread.frag/not-frag1-dispatch`,
`:thread.frag/datagram-size-out-of-range`, `:thread.mesh/not-mesh-
dispatch`, `:thread.mesh/hops-left-out-of-range`,
`:thread.iphc/reserved-tf-mode`, `:thread.iphc/prefix-mismatch`,
`:thread.iphc/address-not-elidable`,
`:thread.iphc/multicast-context-compression-not-implemented`, and so on.
Every rejection test asserts the specific reason keyword, not merely that
*some* error came back.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

`thread.mesh`'s 64-bit addresses use `quot`/`mod`/`+'`/`*'` rather than
`bit-shift`, the same pattern `org-csa-iot-zigbee` documents for the same
reason (BigInt rejects bit-ops outright on the JVM; ClojureScript's
32-bit signed semantics silently corrupt them). `thread.iphc`'s Traffic
Class/Flow Label packing chains several `bit-shift-left`/`bit-or`
combinations whose intermediate byte values this library keeps
individually masked to 8 bits specifically so no partial computation ever
crosses the 31-bit boundary where ClojureScript's signed bitwise
operators diverge from the JVM's — the ClojureScript run is what actually
proves that discipline held, not an assumption about it.

Round-trip sweeps: all four TF modes, all four HLIM modes, the
`{stateless, stateful} × {mode 0,1,2,3}` unicast address grid, and all
four stateless multicast DAM forms (`thread.iphc-test`); the full 256-byte
range of the dispatch classifier (`thread.dispatch-test/sweep-full-byte-
range-partitions`); the 14-vs-15 Deep Hops Left boundary (`thread.mesh-
test/hops-left-boundary-14-vs-15`).

## Not here

**Reassembly.** `thread.frag` encodes/decodes individual FRAG1/FRAGN
headers; holding out-of-order fragments until a datagram is complete,
timing out incomplete ones, and matching fragments by `datagram-tag` +
source address across possibly-interleaved datagrams is stateful
session-management the caller owns, not a pure codec's job.

**LOWPAN_NHC** (RFC 6282 §4 — the mechanism that compresses the *next*
header, most commonly UDP, when `thread.iphc`'s `NH` bit is 1). When
`:nh :elided`, `decode` hands back the remaining bytes as `:payload`
undecoded; a caller that needs UDP port/checksum compression handles the
NHC dispatch byte itself.

**RFC 6282 §3.2.3's stateful (context-based) multicast compression** —
see 'The address-compression scope line' above.

**Full IPv6.** This library compresses/decompresses the fields IPHC
elides (version, traffic class, flow label, next header, hop limit,
addresses); it does not parse or validate an IPv6 extension header chain
or payload.

**MLE, address query, Thread's routing/leader-election protocol.** All
out of scope for a link-layer/adaptation-layer codec.
