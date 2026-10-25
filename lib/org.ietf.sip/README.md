# org-ietf-sip

SIP message codec — RFC 3261 — in portable `.cljc`. Parses and serializes SIP
requests and responses, and the `sip:` / `sips:` / `tel:` URI grammar.

## What this is

A codec. You hand it text, it hands you a map; you hand it a map, it hands you
text. It handles the parts of RFC 3261's grammar that are easy to get subtly
wrong and that a `clojure.string/split` sketch gets wrong immediately:

- **compact header forms** (`i` `m` `e` `l` `c` `f` `t` `v` `k`) canonicalised to
  their long names, so `v:` and `Via:` are the same header
- **folded continuation lines** — a header value continued on the next line by
  leading whitespace
- **quoted strings** that contain separators, and backslash escapes inside them,
  so a display name of `"Watson, Thomas"` is one value and not two
- **comma-folded multi-value headers**, with **order preserved**, because Via
  order is semantically load-bearing (RFC 3261 §18.1.1 routes a response by
  walking Via top-to-bottom) — a set would be wrong here
- structured access to Via / To / From / Call-ID / CSeq / Contact /
  Max-Forwards / Content-Length, with parameters parsed
- `Content-Length` treated as authoritative: a body shorter than the declared
  length is refused as `[:error :sip/short-body]` rather than quietly accepted

Failures are named values, never thrown: `[:error :sip/bad-start-line]`,
`[:error :sip/short-body]`, `[:error :sip/unknown-message-type]`, and so on.
`encode` returns an error value rather than throwing on a map with no `:type`,
so `(encode (decode bytes))` is safe to write without a try.

## What this is not

- **Not a user agent, proxy, registrar or B2BUA.** There is no transaction state
  machine, no dialog state, no retransmission timers, no forking.
- **No transport.** No sockets, no threads, no TLS, no IO of any kind. You bring
  the bytes.
- **No SDP.** SIP carries SDP as an opaque body and this library treats it that
  way. This workspace has WebRTC session-negotiation code in `kotoba-lang/rtc`,
  `kotoba-lang/webrtc` and `kotoba-lang/org-w3-webrtc-signaling`; none of them is
  an RFC 4566 SDP codec, so if you need to parse SDP itself that is still a gap.
- **No authentication.** Digest (RFC 8760 / 2617-style) is not implemented.
- **No media.** RTP/RTCP lives in `kotoba-lang/org-ietf-rtp`.

## Test vectors — provenance

The INVITE and 200 OK fixtures follow RFC 3261's own repeatedly-reproduced
example flows (§8.1.1.1 and the §4 trapezoid), and the header shape and Via
ordering are cited to those sections. **The bodies and their `Content-Length`
values are constructed, not spec text** — the RFC's examples carry an SDP body
this codec does not reproduce, and fabricating SDP bytes while labelling them as
the RFC's own is exactly what this workspace's test-vector rule exists to
prevent. Both `Content-Length` values are the true UTF-8 byte counts of the
constructed bodies.

Everything else is round-trip and structural negative testing: 86 tests, 319
assertions, green on both JVM (`kbb -M:test`) and ClojureScript.

## Use

```clojure
(require '[sip.message :as m])

(m/decode wire-text)   ;; => {:type :response :status 200 :reason "OK" :via [...] ...}
                       ;;    or [:error :sip/short-body]
(m/encode msg)         ;; => wire text, or [:error :sip/unknown-message-type]
```

Licensed Apache-2.0.
