# Authenticated network topic protocol v1

Status: enforced production baseline  
Date: 2026-07-23

`aiueos.network-topic` carries topic samples across an untrusted transport as
bounded EDN envelopes. Transport selection is outside the protocol; TCP, QUIC,
message queues and store-and-forward links may carry the same bytes.

Each Ed25519 signature binds:

- protocol version and channel id;
- publisher identity and numeric topic id;
- per-publisher/per-topic sequence;
- epoch timestamp and integer sample.

The receiver registry binds an active publisher key to its authorized topic
set. Admission verifies exact wire shape and size, channel, lifecycle status,
topic authorization, signature, and the next expected sequence before
publishing to the local topic bus.

## Replay and restart

Sequence space is independent for each `[publisher topic]`. Duplicate or older
sequences are replay; future sequences are gaps. Both are rejected.
`checkpoint` exports the minimal last-sequence map. A production receiver must
seal and durably persist this checkpoint before acknowledging delivery, then
restore it after restart. Production profile admission requires this mode.

## Partition and rejoin

While partitioned, direct receipt is rejected. Rejoin accepts a backlog only
when every envelope is authenticated, authorized and contiguous. Application
is atomic: any failure leaves the prior bus and anti-replay state unchanged and
keeps the receiver partitioned.

The protocol provides message authentication and authorization, not traffic
confidentiality. Deployments needing metadata or payload confidentiality must
also use an authenticated encrypted transport.
