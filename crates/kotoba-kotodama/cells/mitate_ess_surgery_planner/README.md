# mitate_ess_surgery_planner — Pregel cell for ESS + septoplasty surgical planning

Per **ADR-2605260145 §Decision 5** (ESS planning) + **ADR-2605260160 §Decision 4** (septoplasty planning).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **levi** (audit-tier).

Dual-purpose cell (conditionContext field で分岐):
- ESS (condition 3 — endoscopic sinus surgery)
- Septoplasty / septorhinoplasty (condition 4)

Output advisory payload includes:
- 罹患洞 location (ESS) or 弯曲 type (condition 4)
- preliminary approach suggestion
- 入院 期間 + cost estimation (transparency, §2(e) anti-paywall)
- **surgeon DID attestation required** (N4 non-goal: mitate plans only, surgeon executes)

R3 phase activation only. Requires 2 ENT surgeons + 1 anesthesiologist on Council Lv6+.
