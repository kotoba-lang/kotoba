# kotoba-lang/voxel

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-voxel` Rust crate
(kotoba-lang/kami-engine, deleted in PR #82 "Remove Rust workspace from kami-engine") as
part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

`voxel.vdb` is the VDB tree itself — a sparse hierarchy with fixed branching
(8^3 voxels per leaf, 16^3 leaves per internal node, 32^3 above) and tiles, in
the shape OpenVDB's `Tree4<T, 5, 4, 3>` uses. `SparseVolume` below is a hash
map of filled cells: sparse, but with neither the locality nor the tiles.

`voxel.nvdb` is the `.nvdb` FILE CONTAINER — segments, their 16-byte
`FileHeader` and 176-byte `FileMetaData`, the grid name, and the grid buffer.
The layout was transcribed from `nanovdb/nanovdb/NanoVDB.h` on 2026-08-24;
two earlier attempts left it unimplemented because only the SIZES were
obtainable, and a parser written from sizes alone round-trips with itself
while opening nobody else's file. The fields were obtainable — from the
source, with a tool that does not summarise.

**The grid buffer is opaque.** `voxel.nvdb` reads and writes the container and
its metadata — what `nanovdb_print` reports — and `voxel.vdb` is the tree.
Nothing connects them: no function here turns a grid buffer into a tree, and
none pretends to. `.vdb` (the OpenVDB file, as opposed to NanoVDB) is still
not read or written. ZIP and BLOSC segments are refused rather than mis-read.

## Status

Restored. `src/voxel.cljk` ports the original `kami-voxel/src/lib.rs` (410 lines) 1:1:
the `Voxel` value type, the `Volume` trait, and its three storage backends —
`DenseVolume` (flat W*H*D array), `SparseVolume` (map of only-filled cells),
`OctreeVolume` (adaptive power-of-2 tree) — plus the `VoxelVolume` wrapper
(`new-dense`/`new-sparse`/`new-octree`, `to-sparse`, `storage-type`). Every backend is a
plain CLJC map tagged with `:type`, with the trait methods becoming generic
`case`-dispatching functions (`vol-get`/`vol-set`/`vol-count-filled`/...). Pure data +
pure functions throughout — no IO/GPU (native execution stays substrate).

All 4 original Rust `#[test]`s (`dense`, `sparse`, `octree`, `wrapper_compat`) are
ported 1:1 to `test/voxel_test.cljk`, plus 1 namespace-loads smoke test — **5 tests /
11 assertions, 0 failures**.

## Develop

```bash
kbb -M:test
```
