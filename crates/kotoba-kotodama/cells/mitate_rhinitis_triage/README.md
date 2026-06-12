# mitate_rhinitis_triage — Pregel cell for 5-condition Bayesian classifier

Per **ADR-2605260100** + all 5 condition sub-ADRs (2605260115/130/145/160/175).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **levi** (audit-style decision;gemma4:e4b distill medical variant 経路).

Algorithm:

- Per-condition Bayesian prior over top-7 sign signature (per condition sub-ADR)
- LLM second-pass (Murakumo only, G12; gemma4:e4b vision-text distill medical variant, open weights G13)
  for narrative cohesion / contextual disambiguation
- G6 escalation flag (pediatric <13 / pregnancy / lactation / immunocompromised / 抗凝固薬服用中)
- G3 disclaimer text injected into output
- R1 advisory tier returns top-3 condition posterior + recommended next-step
  (self-care advisory OR `escalation = "recommend-md-visit"`)

Output lexicon: `com.etzhayyim.mitate.triageVerdict`.
