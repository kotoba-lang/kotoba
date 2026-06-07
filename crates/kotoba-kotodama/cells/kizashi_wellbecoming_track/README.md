# kizashi_wellbecoming_track — kizashi (R0 scaffold)

compute a self-referenced Wellbecoming trajectory — compare the member's current
scan to their OWN prior scans and emit a delta. No population norm / ranking /
health-score.

Per ADR-2605312700. R0 scaffold — `cell.py` raises at import time until R2
(Council Lv6+ ≥4 + 30-day public + encrypted backend live).

- **Actor**: kizashi (兆) — `did:web:kizashi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: **G8 (self-referenced — baseline = member's own prior scan only; no population field exists)** + G2 (encrypted) + G14 (Murakumo-only)
- **Output Lexicon(s)**: com.etzhayyim.kizashi.wellbecomingTrajectory
- **Ceiling**: SELF-REFERENCED WELLBECOMING (G8, anti-individualist 動的軌跡, ADR-2605192100) · ENCRYPTED-ENVELOPE (G2, ADR-2605181100) · Murakumo-only inference (ADR-2605215000)
