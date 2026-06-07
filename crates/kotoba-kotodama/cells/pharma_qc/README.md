# pharma_qc — Pregel cell for per-lot QC suite

Per **ADR-2605250515 §Decision 5** (QC suite per lot).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **levi** (audit/witness leader — QC = analytical witness; G9 N≥2 invariant).

QC analyses dispatched per lot (Mimi pharma-analytical sub-config drives instruments):

- **HPLC purity** (per USP/JP monograph wavelength + reference standard)
- **IR identity** (ATR-FTIR vs. reference spectrum)
- **¹H / ¹³C NMR identity** (400 MHz)
- **Karl Fischer water** (DSCG: 5.0-9.0% / others: ≤ 1.0%)
- **ICP-MS heavy metals** (ICH Q3D PDE)
- **GC headspace residual solvent** (ICH Q3C class limits)
- **LC-MS/MS PGI** (chlorpheniramine only: 4-chlorobenzyl chloride ≤ 1.5 µg/day ICH M7)
- **Endotoxin LAL** (≤ 1.0 EU/mL ophthalmic)
- **Microbial limit test** (USP <61> / <62>)

Auto-reject conditions (constitutional G2):
- HPLC purity below monograph
- ICP-MS heavy metal > Q3D PDE
- GC residual solvent > Q3C class limit
- PGI > ICH M7 Class 1B 1.5 µg/day
- LAL > 1.0 EU/mL
