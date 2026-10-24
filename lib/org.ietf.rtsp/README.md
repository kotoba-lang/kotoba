# kotoba-lang/org-ietf-rtsp

**RTSP 1.0 — [RFC 2326](https://www.rfc-editor.org/rfc/rfc2326) — in
portable `.cljc`, with no dependencies.**

[RFC 7826] defines RTSP 2.0, a substantial revision (TCP-only by
default, different state machine details, new headers). This codec
implements **RFC 2326 (RTSP 1.0)** — the version actually deployed
across the installed base of IP cameras, media servers (Live555,
GStreamer's `rtspsrc`, VLC) and NVRs this workspace is likely to talk
to — and does not claim 2.0 compatibility.

Request/status lines, the eleven methods (`DESCRIBE` `ANNOUNCE`
`GET_PARAMETER` `OPTIONS` `PAUSE` `PLAY` `RECORD` `REDIRECT` `SETUP`
`SET_PARAMETER` `TEARDOWN`), `CSeq`, the `Transport` header's full
parameter grammar (`unicast`/`multicast`, `destination`, `interleaved`,
`append`, `ttl`, `layers`, `port`/`client_port`/`server_port`, `ssrc`,
`mode`), `Session` with `timeout`, and — the one genuinely binary piece
of this text protocol — §10.12's interleaved framing: `$` + one-byte
channel + big-endian 16-bit length, for tunnelling RTP/RTCP through the
same TCP connection as the RTSP messages themselves.

## Surface

```clojure
(require '[rtsp.message :as msg] '[rtsp.bytes :as rb]
         '[rtsp.transport :as tr] '[rtsp.interleaved :as il]
         '[rtsp.stream :as stream])

(msg/decode (rb/str->bytes "OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n"))
;; => {:status :ok :message {:type :request :method "OPTIONS" ...} :consumed 27}

(tr/decode "RTP/AVP/TCP;interleaved=0-1")
;; => [:ok [{:transport-protocol "RTP" :profile "AVP" :lower-transport "TCP"
;;           :interleaved {:from 0 :to 1}}]]

(il/encode {:channel 0 :data [0xDE 0xAD 0xBE 0xEF]})
;; => [0x24 0 0 4 0xDE 0xAD 0xBE 0xEF]

;; decode a mixed stream of RTSP messages and interleaved RTP/RTCP frames
(stream/decode-all stream-bytes)
;; => {:units [{:frame :message ...} {:frame :interleaved :channel 0 :data [...]} ...]
;;     :leftover []}
```

| namespace | |
|---|---|
| `rtsp.message` | `decode` `encode` — request/status line, headers with folding, `Content-Length`-delimited body |
| `rtsp.transport` | `decode` `encode` `parse-spec` — the `Transport` header's parameter grammar |
| `rtsp.session-header` | `decode` `encode` — `Session: <id>[;timeout=<seconds>]` |
| `rtsp.interleaved` | `decode` `encode` — the `$`/channel/length binary frame |
| `rtsp.stream` | `decode-one` `decode-all` — dispatch a persistent connection's bytes to the right decoder |
| `rtsp.bytes` | the one octet↔char conversion this codec needs (see "A bug this library's own suite caught," below) |

Bytes are `vector<int 0..255>`, same convention as `modbus.pdu`/
`rtp.header`. The interleaved frame length is real bit arithmetic
(`bit-and`/`bit-or`/`bit-shift-left`/`unsigned-bit-shift-right`), not a
`DataView` call hidden behind a library.

## No chunked transfer coding — this is RTSP-specific, not borrowed from HTTP

RTSP's own §4.3: *"RTSP does not (at present) support the HTTP/1.1
'chunked' transfer coding and requires the presence of the
Content-Length header field."* And rule 2 of the same section: *"If
this header field is not present, a value of zero is assumed"* — RTSP,
unlike HTTP/1.0, does **not** use connection-close as an implicit body
length. `rtsp.message` reflects both: no chunk-size parsing exists at
all, and a missing `Content-Length` means a zero-length body, never
"read until EOF."

## A bug this library's own suite caught

`rtsp.bytes/str->bytes` originally read `(mapv int s)` — exactly the
idiom this workspace's own `org-modbus` README documents as silently
wrong under ClojureScript (`(seq "...")` yields `Character`s on the JVM,
one-character *strings* in cljs, and `int` on a one-character string is
not a code point). Running this codec's cljs test suite during
development reproduced it directly: `(mapv int "abc")` => `[97 98 99]`
on the JVM, `[0 0 0]` under `nbb`. Fixed with the same
reader-conditional accessor `kotoba.bytes/code-unit-at` uses
(`.charAt`+`int` vs `.charCodeAt`). This is the third time this exact
idiom has produced a wrong-and-plausible answer in this workspace
(`org-modbus`, `org-ietf-websocket`'s `Sec-WebSocket-Accept`, and now
here) — evidence for running the cljs suite as part of the conformance
floor, not a formality bolted on afterward.

## Test vectors — provenance

**[RFC 2326] §10.2's DESCRIBE example and §10.4's SETUP example** are
used for the request/status-line/header shapes and the `Transport`
header values, fetched from `https://www.rfc-editor.org/rfc/rfc2326.txt`
on 2026-08-30. The DESCRIBE example's SDP body **Content-Length is
computed from the reconstructed body bytes in this test suite (363),
not copied from the RFC's own printed value (376)** — the plain-text
refetch and the RFC's original print formatting do not agree
byte-for-byte, so asserting the printed number would be asserting a
value this suite cannot itself reproduce. §12.39's own multi-spec
`Transport` example (`multicast;ttl=127;mode="PLAY",unicast;
client_port=3456-3457;mode="PLAY"`) is used verbatim for the
comma-separated/quoted-mode parsing test. Everything else (interleaved
frame shapes, negative-test fixtures, the mixed-stream test) is
constructed test data exercising the grammar, not spec text.

## Errors

Returned, never thrown. `:reason` keywords: `:rtsp/malformed-request-line`
/ `:rtsp/malformed-status-line`, `:rtsp/malformed-header-line`,
`:rtsp/incomplete-headers` (no blank line yet — ask for more bytes),
`:rtsp/incomplete-body` (carries `:need`/`:have`), `:rtsp/malformed-content-length`,
`:rtsp/missing-content-length` (encode-side: a body with no
`Content-Length` header supplied), `:rtsp/malformed-transport-protocol` /
`:rtsp/malformed-transport-parameter`, `:rtsp/malformed-session-header`,
`:rtsp/interleaved-not-a-frame` / `:rtsp/interleaved-incomplete-header` /
`:rtsp/interleaved-incomplete-payload` / `:rtsp/interleaved-channel-out-of-range`
/ `:rtsp/interleaved-length-out-of-range`.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

## Not here

**Sockets, TLS, and the actual RTSP session state machine** (SETUP →
PLAY → PAUSE → TEARDOWN transitions, aggregate-vs-single-stream control,
retransmission). This is a message/frame codec: it turns bytes into
structured messages and back, and decides where one unit of the stream
ends and the next begins — nothing about *when* to send which message.
**RTP/RTCP payload interpretation** — `rtsp.interleaved` hands back the
framed bytes as an opaque payload; decoding them as RTP is
`kotoba-lang/org-ietf-rtp`'s job. **Digest authentication** and
**`Range`/NPT-SMPTE-clock time-format parsing** (the `Range` header's
`npt=`/`smpte=`/`clock=` sub-grammars) are not implemented — real
values appear in the SETUP/PLAY test fixtures as opaque header strings,
but no structured decoder for them exists yet.
