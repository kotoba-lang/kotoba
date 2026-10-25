# kotoba-lang/org-modbus

**Modbus PDUs and framing — TCP, RTU and ASCII — in portable `.cljc`, with no
dependencies.**

`kotoba-lang/dcs` says it plainly in its own `deps.edn`: the domain core is
zero-dependency portable `.cljc`, and `dcs.modbus` is a JVM-only `.clj`
transport layer over `com.digitalpetri.modbus`, supplying "only the
register↔tag mapping on top of it, not a reimplementation of the wire
protocol". That was the right call when the alternative was reimplementing a
wire protocol badly. This library is the alternative done properly, so the
protocol layer can stop being JVM-only.

## Surface

```clojure
(require '[modbus.pdu :as pdu] '[modbus.tcp :as tcp] '[modbus.rtu :as rtu])

(def p (:bytes (pdu/encode-request {:function :read-holding-registers
                                    :address 0x6B :quantity 3})))
;=> [0x03 0x00 0x6B 0x00 0x03]

(:bytes (tcp/encode {:transaction-id 1 :unit-id 0x11} p))
(:bytes (rtu/encode 0x11 p))
```

| namespace | |
|---|---|
| `modbus.pdu` | `encode-request` `decode-request` `encode-response` `decode-response`, thirteen function codes and all nine exception codes |
| `modbus.tcp` | the MBAP header — `encode` `decode` `decode-all` |
| `modbus.rtu` | serial framing — `encode` `decode`, plus `encode-ascii` `decode-ascii` |
| `modbus.crc` | CRC-16/MODBUS and the ASCII mode's LRC |

Bytes are `Sequential` collections of ints in 0..255, in and out.

## Three details that are usually got wrong

**The MBAP length counts the unit id.** It is `1 + (count pdu)`, not
`(count pdu)`. An implementation that omits the one desynchronises the stream
a frame *later* rather than at the frame it got wrong, which is why it
survives casual testing.

**The RTU CRC goes on the wire low byte first.** Modbus is big-endian for
every other field — addresses, quantities, register values — and
little-endian for exactly this one. Reversed, it produces a frame that looks
correct and every device rejects.

**Coil bits are packed least-significant-bit first.** The specification's own
example has coils 20–27 as `0xCD`, which reads `1 0 1 1 0 0 1 1` — backwards
from how the byte is written down.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule:
`:crc-mismatch` (carrying both values, because on a noisy line the difference
is diagnostic), `:lrc-mismatch`, `:not-modbus-protocol`, `:zero-length`,
`:quantity-out-of-range`, `:address-out-of-range`, `:illegal-coil-value`,
`:odd-register-byte-count`, `:frame-too-short`, `:unknown-function`. **Those
keywords are contract.**

An exception *response* — a device saying no — is `{:status :ok :pdu
{:exception :illegal-data-address}}`, not an `:error`. It is a well-formed
message carrying a refusal, and collapsing the two loses the difference
between *the device rejected this* and *these bytes are not Modbus*.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Every framing test is **MODBUS Application Protocol Specification V1.1b3 §6
verbatim** — the specification's own worked examples, the only place both
sides of an exchange are written out. A codec that agrees with itself passes
a round-trip suite and fails against a device.

The CRC gets three independent checks rather than one remembered constant:

1. The CRC RevEng catalogue check value, `0x4B37` for `"123456789"`.
2. `crc16` (nibble table) against `crc16-bitwise` (the definition) over
   **all 65,536 two-byte inputs**. Two implementations agreeing is a stronger
   statement than either matching a value someone recalled.
3. Every single-bit error in a full frame is caught — flipped one at a time
   across every byte and bit position.

## A trap this library's own suite fell into

`(map int "123456789")` gives code points on the JVM and a vector of **zeros**
under ClojureScript, where a character is a one-character string and `int` of
one is not a code point. The catalogue check therefore ran against nine zero
bytes, and `kbb -M:test` reported it green. Only the second runner saw it.

That is the third time this idiom produced a wrong-and-plausible answer in
this workspace in one day — it also made `Sec-WebSocket-Accept` a digest of
zeros in `org-ietf-websocket`, and made two different passwords hash
identically in `org-ietf-argon2`. Write the bytes out, or use a real UTF-8
encoder.

## Not here

**Sockets, and the silence that delimits an RTU frame.** RTU has no start or
end delimiter: a frame ends after 3.5 character times of quiet on the line.
That is a timing property no pure library can observe, so `rtu/decode` takes
a buffer the caller has already delimited and checks the checksum. A caller
reading a real serial port owns the silence.

**Function codes 0x18 and above**, the file-record and FIFO functions, and
the encapsulated-interface transport. They are in the specification and
nothing in this workspace uses them; adding untested code paths for
completeness is how a protocol library acquires bugs nobody finds.
