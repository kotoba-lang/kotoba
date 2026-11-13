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
