# tadori_address_label - tadori (R0 scaffold)

aggregate multi-source labels for a list of addresses into label datoms; delegates compute to the malak address_label_pursuit Pregel. External paid sources (OFAC/Tornado/Chainalysis) are feature-flagged INPUTS only, never the system of record.

Per ADR-2605301400. R0 scaffold - `cell.py` raises at import time until T1
(Council Lv6+ >=3 ratify, post 2026-06-19).

- **Actor**: tadori (辿) - `did:web:tadori.etzhayyim.com` (malak's durable-graph sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G4 (open-source) + G9 (Murakumo-only)
- **Output Lexicon(s)**: com.etzhayyim.tadori.traceReport
- **Ceiling**: AUTHORIZED-INVESTIGATION-ONLY (caseMandate anchor) - OPEN-SOURCE (no proprietary chain-analysis SoR) - ON-CHAIN-MONITORABLE (Transparent Force SS1.12) - PII-ENCRYPTED (com.etzhayyim.encrypted.*) - EVIDENCE-ONLY / NO ENFORCEMENT - NO PLATFORM-HELD KEY (ADR-2605231525) - Murakumo-only (ADR-2605215000) - kotoba-only (ADR-2605262130)
