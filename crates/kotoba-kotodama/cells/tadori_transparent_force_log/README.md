# tadori_transparent_force_log - tadori (R0 scaffold)

emit an on-chain-anchored Transparent Force audit datom per case action (Charter SS1.12 + ADR-2605192315). tadori is evidence-producing only; enforcement routes via yabai + Council.

Per ADR-2605301400. R0 scaffold - `cell.py` raises at import time until T1
(Council Lv6+ >=3 ratify, post 2026-06-19).

- **Actor**: tadori (辿) - `did:web:tadori.etzhayyim.com` (malak's durable-graph sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G5 (on-chain-monitorable) + G7 (evidence-only, not enforcement)
- **Output Lexicon(s)**: com.etzhayyim.tadori.caseMandate
- **Ceiling**: AUTHORIZED-INVESTIGATION-ONLY (caseMandate anchor) - OPEN-SOURCE (no proprietary chain-analysis SoR) - ON-CHAIN-MONITORABLE (Transparent Force SS1.12) - PII-ENCRYPTED (com.etzhayyim.encrypted.*) - EVIDENCE-ONLY / NO ENFORCEMENT - NO PLATFORM-HELD KEY (ADR-2605231525) - Murakumo-only (ADR-2605215000) - kotoba-only (ADR-2605262130)
