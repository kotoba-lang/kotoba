# tsukuroi_patch_validation — tsukuroi (R0 scaffold)

build + test the candidate patch inside the egress-restricted tsukuroi-validate namespace; the patch is NEVER executed against the live target.

Per ADR-2605291500. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: tsukuroi (繕い) — `did:web:tsukuroi.etzhayyim.com` (akuma's constructive sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G9 (sandbox validation, never live target)
- **Output Lexicon(s)**: com.etzhayyim.tsukuroi.patchValidationResult
- **Ceiling**: PROPOSE-ONLY (no merge/deploy) · NO PROBING (akuma finding_cid input only) · DEFENSIVE-ONLY (no exploit/PoC, §2(a)) · NO PLATFORM-HELD KEY (ADR-2605231525) · Murakumo-only inference (ADR-2605215000)
