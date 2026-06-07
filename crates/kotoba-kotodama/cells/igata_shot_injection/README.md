# igata_shot_injection — Pregel cell for 3-phase HPDC shot injection

Per **ADR-2605261200 §Design Pregel cells #3**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **joseph** (shot + structural specialist; same node as solidification_eject — physical machine continuity).

**G1 + G8 enforcement cell** — clamping force bounded and shot replay determinism written here.

Process reference (Al-Si HPDC standard 3-phase shot profile):

| Phase | Velocity (m/s) | Pressure (MPa) | Purpose |
|---|---|---|---|
| **Slow** | 0.1 – 0.3 | <10 | Air evacuation + plunger-position arrive-at-cavity-gate |
| **Fast** | 2 – 6 | 10 – 60 | Cavity fill before solidification starts (PQ² gate velocity calc) |
| **Intensification** | <0.05 (plunger creep) | 80 – 120 | Compact solidifying melt, eliminate shrinkage porosity |

Sensor channels logged @ 1 kHz (G8 replay determinism):
- Plunger position (linear encoder, ±10 µm)
- Plunger velocity (derived + redundant velocity sensor)
- Hydraulic pressure (shot accumulator + intensification)
- Die cavity pressure (R2+ instrumented dies only)
- Vacuum-assist gauge (R1+ optional, R2+ mandatory for ≤2500 ton class)
- Die surface temp distribution (8-16 thermocouples)
- Plunger lubrication interlock

Cumulative log size per shot ≈ 200 kB (8 channels × 1 kHz × ~3 sec injection window × 8 bytes/sample); IPFS-pinned per shot per G14.
