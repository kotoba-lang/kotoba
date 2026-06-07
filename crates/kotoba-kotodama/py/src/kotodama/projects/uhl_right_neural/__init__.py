"""uhl_right_neural — 先天性右側感音難聴 (neural軸) 治療研究 Pregel.

Authoritative ADRs:
  - 2605181000 — project charter (16-vertex Pregel, 15-actor fleet)
  - 2605181040 — medical institution registry schema
  - 2605181050 — overseas referral paths
  - 2605181060 — Otarmeni access path

Pregel topology (V01-V16, see pregel.py for the StateGraph):

    V01 Phenotype → V02 Genetic, V03 Imaging, V04 Electrophys, V05 CMV/TORCH
                         ↓
                  V06 Substrate Classifier (DMN, 4-way hinge)
                  ┌────────┬────────┬─────────┐
                  ▼        ▼        ▼         ▼
                SGN+    SGN-deg   SGN-       Nerve
                HC-only  +nerve   absent      aplasia
                  │        │        │           │
            V07 OTOF-tx  V08 BDNF  V09 reprog  V11 ABI
                  ↓        ↓        ↓           ↓
                  └─── V10 eCI / optoCI ────────┘
                                ↓
                       V12 Plasticity (age × critical period)
                                ↓
                       V13 Bayesian outcome
                                ↓
                       V14 Trial → V15 Reg
                                ↓
                       V16 Institution Matcher

P0 MVP (this scaffold): V01, V06, V16 + Pregel skeleton with all 16 nodes declared.
"""

__all__ = ["__version__"]
__version__ = "0.0.1"
