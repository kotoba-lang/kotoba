# tadori_tx_trace - tadori (R0 scaffold)

trace a target address (wallet deep-inspect) into tx/addr/cluster datoms; delegates the paginated fetch + classification compute to the malak wallet_deep_inspect_pursuit Pregel (ADR-2605152000).

Per ADR-2605301400. R0 scaffold - `cell.py` raises at import time until T1
(Council Lv6+ >=3 ratify, post 2026-06-19).

- **Actor**: tadori (辿) - `did:web:tadori.etzhayyim.com` (malak's durable-graph sibling)
- **Murakumo node (proposed)**: levi
- **Gates**: G9 (Murakumo-only) + G11 (kotoba-only)
- **Output Lexicon(s)**: com.etzhayyim.tadori.traceReport
- **Ceiling**: AUTHORIZED-INVESTIGATION-ONLY (caseMandate anchor) - OPEN-SOURCE (no proprietary chain-analysis SoR) - ON-CHAIN-MONITORABLE (Transparent Force SS1.12) - PII-ENCRYPTED (com.etzhayyim.encrypted.*) - EVIDENCE-ONLY / NO ENFORCEMENT - NO PLATFORM-HELD KEY (ADR-2605231525) - Murakumo-only (ADR-2605215000) - kotoba-only (ADR-2605262130)
