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

## Native lookup into the 1 GiB Otehon fixture

Two checked-in Forest files are byte-for-byte copies of the first two Packs
from the prior 1 GiB sparse AWAI-532 fixture, whose logical manifest CID is
`bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy`.
The source file was highly compressible and its SHA-256 was
`dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0`.
The Pack SHA-256 values are
`932d89b5e28f61bba5a2fd644b04e8201186218afa90ae5194d8434dbabe6b4f`
and `aa2f7daab2da7bc8f145e439748589e64d7ea1c72b716de0532738a40627bdfc`.
A fresh Otehon recovery of all 64 Packs and `forest/verify-file` of these two
identified 1 MiB blocks whose SHA-256 digests are
`6ffb6ccd5ca18062fb3e6175f6682800e623056b77256e074f1fef9ceb10b900` and
`ad1925fe80c09fb367e0a7b3630232403b03161c78f50e432b48dc723258f4c0`.

The pinned macOS arm64 Native gate read the first selected block directly and
the second through ordered multi-file lookup. It checked both full block sizes
and digests. An independently compiled wrong-second-Pack digest returned 38;
other digest and error-swallowing controls returned their expected failures.
Positive source lock:
`877462795970f0908fbf74b48b61fd2cd6e0df699e4fb4b07f17f6bc706aeaae`;
Native executable SHA-256:
`5d87e5fad7a43a1dfd4f731ee742b96a360fbc3828a8d97f8890adb3c9c9beb9`.
This reads two selected blocks from two real Packs, not all 1 GiB or all 64
Packs in Native. The Native caller receives the locations and CIDs as fixture
inputs; the Otehon logical manifest or root is not authenticated by Native.
OS cache loss, concurrent mutation, Native publication and other platforms
remain separate evidence requirements.

## Canonical 1 GiB manifest to Native Pack reads

The pinned `gib-manifest.cbor` is the exact 71,783-byte canonical logical-file
manifest recovered from the preceding Otehon 1 GiB fixture, SHA-256
`1760ba196e18e6b1ed18477b2a42ed7eee248c191000c41ef2629fc6ebf48d1e`.
A Native executable reads the file through scoped FS2, uses Kotoba's existing
logical-file decoder and canonical CID routine, requires the expected manifest
CID, checks the 1,024 rows and 1 GiB logical size, and takes the selected raw
block CIDs from rows 0 and 16. It then obtains those blocks through the two
actual Forest Pack files and checks their bytes/digests. File locations remain
explicit test inputs, not a verified physical catalog.

The pinned macOS arm64 Native gate passed the manifest-to-Pack path and all
existing file controls. A separately compiled wrong expected manifest CID and
a separately staged manifest with one chunk digest modified each exited 4 at
the CID check before the Pack reads. The positive source lock is
`e51984b1083d93856fcdc71b71591b33e8b47a71d0ad5c1e1fefa5cd6387dc41`;
the Native executable SHA-256 is
`0e6100b9857008294b4c280db4ce937b43bd8cc058dde3537ee531fcda5d97cc`.

The expected CID is a pinned test input, not an authenticated signature or
signed commit. The experiment reads two selected blocks, not the complete
1 GiB. It does not prove a production Native catalog/writer, concurrent file
snapshot, guest or host cache loss, or power-loss durability. Other platforms
and exact-head CI are separate.

## Native manifest-bound chunk view

`awai.fs.forest-view/read-chunk` makes the earlier fixture composition a
reusable Native call. It decodes and validates canonical logical-file bytes,
checks their CID against the caller's expected CID, checks the chunk index,
derives the CID and length from the manifest row, searches the caller-supplied
bounded file locations, and requires the returned verified block length to
match the logical row. It propagates physical read and selected-block errors.
The caller is responsible for authenticating the expected manifest CID and
physical locations; index misses remain untrusted and the provider's
concurrent truncation limitation is unchanged.

On macOS arm64, the Native gate used the preserved 1 GiB Otehon manifest and
Pack fixtures to retrieve row 16 through this function. It checked wrong root
and negative/out-of-range indexes against a missing-file location, showing the
logical rejections happen before file access; it also checked missing-file
propagation and a valid one-chunk manifest whose declared length conflicts
with the real CID-addressed block. The combined Native file/view gate passed
10 positive and negative cases. A separately compiled mutant that ignores the
view's manifest CID check returned 10 as expected. Positive view source lock:
`0c09113249ab201b364108a41e58046a337727a50aceca0ab0dae534cf2a0a67`;
Native executable SHA-256:
`a6f2e314a93151bc38ebf9750cb491900d674be4710b879b08f06572a6472191`.
This tests selected blocks, not Native full-file 1 GiB recovery, signed basis,
atomic publication, or cache/power-loss recovery. Other platforms and
exact-head CI remain separate.

## Opt-in Native verification of all 1 GiB chunks

`forest_gib_full.kotoba` reads and canonical-CID-checks the preserved Otehon
1 GiB logical manifest, then checks all 1,024 1 MiB chunk CIDs against the
actual 64 ordered Forest Packs. Each selected full block is decoded and
CID-verified by Native; the checked length must match its manifest row. The
loop uses a Native `arena-scope` for each chunk and returns success only after
all rows. It chooses one explicitly staged Pack for each 16 rows; this
mapping, the file locations and expected root are fixture inputs, not a
Native-validated persistent catalog or a signed authority.

`gib-packs.bin` concatenates the 64 compressed archive fixture bytes only for
test transport; it is not a new storage format. Its SHA-256 is
`64e67a69917f3a5daaaaff67b48c317878bf9090709a16552e271b062f597ad1`.
`gib-packs.json` records the ordered byte extents and individual SHA-256s;
the gate verifies every extent and digest before staging separate files.
The input is the same highly compressible, marked sparse data as the earlier
Otehon readback, not 1 GiB of physical I/O.

On Darwin 25.4.0 arm64 with the pinned Amu selfhost compiler and Native scoped
file provider, the opt-in `--only forest_gib_full` gate passed all 1,024 chunk
checks. Independently staged one-byte corruptions in Pack 31 and Pack 63 were
refused at those Packs (exit codes 41 and 73); all cases used the same Native
executable. Positive source lock:
`1bc87e2519dec2c3144a33bc317865c17e7e151e84db2a80fb1af42218f2a41f`;
Native executable SHA-256:
`33ea8fe7800b7cb87589e0e38d5993d86b6bd99010a3e73a4ca799a8f992cf8b`.
A single `/usr/bin/time -l` run of staging, compiling and executing the
positive plus both negative cases took 87.44 s, with reported maximum RSS
181,141,504 bytes. This is not an isolated read benchmark; OS cache and other
work were uncontrolled. It validates per-chunk CID and length; it does not
emit a reconstructed byte stream or independently compute its whole-file hash.

The full gate is opt-in and has not been run on Linux or in exact-head CI.
It does not establish a signature, authenticated location catalog, Native
writer/atomic publication, restart after OS cache loss, concurrent mutation
safety, device power-loss durability or production qualification.

## Native GiB verification through the reusable chunk view

On 2026-11-14 JST the opt-in GiB case above was changed to call
`awai.fs.forest-view/read-chunk` for each of the 1,024 chunks. This exercises
manifest canonical CID checking, index and length checks, file-backed Forest
lookup and decoded block CID verification through the reusable Native API;
the earlier low-level result above remains a historical measurement. The root
and per-chunk Pack selection are supplied by the fixture. Each chunk has its
own arena; the manifest is decoded and checked again per call.

On Darwin 25.4.0 arm64 the positive case exited 0; independently corrupted
Pack 31 and Pack 63 were rejected with exits 41 and 73. The source lock was
`aaf30c39bc1d80238b406b10a56a5caf34aca942b84640dfd0a27a9b3733ca45`
and the Native executable SHA-256 was
`d58d849dc3a9eca2c92e372cba343cf3814e08b713f2e501968b217b9a90c3d8`.
One `/usr/bin/time -l` measurement covering staging, compilation and all three
runs took 146.80 seconds and reported maximum RSS 253,722,624 bytes. It is
not an isolated I/O benchmark, and cache and concurrent load were uncontrolled.
The compressed synthetic fixture, caller-supplied authority and mapping,
whole-stream hash, opt-in platform coverage and durability limitations above
still apply; this is not a Native writer or production qualification.

## Native whole-stream digest across the 1 GiB chunk view

On 2026-11-14 JST, `forest_gib_full.kotoba` was extended to feed every verified chunk, in manifest order, into the bounded Native streaming SHA-256 implementation. The accumulator is allocated outside per-chunk `arena-scope`s. After all 1,024 chunk CID and length checks, the program compares the complete stream digest with the independently measured Otehon source/readback value `dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0` documented in `network-awai/awai-os` `README-forest-gib-readback.md`.

On Darwin arm64, the pinned Native compiler and provider built the current sources under a KSL1 lock. The positive run exited 0. A separately compiled control with only the expected whole-stream digest changed exited 74; the positive binary on the separately corrupted Pack 31 fixture exited 41. The positive lock SHA-256 was `ee63a94a04e35c17081005e1cacd069f2795be40867d503affd2fe57d11ce47d`, and signed executable SHA-256 `c2e97ca0b4bcdf2459bbcb280342d98b9f745c2c732a70c0fcc5efa1e2738b69`. The digest-negative lock SHA-256 was `9261a68e3565fd4ace24942e36147bc427d9d1cc707ddb39e727d6f6fcf8d82d`. A single positive execution took 78.96 seconds and reported 253,689,856 bytes maximum RSS. This is an uncontrolled local observation, not an I/O benchmark; compilation of the negative control overlapped part of the run.

The source remains the synthetic, highly compressible fixture; expected root, Pack locations and digest are fixture inputs. The execution computes a full logical hash but does not write a reconstructed file. It does not demonstrate physical GiB traffic, authenticated catalog, Native writer, Linux or exact-head CI, OS cache loss, power-loss durability or production qualification. The Native test and controls were compiled directly with the pinned compiler/packager and a source lock; no Python gate or host codec supplied the result.
