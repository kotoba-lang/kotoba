# kotoba-lang/org-ietf-rtp

**RTP and RTCP — RFC 3550 — in portable `.cljc`, with no dependencies.**

The 12-byte RTP fixed header (version/padding/extension/CSRC-count, marker/
payload-type, sequence number, timestamp, SSRC), the CSRC list, header
extensions and padding; and the five RTCP packet types (SR 200, RR 201,
SDES 202, BYE 203, APP 204) as compound packets, including the report-block
layout (fraction lost, 24-bit signed cumulative loss, extended highest
sequence number, jitter, LSR, DLSR). The sequence-number wrap/reordering
state machine and the interarrival jitter estimator from RFC 3550's own
Appendix A ("Algorithms for RTP header validation and jitter estimation")
are reimplemented as pure functions rather than left as an exercise.

## What this is not

A media stack. There is no transport (no UDP/TCP socket code — this codec
consumes and produces byte vectors, nothing more), no SRTP (RFC 3711 is a
separate protocol and a separate repository's job), no jitter *buffer*
(this library computes the jitter *estimate* the RFC defines, not a
playout-delay scheduler that uses it), no payload format (RFC 3551/RFC
6184/etc — how audio/video samples are packed into the RTP payload bytes
— is out of scope; `:payload` here is an opaque byte vector), and no RTCP
transmission-interval/bandwidth-limiting logic (RFC 3550 §6.2's "don't
flood the network with RTCP" timer algorithm). It does not negotiate
sessions — see `org-ietf-sip` for that, and see "SDP" below for what
connects the two.

## Surface

```clojure
(require '[rtp.header :as h] '[rtp.rtcp :as rtcp] '[rtp.seq :as s])

;; RTP
(def bs (h/encode {:payload-type 0 :sequence-number 100 :timestamp 12345
                    :ssrc 0xdeadbeef :payload [1 2 3 4]}))
(h/decode bs)
;=> {:version 2 :marker? false :payload-type 0 :sequence-number 100 ...}

;; RTCP — a compound packet, as it actually goes on the wire
(def compound
  (rtcp/encode-compound
    [{:type :sr :ssrc 1 :ntp-sec 0 :ntp-frac 0 :rtp-timestamp 0
      :packet-count 10 :octet-count 1500 :reports []}
     {:type :sdes :chunks [{:ssrc 1 :items [{:type :cname :text "a@b.com"}]}]}]))
(rtcp/decode-all compound)

;; sequence-number wraparound + loss accounting (RFC 3550 Appendix A.1/A.3)
(def track (reduce s/update-seq nil [1 2 3 5 7]))
(s/loss-stats track)
;=> {:expected 6 :lost 2 :fraction-lost 85 :extended-max 7}

;; jitter estimator (Appendix A.8)
(-> nil (s/update-jitter 1000 0) (s/update-jitter 2010 1000) s/jitter-estimate)
```

| namespace | |
|---|---|
| `rtp.header` | `encode` `decode` — the 12-byte fixed header, CSRC list, extension, padding |
| `rtp.rtcp` | `encode-one` `decode-one` `encode-compound` `decode-all`, plus per-type `encode-sr`/`encode-rr`/`encode-sdes`/`encode-bye`/`encode-app` and `encode-report-block`/`decode-report-block` |
| `rtp.seq` | `update-seq` `new-source` `loss-stats` `advance-interval` `update-jitter` `jitter-estimate` `seq-delta` `seq-more-recent?` — Appendix A as pure `(state, input) -> state` functions |

Bytes are `Sequential` collections of ints in 0..255, in and out — the same
convention `modbus.pdu` in this workspace uses.

## Three details that are usually got wrong

**RTCP's `length` field is 32-bit words minus one, including the header —
never a byte count, and never the body alone.** `total-bytes = 4 * (length +
1)`. Reading it as "body length in bytes" desyncs every packet after the
first one in a compound packet.

**The 24-bit cumulative-lost field is signed.** A source that has received
*more* packets than it expected (heavy duplication, or a receiver that
double-counted) reports negative loss. Reading those three bytes as unsigned
turns `-1` into `16777215`, which is exactly what happened the one time this
library's own report-block sign extension was deliberately broken to check
the test suite catches it (see "Discrimination proof" below).

**`fraction_lost` can compute to 256, one past its 8-bit field, at exactly
100% loss in the reporting interval.** RFC 3550's own pseudocode
(`(lost_interval << 8) / expected_interval`) has an explicit `<= 0` clamp on
the low end but nothing on the high end. The naive "just mask it" fix
(`bit-and 0xFF`) turns total loss into `0` on the wire — indistinguishable
from *zero* loss, which is a worse bug than not clamping at all.
`rtp.seq/loss-stats` clamps to `255` instead.

## SDP — checked, not present

Before writing anything here, this workspace's repo index
(`kbb --backend sci scripts/repo-search.cljk sdp`) was searched for an existing Session
Description Protocol (RFC 4566) implementation, since SDP is what actually
carries the payload-type ↔ codec mapping, port numbers and RTP/RTCP
multiplexing this library assumes was negotiated out-of-band. Three repos
matched on the term ("rtc", "webrtc", "org-w3-webrtc-signaling") but none of
their checked-out READMEs describe SDP parsing, and a source-file search
inside each (`*sdp*`, `*sip*`, `*rtp*`) found nothing. **SDP does not exist
in this workspace yet.** This is a gap, not a half-implementation stitched
in here: an RTP/RTCP codec and an SDP codec are different RFCs with
different grammars (SDP is closer to SIP's text-header style than to RTP's
binary layout), and inlining a partial SDP parser into an RTP library would
misattribute it under the wrong protocol's name.

## Design notes

- **Pure data, no IO.** No sockets, no threads, no clocks read internally —
  `rtp.seq/update-jitter` takes `arrival-timestamp` as an argument rather
  than calling a clock, so the same arithmetic is testable and portable to
  every `.cljc` host this workspace runs on (JVM, browser, nbb).
- **`rtp.seq`'s state machine is the RFC's own struct-mutating C code,
  translated to `(state, input) -> new-state`.** `new-source` corresponds to
  the probation-priming glue code Appendix A.1 describes around
  `update_seq`/`init_seq`, not `init_seq` itself — conflating the two (as an
  earlier draft of this library did) means a mid-stream sequence-number
  jump silently gets treated as a brand-new, unvalidated source instead of
  the RFC's actual "hold pending confirmation via `bad_seq`" behaviour.
- **`fraction-lost` is Appendix A.3's *windowed* metric; `:lost` is
  cumulative since the stream began.** Both live in the same RTCP report
  block on the wire (RFC 3550 §6.4.1) but answer different questions —
  `advance-interval` resets the window `fraction-lost` reads from without
  touching the running total `:lost` reads from.

## Test vectors

`test/rtp/header_test.cljk`'s `constructed-frame` is hand-built and labelled
`;; constructed, not a published spec vector` — RFC 3550 §5.1 documents the
*bit layout* of the fixed header but, unlike RFC 3261 §24 for SIP, does not
publish a worked numeric example packet to cite. Every other test vector
(RTCP packets, sequence-number sequences, jitter inputs) is likewise
constructed and derived by running this library's own implementation of the
cited algorithm — RFC 3550 Appendix A's pseudocode is precise enough that a
correct translation's output is independently checkable by hand (see the
comments beside `loss-stats-with-loss` and `jitter-tracks-known-single-step`
in `test/rtp/seq_test.cljk` for worked-by-hand examples), which is a
different and stronger claim than "matches a number I made up."

## Discrimination proof

To confirm the negative tests actually discriminate (not just "fail
somehow"), `rtp.rtcp/decode-report-block`'s 24-bit sign extension was
deliberately removed — `cumulative-lost` decoded unsigned instead of
sign-extended — and the full suite re-run. Seven tests failed, every one on
a specific negative `cumulative-lost` value being decoded back as its
unsigned two's-complement equivalent (`-1` → `16777215`, `-2` → `16777214`,
`-8388608` → `8388608`, `-12345` → `16764871`), not on an unrelated
assertion or a crash. The sign extension was then restored and the full
suite (52 `deftest`s, 1770 assertions) passed again with `0 failures, 0
errors`.
