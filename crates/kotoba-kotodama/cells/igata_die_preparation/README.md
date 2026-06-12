# igata_die_preparation — Pregel cell for die preheat + release agent spray

Per **ADR-2605261200 §Design Pregel cells #2**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **zebulun** (die-prep + utility specialist).

Die material reference (open-source choice):
- **H13 hot-work tool steel** — industry standard for HPDC die (Mo + Cr + V alloyed)
- **Anviloy 1150** *(deferred R3+)* — W-based die for ≥6000 ton class, only with G7 W non-ammunition certification
- **Open-source CAD format**: FreeCAD `.fcstd` / Open CASCADE `.step` / OpenSCAD only (G3)

Release agent / lubricant constraints (Charter Rider §2(g) + G7=NONE):
- Water-based emulsion (e.g., open-formulation graphite-water or wax-water emulsion)
- **Prohibited**: chlorinated solvent (1,1,1-TCE, methylene chloride), PFAS, leaded paste

Thermal management:
- Preheat target 180-260°C for Al-Si HPDC (G9: induction or radiant electric only)
- Thermal cycle limit per die design (typical H13 = 100k cycles before re-machining)
