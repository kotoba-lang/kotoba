# tadori_case_intake - tadori (R0 scaffold)

open/validate an authorized caseMandate (authorizationRef + authority signature); reject any live write lacking an active case anchor (Phase 0 dry-run otherwise).

Per ADR-2605301400. R0 scaffold - `cell.py` raises at import time until T1
(Council Lv6+ >=3 ratify, post 2026-06-19).

- **Actor**: tadori (辿) - `did:web:tadori.etzhayyim.com` (malak's durable-graph sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G3 (authorized-investigation-only) + G5 (transparent-force log)
- **Output Lexicon(s)**: com.etzhayyim.tadori.caseMandate
- **Ceiling**: AUTHORIZED-INVESTIGATION-ONLY (caseMandate anchor) - OPEN-SOURCE (no proprietary chain-analysis SoR) - ON-CHAIN-MONITORABLE (Transparent Force SS1.12) - PII-ENCRYPTED (com.etzhayyim.encrypted.*) - EVIDENCE-ONLY / NO ENFORCEMENT - NO PLATFORM-HELD KEY (ADR-2605231525) - Murakumo-only (ADR-2605215000) - kotoba-only (ADR-2605262130)
