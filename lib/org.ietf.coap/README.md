# kotoba-lang/org-ietf-coap

**CoAP (Constrained Application Protocol) message wire codec — RFC 7252 —
with RFC 7959 block-wise transfer, in portable `.cljc`, with no
dependencies.**

This is a codec, not a client, server, or proxy. It turns a CoAP message
(4-byte header, token, delta-encoded options, optional payload) into bytes
and bytes back into a message — no UDP socket, no retransmission of
Confirmable messages, no deduplication by Message ID, no matching a
response to its request by Token, no CoAP-over-DTLS or CoAP-over-TCP
transport framing. A caller feeds it bytes read from (or destined for) a
socket; this library does not open one.

## Surface

```clojure
(require '[coap.message :as msg])

(def get-req
  (msg/encode {:type :con :code :get :message-id 0xABCD :token [1 2 3 4]
              :options [[:uri-path (msg/ascii->bytes "sensors")]
                        [:uri-path (msg/ascii->bytes "temperature")]]}))
;=> {:status :ok :bytes [0x44 0x01 0xAB 0xCD 1 2 3 4 0xB7 0x73 0x65 0x6E ...]}

(msg/decode (:bytes get-req))
;=> {:status :ok :message {:type :con :code :get :options [[11 [...]] [11 [...]]] ...}}
```

| namespace | |
|---|---|
| `coap.code` | the Code field (`class.detail` <-> byte <-> keyword) |
| `coap.options` | Option Numbers table and the Delta/Length nibble-extension arithmetic |
| `coap.message` | the whole message: header, token, options, payload — `encode`/`decode` |
| `coap.block` | RFC 7959 Block1/Block2 option VALUE encoding (NUM/M/SZX) |

Bytes are `Sequential` collections of ints in 0..255, in and out. Every
function returns `{:status :ok ...}` / `{:status :error :reason kw}` /
`{:status :incomplete}` — nothing throws, and `:incomplete` (a message
truncated mid-transfer) is a distinct, non-error outcome from `:error`
(bytes that are not, and will never become, a valid CoAP message).

Options are addressed by name (a keyword from `coap.options/option-numbers`,
e.g. `:uri-path`, `:content-format`) or by raw option number, for Block1/
Block2 (27/23, defined in `coap.block`, not `coap.options`) and any option
number this table doesn't happen to carry. `encode-options` sorts its input
by option number for you — CoAP requires options in ascending order on the
wire, but nothing requires the caller to have built their option list in
that order already.

## Three details that are usually got wrong

**An option's Delta is not its number — it's the DIFFERENCE from the
previous option's number**, which is why two options with the same number
(repeated `Uri-Path` segments, repeated `If-Match` values) are written
back to back with a Delta of 0, and why options MUST appear in ascending
numeric order: a decoder has no other way to recover the actual numbers.

**`0xFF` is not always the payload marker.** It's the payload marker only
at a point where an option-header byte was expected — RFC 7252 reserves
nibble value 15 in the Delta or Length position specifically so that
seeing a byte with BOTH nibbles at 15 (i.e. the literal byte `0xFF`) at
that position is unambiguous, and a byte with only one nibble at 15 (like
`0xF3` or `0x3F`) is a format error, not "a bigger delta/length that
happens to look like it might be the marker."

**Block-Wise Transfer's NUM/M/SZX triple is one bit-packed integer, not
three separately-length-prefixed fields.** The whole option value is 0-3
bytes; NUM occupies everything above the low 4 bits, M is bit 3, SZX is
bits 2-0 — get the field boundaries right and the byte-length of the whole
thing falls out automatically from how large NUM is.

## What this is not

Not a CoAP client or server. No UDP, no DTLS, no CoAP-over-TCP/WebSockets
framing (RFC 8323), no Observe (RFC 7641), no CoRE Link Format (RFC 6690)
parsing, no congestion control or retransmission timers, no
deduplication. Those all belong on top of this codec, in a runtime that
owns IO and a clock.
