# Transport

Transport moves **bytes to a neighbor**. It does not own identity.

TCP, QUIC, WebRTC, Tor, relays, and WebSocket addresses are represented as
multiaddrs. Implementations live in `io-libp2p-specs-transport`, `noise`, and
`libp2p`.

`kotoba.protocol.transport` defines the pure hop algebra: a hop is a multiaddr
plus protocol capabilities. Supplying `ipfs://`, `ipns://`, or `https://` as a
hop address fails with `:not-a-multiaddr`. Attaching a hop to a CID or peer never
rewrites that identity.

This repository intentionally opens no sockets. `dial-live` returns a named
blocked result because this process is not a DHT node. Live maturity remains
blocked on `:dht-node-transport`; framing belongs to the transport repository,
not here.

An HTTPS gateway such as `https://ipfs.kotobase.net/ipfs/{cid}` is a transport
and location projection. The canonical identity remains `ipfs://{cid}`. An
HTTP URL in an object graph therefore describes where bytes may be retrieved;
it is not proof of the bytes' CID.
