# pharma_purification — Pregel cell for API purification

Per **ADR-2605250515 §Decision 4** (purification scheme per compound).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **zebulun** (chemistry paired with synthesis).

Purification template:
- DSCG: recrystallization from EtOH/H₂O + activated charcoal + 0.45 µm filtration → ≥ 98.5% HPLC
- Naphazoline HCl: recrystallization from i-PrOH/EtOAc + activated charcoal → ≥ 99.0% HPLC
- Chlorpheniramine maleate: recrystallization from acetone + **preparative-scale HPLC** for genotoxic 4-chlorobenzyl chloride removal (ICH M7 Class 1B: ≤ 1.5 µg/day per 70 kg patient) → ≥ 99.5% HPLC

The ICH M7 PGI removal step (chlorpheniramine prep-HPLC) is the most stringent
per-compound capability requirement; QC bridging via `pharma_qc` cell auto-verifies
ICH M7 limits after this step.
