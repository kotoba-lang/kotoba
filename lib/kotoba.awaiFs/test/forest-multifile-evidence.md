# AWAI-531 Native Forest multi-file probe — 2026-11-14 JST

This adds a second real Forest archive from Awai OS's crosspack fixture. Each
archive is independently opened via the scoped Native FS2 file capability,
its selected 64 KiB raw block is decoded and its CID digest checked. The
second CID returns `:no-candidate` against the first archive's untrusted
index. This is an index lookup result, not an archive-wide absence proof or a
Native multi-Pack catalog.

The fixtures' SHA-256 values are:

- `forest-part0.car.zst`: `87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df` (1,767 bytes).
- `forest-part1.car.zst`: `33469df01bb4f837d655da9b232a366910ab4a575094235ffc875029f46ad206` (1,765 bytes), copied from `network-awai/awai-os` revision `f6d07f93652c70662005f86c44659b27b0a657dd`, `nixos/otehon/storage/test/fixtures/crosspack/part-1.forest.car.zst`.

The second block's CID digest and length were independently read from that
fixture using the dated Otehon Forest/CAR oracle: digest
`7786c19371f6b8a948e551624e0dd2993ca6c21439bf876f67a14821807b8c88`,
65,536 bytes. Babashka 1.12.218 was a local reference only.

On Darwin 25.4.0 arm64, the pinned Amu selfhost compiler and Native file gate
produced a passing Native artifact (exit 0). Independently compiled controls
with an incorrect first and second block digest returned 3 and 13 respectively.
The positive source lock is
`e58ec3eb29ab4a8407e65c55c588a924021826b675a38a9a3af374bb178ae616`;
the Native executable SHA-256 is
`e9324855328912d04c06cce5e353357243f432f63cfc4acc884276c4df8ce3d4`.
Full per-case locks and hashes are retained in the task's `.agent-output`.

This uses two immutable fixture files and one Native process. It does not
establish concurrent mutation safety, general Forest/Zstd coverage, durable
publication or recovery, a Native writer, OS-cache loss, GiB scale or product
qualification. Native tests on other hosts and exact-head CI are separate.

## Ordered Native file search

`get-block-in-files` accepts 1–64 paths and the same number of file sizes.
It returns the first verified matching block, proceeds only for an individual
`:no-candidate`, and propagates other errors. A group-level `:no-candidate`
is also only an untrusted-index outcome: later files are not read after a hit,
and unread frames/files are not scrubbed. This is an in-memory list of
locations, not an authenticated catalog or an atomic multi-Pack publication.
The single-file provider's concurrent truncation limitation still applies.

The macOS arm64 Native gate exercised a hit in the first and second file,
all-index misses, selected corrupted data, a missing file before a valid file,
and empty, mismatched and >64 entry bounds. Its Native executable returned 0.
Independent wrong-digest controls returned 3 and 13. A separate compiled
negative control that silently continued past all errors returned 20, proving
the selected corruption test detects that regression. Positive source lock:
`4e51381e59015da39aad5450cbed5e3d61b10814dff570cd08e0d4050daf477d`;
Native executable SHA-256:
`45ca739f184fdd845829db9e09a0353a8e8b8586542a9c772a2475da636b1aad`.
Other hosts and exact-head CI remain separate.

## Bounded tail index and larger positioned file

The Native adapter reads the bounded index/footer tail instead of allocating a
vector for the entire archive. `find-frames-tail` checks the tail's base,
total length and absolute index and frame offsets, with a 32 MiB file bound;
the previous in-memory `find-frames` still has its original 1 MiB bound.
Selected compressed frames remain capped at 256 KiB, and selected bytes are
CID-verified. This does not yet cover incompressible 1 MiB leaf frames.

The 1,155,199-byte fixture was built from `forest-part0.car.zst` by prefixing
one Zstd skippable frame and adjusting physical index offsets. Its SHA-256 is
`eea07036e8a76dd891f675a198a3da90afa4181f31794c910f376fe27b7bd39f`.
It is reproducible by passing a new task-owned output path to
`generate_large_forest_fixture.py`; the script refuses to overwrite a file. The independent Otehon
`forest/verify-file` accepted its archive, index, canonical Pack root and
block CIDs; selected first frame starts at 1,153,500 and index at 1,154,951.
The macOS arm64 Native gate read the selected block from that actual file and
refused a changed index and a file size above 32 MiB. The existing Native
Zstd, file, digest and error-fallback mutation controls also passed.

This is a shifted small Pack, not 1 GiB of data or a full verification of the
archive by Native. No authenticated catalog, concurrent truncation safety,
Native writer, OS-cache-loss or power-loss conclusion follows.

## Segmented positioned reads for a 1 MiB block

The preceding 256 KiB selected-frame limit described the earlier revision.
The current implementation retains 256 KiB as the maximum **single FS2
request**, reads at most 2 MiB per selected frame in ordered segments, and
limits decoded CAR sections to 2 MiB. It CID-verifies the returned complete
selected block. The provider can still terminate on a concurrent short read;
segmentation does not establish a file snapshot.

The pinned `forest-megaframe.car.zst` (1,048,922 bytes, SHA-256
`ee5c2c5c601e5f24cbf087ac73f8e9cfdd3bfa3002445e426b48a9756e6c0d50`)
was generated locally by the AWAI-532 Otehon `put-file-large!` at Awai OS
revision `f6d07f93652c70662005f86c44659b27b0a657dd` using the digest-pinned
Forest tool `e5fb23076a46c055142b3dbf3efa1ad5a68532d14419ad9994785986719b205f`.
The 1 MiB input was created with `java.util.Random` seed `53120261114` as a
local fixture, not a security random source. Otehon's independent
`forest/verify-file` identified the selected compressed frame at byte
68..1,048,719 and its 1,048,576-byte raw block SHA-256
`ef25f52bde3a24316912f2214e179ca2e56c21e78cd3ea76a06296e96ff2349e`.

The pinned macOS arm64 Native gate read and CID-verified that full block.
Flipping a byte inside the third requested segment caused `:cid-mismatch`.
A separately compiled wrong expected digest returned 31, and existing two
small-file digest and error-swallowing controls returned 3, 13 and 20. Positive
source lock: `5deaba66a2596aa1a451879e611c74c167466be68f28821f549d64c34d9462d8`;
Native executable SHA-256:
`da0dcb0291c77df2a79ae802cb86dfc0987eb28440ab1056348fa3fb12eca844`.
The earlier Native Zstd and index controls were rerun with the new reader.

This exercises one seeded, essentially incompressible frame and does not prove
all Zstd modes, stable concurrent file identity, Native publication, a 1 GiB
Native read, cache-loss recovery or production qualification. Other platforms
and exact-head CI require their own results.
