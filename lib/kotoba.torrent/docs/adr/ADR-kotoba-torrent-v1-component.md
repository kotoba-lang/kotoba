# ADR: bounded BitTorrent v1 downloader component

## Decision

The downloader protocol kernel is canonical `.kotoba` source at
`src/kotoba/torrent_v1.kotoba`. It accepts BitTorrent v1 metainfo and peer-wire
bytes, emits bounded handshake/request messages, and validates piece messages.

The protocol kernel has no ambient authority. `torrent_downloader.kotoba`
composes explicitly granted tracker HTTP, peer TCP, and atomic filesystem
imports with the capability-free `kotoba-lang/hash` SHA-1 implementation. Its
commit path calls `sha1-equal?` before `fs-write-atomic`; a mismatch returns
`-2` and cannot reach the filesystem import.

## Initial limits

- BitTorrent v1 only; no v2/hybrid, DHT, PEX, uTP, UDP tracker, or magnet URI.
- Metainfo input is limited to 1 MiB and parser work to 4096 nodes.
- Peer messages are limited to 1 MiB plus their nine-byte piece envelope.
- Request blocks are limited to 16 KiB.
- The first operational download primitive handles one block from an already
  unchoked peer. Choke/unchoke negotiation and multi-block piece assembly remain
  scheduler work; the primitive never labels a partial piece as verified.
- Paths, tracker redirects, DNS, network endpoints, and output roots are policy
  decisions outside the protocol kernel.

These limits make the parser and state primitives useful now without pretending
that untrusted source has socket, hash, or filesystem authority.
