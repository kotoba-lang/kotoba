# kotoba-lang/io-alembic

`ogawa.core` — the binary container Alembic files are written in. Portable
`.cljc`.

An `.abc` file is two layers: **Ogawa** underneath, a tree of groups and data
blocks addressed by 64-bit offsets, and the **Alembic object model** above it,
which gives those blocks meaning. This repository is the lower layer.

```clojure
(ogawa/write-archive (ogawa/group (ogawa/data [1 2 3]) ogawa/empty-data))
(ogawa/read-archive bytes)  ;=> [:ok tree] or [:error why]
```

## Where the layout came from

Transcribed from `AcademySoftwareFoundation/alembic` `lib/Alembic/Ogawa`,
read 2026-08-23 — `OStream.cpp` for the header bytes, `IStreams.cpp` for how
they are validated, `IGroup.cpp` and `IData.cpp` for the node encoding, and
`Foundation.h` for the four sentinel values.

    header, 16 bytes
      0..4   'O' 'g' 'a' 'w' 'a'
      5      0 while writing, 0xff when the archive is complete
      6..7   version, (byte6 << 8) | byte7 — written as 0, 1
      8..15  uint64 little-endian position of the root group

    group at P    uint64 child count, then that many uint64 child values
    data  at P    uint64 size, then that many bytes

    child value   0x0000000000000000  EMPTY_GROUP
                  0x8000000000000000  EMPTY_DATA
                  high bit set        data at (value & 0x7fff…)
                  high bit clear      group at value

The reader is tested against **bytes assembled by hand from that spec**, in a
layout this library's writer never produces. A reader checked only by
round-tripping its own output agrees with itself; it does not agree with
Alembic.

## What is not here

The Alembic object model: objects, properties, samples, time sampling,
schemas. So this cannot yet pull a PolyMesh out of a real `.abc` — it can tell
you the shape of the tree inside one. `read-archive` returns that raw tree
rather than pretending otherwise, and refuses a file whose byte 5 says it was
never finished.

## Test

```sh
kbb -M:test
```
