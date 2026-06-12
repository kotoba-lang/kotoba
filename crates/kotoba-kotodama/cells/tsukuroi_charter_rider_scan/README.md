# tsukuroi_charter_rider_scan — tsukuroi (R0 scaffold)

run sensors.charter_rider.scan over the generated patch; reject §2(a)..(h) violations and any offensive/PoC content before validation.

Per ADR-2605291500. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: tsukuroi (繕い) — `did:web:tsukuroi.etzhayyim.com` (akuma's constructive sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G1 (Charter Rider scan) + G5 (defensive-only / no exploit)
- **Output Lexicon(s)**: com.etzhayyim.tsukuroi.patchProposal
- **Ceiling**: PROPOSE-ONLY (no merge/deploy) · NO PROBING (akuma finding_cid input only) · DEFENSIVE-ONLY (no exploit/PoC, §2(a)) · NO PLATFORM-HELD KEY (ADR-2605231525) · Murakumo-only inference (ADR-2605215000)
