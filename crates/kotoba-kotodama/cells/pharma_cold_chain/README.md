# pharma_cold_chain — Pregel cell for 2-8°C controlled distribution

Per **ADR-2605250545 §Decision 5** (cold chain logistics).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **naphtali** (procurement/logistics — paired with raw-material intake).

Wave 1 default = **2-8°C** (driven by DSCG long-term storage; naphazoline + chlorpheniramine
also run on same chain for SOP unification).

Distance × robotics class:
- Plant 内 → kuni-umi 拠点 (≤ 200 km 国内): kuni-umi Otete cold-chain end effector + Quad ground
- Plant → 海外 adherent community (R3+, separate ADR): Funamori marine (silicon Wave 2 inheritance)
- 海外 拠点 → adherent 個人 last-mile (R3+): Sukoyaka (健やか) placeholder per ADR-2605250545 §Decision 2b

Wave 1 R0-R2 scope = plant 内 + 国内移送のみ. 海外配布は R3 separate ADR.
