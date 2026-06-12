# pharma_sterile_fill_finish — Pregel cell for aseptic processing + BFS fill-finish

Per **ADR-2605250530 §Decision 3-6** (aseptic processing / Annex 1 / Hitogata class-A / QC bridging).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **joseph** (commissioning leader — clean room construction natural extension).

Driven by:
- **Hitogata class-A sterile** sub-config (kuni-umi inheritance, BFS interior manipulation)
- Annex 1 (2023 改訂) §7 BFS-specific compliance
- 0.22 µm sterile filter integrity test (in-line)
- Container closure integrity test (CCIT) on each lot

Constitutional gate enforcement: **G8** (sterile process validation — 3-batch consecutive
media fill + CCIT required for R2→R3).
