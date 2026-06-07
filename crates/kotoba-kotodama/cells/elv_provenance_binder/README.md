# elv_provenance_binder — hodoki terminal (R0 scaffold)

Terminal kotoba-datomic provenance binder — anchors full chain (input VIN → parts catalog + material lots + emissions + ASR mass) on kotoba-datomic.
Per ADR-2605261215 §6 terminal. R0 scaffold — `.solve()` raises until R1.

- **Murakumo node**: judah
- **Output**: kotoba-datomic-anchored audit binder + mass-balance attestation
- **Constraints**: G2 mass-balance ≥98% closure (input curb-weight = parts + material lots + emissions + ASR); inherits kanayama G2 pattern
