# bencode

Capability-free bencode codec primitives written in canonical `.kotoba`.

The initial bounded decoder validates and skips untrusted bencode values without
allocating object graphs. It is shared infrastructure for BitTorrent metainfo,
tracker responses, and any other bencode consumer.

Limits are caller supplied. The decoder rejects malformed integers, oversized
byte strings, truncated collections, and exhausted parse fuel.
