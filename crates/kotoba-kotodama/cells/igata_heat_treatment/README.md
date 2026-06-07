# igata_heat_treatment — Pregel cell for T5 / T6 / HT-free branch + verify

Per **ADR-2605261200 §Design Pregel cells #7**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **dan** (HT specialist).

HT recipe branches (Al-Si HPDC structural parts):

| Branch | Process | Target yield (MPa) | Use case |
|---|---|---|---|
| **HT-free** (default) | In-die rapid cool + Sr modifier; open-recipe equivalent to Tesla AS3 | ~150 MPa | ≤5 kg structural parts; high-throughput |
| **T5** | Artificial age only (no quench); 150-200°C × 4-12 hr | ~180-220 MPa | Stable structural without quench distortion |
| **T6** | Solutionize 500-540°C × 4-8 hr → quench → age 150-200°C × 4-12 hr | ~250-310 MPa | Maximum strength structural (knuckle, control arm) |

Open recipe references (no proprietary lock-in):
- HT-free baseline: AlSi9Mg0.3 + 200 ppm Sr (from `igata_alloy_melt` G7 baseline)
- T6 standard: A356 (AlSi7Mg0.3) per Aluminum Association handbook

Equipment (R2+):
- Solutionize furnace: electric resistance or induction (G9: no fossil-fired)
- Quench bath: water 40-80°C, polymer (UCON/Aqua-Quench) for low-distortion class
- Age furnace: convection electric, ±2°C uniformity

Hitogata class-A clean loading (R2+) — solutionize furnace operates 500-540°C, manual operator R1 with thermal PPE, Hitogata humanoid takeover R2+.
