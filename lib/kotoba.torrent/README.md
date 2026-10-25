# torrent

A capability-safe BitTorrent downloader written in canonical Kotoba source.

Current scope is the bounded BitTorrent v1 protocol kernel: metainfo parsing,
exact `info` byte-range discovery, announce extraction, compact IPv4 peers,
handshake, bitfield selection, and request/piece framing. Network, hashing, and
filesystem effects remain explicit provider boundaries.

See `docs/adr/ADR-kotoba-torrent-v1-component.md` for limits and the remaining
downloader-provider work.
