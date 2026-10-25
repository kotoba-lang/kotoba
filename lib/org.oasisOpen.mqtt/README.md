# kotoba-lang/org-mqtt

**MQTT control-packet wire codec — OASIS MQTT Version 3.1.1 and MQTT Version
5.0 — in portable `.cljc`, with no dependencies.**

This is a codec, not a broker or a client with IO. It turns packet data into
bytes and bytes back into packet data — no sockets, no threads, no
reconnect/keep-alive/retry logic, no topic-matching engine. A caller feeds
it bytes read from (or destined for) a TCP connection (or a WebSocket, or
whatever transport); this library does not open one.

## Surface

```clojure
(require '[mqtt.packet :as pkt] '[mqtt.utf8 :as utf8])

(def p (pkt/encode-publish {:version 4 :qos 1 :packet-id 7 :topic "a/b"
                            :payload (utf8/ascii->bytes "hello")}))
;=> {:status :ok :bytes [0x32 0x0C 0x00 0x03 0x61 0x2F 0x62 0x00 0x07 0x68 0x65 0x6C 0x6C 0x6F]}

(pkt/decode (:bytes p) 4)
;=> {:status :ok :type :publish :packet {:topic "a/b" :qos 1 :packet-id 7 ...} :next-index 14}
```

| namespace | |
|---|---|
| `mqtt.varint` | the Variable Byte Integer (Remaining Length / Property Length) |
| `mqtt.utf8` | the length-prefixed UTF-8 string / binary-data field |
| `mqtt.fixed-header` | packet type, per-type reserved flags, Remaining Length |
| `mqtt.properties` | MQTT 5.0 Properties (absent from 3.1.1 entirely) |
| `mqtt.packet` | CONNECT, CONNACK, PUBLISH, PUBACK/PUBREC/PUBREL/PUBCOMP, SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ, PINGRESP, DISCONNECT, and `decode` (whole-packet dispatch) |

Bytes are `Sequential` collections of ints in 0..255, in and out. Every
function returns `{:status :ok ...}` / `{:status :error :reason kw}` /
`{:status :incomplete}` — nothing throws, and `:incomplete` (a truncated
packet on a stream transport) is a distinct, non-error outcome from
`:error` (malformed bytes that will never become a valid packet no matter
how many more arrive).

Pass `:version 4` for MQTT 3.1.1 or `:version 5` for MQTT 5.0 to every
`encode-*`; `decode`/`decode-*` need the version too, because nothing in a
packet's own bytes says which protocol version it belongs to — that is
only ever known from the CONNECT packet at the start of the connection.

## Three details that are usually got wrong

**MQTT 5.0's PUBACK/PUBREC/PUBREL/PUBCOMP have a short form.** A Reason
Code of Success with no Properties may be omitted entirely, leaving
Remaining Length at exactly 2 — the same two bytes 3.1.1 always sends. A
codec that always emits the long form is spec-legal but interoperability
hazard #1 against implementations that assume the short form is common; a
codec that always assumes short-form-or-nothing breaks the moment a real
Reason Code shows up.

**The Remaining Length field is little-endian base-128, and every other
multi-byte field in MQTT is big-endian.** Keep Alive, Packet Identifier,
string lengths — all big-endian. Only the Variable Byte Integer used for
Remaining Length and Property Length reads least-significant-7-bits-first.

**A device saying no is not a decode error.** An MQTT 5.0 Reason Code of,
say, `0x87` (Not Authorized) on a CONNACK is a well-formed packet that
happens to carry a refusal — `decode-connack` returns `{:status :ok ...}`
for it, the same way `modbus.pdu` in this workspace treats a Modbus
exception response as a successful decode of a message that says no.

## What this is not

Not a broker. Not a client. No topic-filter wildcard matching (`+`/`#`),
no retained-message store, no session state, no QoS delivery
state-machine, no TLS, no WebSocket framing. Those all belong on top of
this codec, in a runtime that owns IO.
