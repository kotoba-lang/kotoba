# io-libp2p-specs-transport

[![CI](https://github.com/kotoba-lang/io-libp2p-specs-transport/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/io-libp2p-specs-transport/actions/workflows/ci.yml)

**multistream-select 1.0.0** and **Yamux** — the two protocol layers between a
libp2p socket and an application stream. Portable `.cljc`, zero dependencies,
no socket.

Written to close the transport gap that stopped
[`io-libp2p-specs-kad-dht`](https://github.com/kotoba-lang/io-libp2p-specs-kad-dht)
from being a real DHT node. The stack a libp2p connection negotiates is:

```
TCP  →  multistream(/noise)  →  Noise XX  →  multistream(/yamux)  →  Yamux
                                                                      ↓
                                            multistream(/ipfs/kad/1.0.0) per stream
```

`kotoba-lang/noise` already implements the XX pattern and
`multiformats.multiaddr` the addresses, so what remains after this repo is the
socket itself.

## multistream-select: one rule, and it is the newline

Every message is a **varint-length-prefixed UTF-8 string ending in `\n`**, and
**the newline is inside the length**. Sending the length without it, or the
newline outside the prefix, produces a stream the peer cannot frame — and
because the very first message is the protocol id, the failure looks like the
peer speaking an unknown protocol rather than a framing bug.

**The echo is the acceptance.** A responder that accepts `/noise` replies
`/noise`. There is no `ok`, and a dialer that treats an unexpected message as
success goes on to speak a protocol nobody agreed to.

**Order is the whole of the preference expression** — no scoring, no
negotiation beyond the list the dialer sends.

**The header and the first proposal go out together.** One round trip per layer
instead of two, and there are three layers per connection.

**`ls` is answered `na`.** Listing everything a node speaks is free
reconnaissance, and every real negotiation works without it.

`negotiate` runs a dialer and a listener against each other in memory. That is
how the tests check both halves: testing one half against a hand-written
transcript proves it agrees with the transcript, not with a peer.

## Yamux: `length` means two different things

The header is twelve octets — `version type flags streamID length` — and
`length` is overloaded. For **DATA** it is a byte count and that many octets
follow. For **WINDOW_UPDATE** it is a **credit delta** and **nothing follows**.

An implementation that reads `length` octets after a window update consumes the
next frame's header as payload and desynchronizes the connection permanently,
with no error, because the bytes are structurally valid. There is a test that
puts a window update immediately before a data frame.

**Stream IDs encode who opened the stream.** Dialer odd, listener even, 0
reserved for session frames. That parity split *is* the collision avoidance:
without it both ends eventually choose the same ID for different streams and
each reads the other's data as its own. `valid-peer-id?` rejects a peer opening
with our own parity.

**FIN is a half-close.** It says *we* will send no more; the peer may still
send to us. Treating it as a full close drops data the peer was entitled to
send.

**Flow control is not optional.** Each stream starts with a 256 KiB window; a
sender that ignores it is dropped by a conforming peer, and a receiver that
never returns credit stalls the stream at exactly that many octets and looks
like a hung peer. Credit is returned **lazily**, below half a window — one
update per packet would be its own flood.

## A reply is not always on the stream you opened

`libp2p.provider.node-muxed` (the async Node driver over this repo's pure
codecs) originally reset any inbound Yamux SYN it did not itself open —
correct for protocols where the peer answers on the stream you dialed
(identify, Kademlia), and silently wrong for one that does not: **go-bitswap
answers a want by opening a NEW stream toward you and writing its `Message`
there**, never on the stream your want arrived on. A dialer that only reads
back the stream it opened, and resets everything else, negotiates
`/ipfs/bitswap/1.2.0` cleanly, sends a well-formed want-block, and then times
out — having reset the very stream carrying the answer before ever reading
it. Measured against both a local Kubo node and several public-network peers:
this was the entire cause of "negotiates fine, never answers", not a wire
encoding bug.

`connect-and-secure!` now takes an `:accept-protocols` opt-in (default empty,
preserving the old reset-everything behaviour) and `accept-stream!` runs the
LISTENER half of multistream-select on whichever inbound stream the peer
opens, so a caller can read a reply that arrives on a stream it did not
dial. It tries pending streams in arrival order, capping each candidate
rather than the whole call, because a peer may open unrelated streams first
(identify-push, measured) that never resolve to a protocol you asked for.

## Usage

```clojure
(require '[libp2p.multistream :as ms] '[libp2p.yamux :as y])

;; negotiate a security protocol
(let [{:keys [out dialer]} (ms/dialer-start (ms/dialer ["/noise" "/tls"]))]
  (write! out)
  ;; feed each received message back:
  (ms/dialer-recv dialer msg))   ;=> {:dialer d :out … :done "/noise"}

;; then muxing
(def sess (y/session :dialer))
(let [{:keys [session stream-id out]} (y/open-stream sess)] …)
(y/decode-all incoming)          ;=> {:frames [...] :rest bs}
```

Everything is a value: frames and messages are octet vectors, sessions are
maps, and the caller owns the socket.

## Scope

- **In:** multistream-select 1.0.0 (framing, dialer, listener, in-memory
  negotiation), Yamux (frame codec, session, stream IDs, flow control,
  half-close, reset, ping, go-away).
- **Not here:** the socket, Noise (see
  [`kotoba-lang/noise`](https://github.com/kotoba-lang/noise)), addresses (see
  `multiformats.multiaddr`), and the identify protocol.
- **Not yet:** mplex (superseded by Yamux in practice), and QUIC — which
  subsumes both layers in this repo and is a different project rather than an
  addition to it.

## Test

```
kbb -M:test
```

25 tests / 119 assertions.
