# tsukuroi_finding_intake — tsukuroi (R0 scaffold)

consume an owner-attested akuma vulnerability finding within an active RemediationMandate; reject any input lacking a resolvable finding_cid on the same owner+target.

Per ADR-2605291500. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: tsukuroi (繕い) — `did:web:tsukuroi.etzhayyim.com` (akuma's constructive sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G3 (no probing) + G7 (dual-sig mandate)
- **Output Lexicon(s)**: com.etzhayyim.tsukuroi.remediationMandate
- **Ceiling**: PROPOSE-ONLY (no merge/deploy) · NO PROBING (akuma finding_cid input only) · DEFENSIVE-ONLY (no exploit/PoC, §2(a)) · NO PLATFORM-HELD KEY (ADR-2605231525) · Murakumo-only inference (ADR-2605215000)
