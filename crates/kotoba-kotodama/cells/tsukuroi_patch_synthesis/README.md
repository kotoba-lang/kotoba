# tsukuroi_patch_synthesis — tsukuroi (R0 scaffold)

draft a candidate DEFENSIVE fix diff for the finding via Murakumo-only LLM (judah LiteLLM 127.0.0.1:4000); never emit exploit/PoC code.

Per ADR-2605291500. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: tsukuroi (繕い) — `did:web:tsukuroi.etzhayyim.com` (akuma's constructive sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G5 (defensive-only) + G6 (scoped write) + G10 (Murakumo-only)
- **Output Lexicon(s)**: com.etzhayyim.tsukuroi.patchProposal
- **Ceiling**: PROPOSE-ONLY (no merge/deploy) · NO PROBING (akuma finding_cid input only) · DEFENSIVE-ONLY (no exploit/PoC, §2(a)) · NO PLATFORM-HELD KEY (ADR-2605231525) · Murakumo-only inference (ADR-2605215000)
