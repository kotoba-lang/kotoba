# Mux and head

A live socket and the causal tip of an agent's chain are separate coordinates.

- **mux** — an application stream opened by Yamux after a Noise handshake
- **head** — the last signed action or graph CID claimed by an agent, analogous
  to a Holochain source-chain head, Git HEAD, an IPNS graph CID, or an Inga
  quorum certificate

`kotoba.protocol.mux` makes the distinction executable. `at-head?` never uses
stream liveness. Dialer stream IDs are odd, listener IDs are even, and stream 0
is reserved for session control.

This process does not open streams. `open-live` fails closed with
`:not-a-dht-node`, and live maturity is blocked on transport
(ADR-2608145800). Identity and authorization are established before transport;
opening a stream does not grant permission to write.

See [Who may write](who-may-write.md) for overlay authorization. This file is
the session-plane document; there is intentionally no separate `session.md`.
