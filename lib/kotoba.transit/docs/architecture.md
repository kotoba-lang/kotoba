# Architecture

`kotoba-lang/transit` is the protocol-level JSON envelope layer for Kotoba. It
is the default internal wire protocol for Kotoba-owned app/resource APIs.
The name predates the switch away from Transit-style tagged JSON
(`ADR-kotoba-json-wire-protocol.md`, which supersedes
`ADR-kotoba-transit-wire-protocol.md`); the repository keeps its name and
`transit.core` namespace to avoid a disruptive rename, but the wire values it
produces are plain JSON, not Transit.

## Authority

The authority boundary is CLJC source in this repository:

- `src/transit/core.cljk` defines the media type and EDN-to-plain-JSON shapes.
- Tests in `test/transit` pin Datomic and app-resource envelope shapes.
- Host runtimes may encode/decode bytes and gzip-compress bodies, but
  envelope semantics remain here.

## App/resource wire

Kotoba-owned app APIs should use versioned JSON envelopes. The current
office-family resource kinds include:

- `:slides/deck`
- `:sheets/workbook`
- `:docs/document`
- `:forms/form`
- `:office/update`
- `:office/selection`
- `:office/presence`

Other families may add resource kinds, but should reuse the shared envelope
vocabulary and `application/json` media type. Bodies above
`transit.core/default-gzip-threshold-bytes` should set
`:content-encoding "gzip"`.

## Datomic first

Kotoba's tier-1 database API is Datomic-shaped:

- datoms are the source of truth
- EDN forms describe transactions and Datalog queries
- plain JSON (optionally gzip) is the HTTP wire media type

SPARQL, Cypher, and GraphQL are tier-2 adapters over this graph.

OpenAPI, ActivityStreams, XRPC, provider REST, and OpenAI-compatible request
shapes are adapter surfaces. They are not the internal source of truth for
keywords, symbols, sets, datoms, CIDs, operations, or patches — but neither
is a bespoke tag scheme any more. The wire projection is intentionally lossy:
callers that need EDN identity back on a field do so explicitly for the
fields they know are typed (see `read-office-envelope-body`).

## Transport layer

This repository only defines the payload encoding, not the transport. QUIC
and WebTransport are already the transport direction elsewhere in Kotoba
(`kotoba-lang/net` for libp2p QUIC native↔native, `kotoba-lang/murakumo` for
HTTP/3-first ALPN, `kotoba-lang/rt` for transport-independent WebRTC
signaling). A JSON body from this library is equally at home over HTTP/1.1,
HTTP/2, HTTP/3, or a WebTransport datagram/stream.

## Rust-free migration

The current `kotoba` Rust CLI/server may still send or receive
`application/json` while those components exist. That does not make Rust the
envelope implementation. Rust hosts should:

- import no envelope semantics beyond media type compatibility
- delegate value-shape decisions to this CLJC library or generated artifacts
- disappear as Kotoba-native CLI/server components replace the compatibility host
