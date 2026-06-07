# tsukuroi_closure_verification — tsukuroi (R0 scaffold)

after a human owner merges, request an akuma re-probe of the same finding and emit a closure attestation only on owner-merge + re-probe pass.

Per ADR-2605291500. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: tsukuroi (繕い) — `did:web:tsukuroi.etzhayyim.com` (akuma's constructive sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G11 (closure: akuma re-probe pass + owner human merge)
- **Output Lexicon(s)**: com.etzhayyim.tsukuroi.closureAttestation
- **Ceiling**: PROPOSE-ONLY (no merge/deploy) · NO PROBING (akuma finding_cid input only) · DEFENSIVE-ONLY (no exploit/PoC, §2(a)) · NO PLATFORM-HELD KEY (ADR-2605231525) · Murakumo-only inference (ADR-2605215000)
