# kurashimori_escalation — kurashimori (R0 scaffold)

when self-help stalls, route the member to the lawful external forum (消費生活
センター / 消費者ホットライン 188 / ADR / chigiri + licensed counsel) →
`escalationReferral`.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R2.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G5 (route, NOT represent — representation/characterization happen at the destination) + G6 (PII encrypted)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.escalationReferral
- **Ceiling**: ROUTE-NOT-REPRESENT (代理 → chigiri+licensed) · PII only in com.etzhayyim.encrypted.* (ADR-2605181100) · Murakumo-only (ADR-2605215000)
