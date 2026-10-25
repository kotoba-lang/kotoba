# kotoba-lang/com-aviation-ia-arinc-664

**A codec for ARINC 664 Part 7 (AFDX) frames — Virtual Link identification
in the destination MAC, Ethernet/IPv4/UDP framing, the 1-byte wrapping
Sequence Number, Bandwidth Allocation Gap predicates, and dual-network
redundancy management — in portable `.cljc`, published by SAE ITC / AEEC
(store: aviation-ia.com).**

## What this is not

This is a *codec and a set of pure predicates*: it packs and unpacks
AFDX frame bytes and models the redundancy-management decision a
receiving End System makes. It is **not** an AFDX switch, not a NIC
driver, has **no IO, no sockets, no clock, no threads**, does not
implement a traffic shaper that actually enforces BAG at transmit time,
does not perform network scheduling or latency analysis, and makes
**no airworthiness or certification claim of any kind**. AFDX carries
flight-critical avionics data; this library is for reasoning about
frame bit patterns and redundancy decisions in a test bench or
simulator, not a validated component of an aircraft data network.

## Provenance — read this before trusting a number here

**This implementation has not seen the paid ARINC 664 Part 7 standard
text.** Everything specific to AFDX (as opposed to the freely published
Ethernet/IPv4/UDP layers underneath it) is reconstructed from publicly
available AFDX overview papers, academic network-calculus/schedulability
research on AFDX, and vendor tutorials — not a citation of the standard's
own wording. Confidence varies by namespace, worst first:

1. **`afdx.vl`** (the `03:00:00:00:HH:LL` destination-MAC-embeds-VL-ID
   convention) — **the single lowest-confidence claim in this library.**
2. **`afdx.frame`**'s claim that the Sequence Number is the LAST octet of
   the UDP payload, inside the datagram.
3. **`afdx.bag`**'s allowed value set (powers of two, 1-128 ms) and
   default jitter tolerance (0.5 ms) — repeated fairly consistently
   across public sources, but still not standard-cited.
4. **`afdx.sequence`**'s wrap rule (255 -> 1, 0 reserved/never
   transmitted) — the most consistently corroborated AFDX-specific claim
   here, and the one the task this library was built against calls out
   by name as the classic trap.
5. **`afdx.redundancy`**'s `:accept-with-gap` classification is this
   library's OWN policy extension, not a spec claim at all — see that
   namespace's docstring.

Everything in `afdx.ethernet`/`afdx.ipv4`/`afdx.udp` rests on freely
published IETF material (Ethernet II framing, RFC 791, RFC 768, RFC
1071) and is cited with confidence.

Every concrete worked value in the test suite that is not an
**exhaustive sweep** is commented `;; constructed, not a published spec
vector`.

## Surface

```clojure
(require '[afdx.vl :as vl] '[afdx.frame :as frame] '[afdx.sequence :as sn]
         '[afdx.bag :as bag] '[afdx.redundancy :as red])

(vl/vl-id->dst-mac 256)
;=> [:ok [3 0 0 0 1 0]]                    ;; VL 256 = 0x0100 -> HH=0x01 LL=0x00

(frame/encode {:vl-id 256 :src-mac [2 0 0 0 0 9]
               :src-ip [10 0 0 1] :dst-ip [239 1 2 3]
               :src-port 1000 :dst-port 2000
               :application-data [0x41 0x42] :sn 1})
;=> [:ok [3 0 0 0 1 0 2 0 0 0 0 9 8 0 69 0 0 31 0 0 0 0 1 17 190 201
;         10 0 0 1 239 1 2 3 3 232 7 208 0 11 182 216 65 66 1]]

(sn/next-sn 255)                            ;=> 1   ;; not 0
(bag/bag->frames-per-second 8)              ;=> 125.0

(def s1 (red/receive red/initial-state {:network :a :sn 1 :received-at-ms 0}))
s1                                          ;=> [{...} :deliver]
(red/receive (first s1) {:network :b :sn 1 :received-at-ms 3})
;=> [{...} :discard-duplicate]              ;; the redundant B-network copy
```

| namespace | |
|---|---|
| `afdx.bytes` | shared byte-vector primitives: `u16be`/`rd-u16be`, `u32be`/`rd-u32be`, `checksum16` (RFC 1071 Internet checksum) |
| `afdx.ethernet` | the Ethernet II header: dst/src MAC + EtherType |
| `afdx.vl` | Virtual Link ID <-> destination MAC (AFDX's lowest-confidence convention — see Provenance) |
| `afdx.ipv4` | IPv4 header (RFC 791), no options, real checksum computed and verified |
| `afdx.udp` | UDP header (RFC 768), real pseudo-header checksum, or disabled per RFC 768's all-zero convention |
| `afdx.frame` | the full AFDX frame: Ethernet + IPv4 + UDP + application data + trailing Sequence Number |
| `afdx.sequence` | the 1-byte SN: `next-sn` (the 255 -> 1 wrap), `steps-forward` (wrap-aware distance in the live 255-value cycle) |
| `afdx.bag` | Bandwidth Allocation Gap as pure predicates over caller-supplied timestamps — no clock, no shaper |
| `afdx.redundancy` | the dual-network (A/B) integrity-check + first-valid-wins state machine, pure |

## The 1-byte Sequence Number's wrap rule — the trap this task brief names directly

The SN wraps **255 -> 1, skipping 0** — not `(mod (inc sn) 256)`, which
would give 255 -> 0. 0 is reserved as a "no frame yet" sentinel and is
never itself transmitted as a real SN. `afdx.sequence/next-sn` handles
both the ordinary increment and the wrap in one rule (`(let [n (inc
sn)] (if (> n 255) 1 n))`); a naive modulo-256 implementation looks
identical for 254 out of every 255 transitions and is wrong exactly once
per cycle, which is precisely the kind of bug that survives casual
testing. **This was demonstrated, not just asserted**: temporarily
replacing `next-sn` with `(mod (inc sn) 256)` (the naive form) makes
`sn-next-sn-over-full-range` fail with
`expected: (= nxt (if (= n 255) 1 (inc n))), actual: (not (= 0 1))` —
caught at exactly SN 255 — and cascades into
`sn-steps-forward-exhaustive` failures for every pair whose path crosses
the wrap. The break was reverted before this repo was published.

Because 0 is excluded from the live cycle, that cycle has **period 255**
(values 1..255), not 256 — `afdx.sequence/steps-forward` computes
wrap-aware forward distance modulo 255, and using modulo 256 there
would silently be off by one for any pair whose path crosses the wrap.

## Errors

`[:error keyword data]`, never thrown: `:afdx/bad-mac`,
`:afdx/frame-too-short`, `:afdx/vl-id-out-of-range`,
`:afdx/not-a-vl-mac`, `:afdx/bad-ip`, `:afdx/ttl-out-of-range`,
`:afdx/not-ipv4`, `:afdx/ip-options-unsupported`,
`:afdx/ipv4-checksum-mismatch`, `:afdx/ipv4-length-mismatch`,
`:afdx/port-out-of-range`, `:afdx/udp-length-mismatch`,
`:afdx/udp-checksum-mismatch`, `:afdx/not-ipv4-ethertype`,
`:afdx/not-udp-protocol`, `:afdx/udp-payload-empty`,
`:afdx/sn-out-of-range`. The test suite asserts the specific keyword,
never just "some error came back".

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

32 tests, 327,126 assertions, on both runtimes. Exhaustive sweeps: all
65,536 possible Virtual Link IDs round-tripped through the MAC-address
codec; all 255 x 255 `(from, to)` pairs of the live Sequence Number
cycle checked against `steps-forward`'s own re-derivation via repeated
`next-sn`; the full 0..255 SN byte range for `next-sn`/`valid-sn?`; and
`checksum16` checked against RFC 1071's own worked example (four words,
checksum `0x220D`) in addition to round-tripping over 50 pseudo-random
buffers.

`afdx.bytes/rd-u32be` — unused by the current frame pipeline (IPv4
addresses stay as 4 separate octets, never a packed 32-bit integer) but
kept as shared infrastructure — is still tested against a value with the
top bit set (`0x80000000`), the same class of value that goes negative
under ClojureScript if `com-aviation-ia-arinc-429`'s `u32` canonicalisation
technique (used here too) were skipped or wrong; an untested corner is
exactly how that bug hides.

## Not here

**A real traffic shaper.** `afdx.bag` only checks whether a caller-supplied
timestamp sequence *would have* conformed to a BAG; it does not enforce
anything at transmit time.

**Per-parameter port/VL assignment tables** (which application uses which
UDP port, on which VL) — those belong to a specific aircraft's network
configuration, same reasoning as `com-aviation-ia-arinc-429` not
hardcoding per-parameter BNR/BCD tables.

**Real network jitter/latency analysis.** `afdx.bag`'s conformance check
is a pure predicate over timestamps a caller already has; it does not
compute worst-case latency bounds the way AFDX network-calculus tooling
does.

## Naming

`com-aviation-ia-arinc-664` is the reverse-DNS of the standard's
publisher (SAE ITC / AEEC, standards sold at aviation-ia.com), matching
`com-aviation-ia-arinc-429`'s naming. `manifest/origin-domains.edn` in
the parent workspace does not currently record an origin for this repo;
this name was chosen rather than looked up, and should follow that file
if it is later updated with an authoritative origin.
