# toritsugi_procedure_registry — toritsugi (R0 scaffold)

maintain + resolve the coded government/municipal procedure catalog
(窓口 / 所管 / オンライン申請URL / 必要書類 / 様式 / 手数料 / 法定処理期間 /
根拠法令 / channel) and enforce the G14 verification gate.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com` (citizen-facing government-procedure concierge; service-delivery counterpart to danjo/himotoki)
- **Murakumo node (proposed)**: reuben
- **Gates**: G8 (non-fabrication — cite 根拠法令 + provenance) + G14 (verified-procedure-only)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.procedure
- **Ceiling**: NON-FABRICATION (never invent 手続き/様式/根拠法令/手数料/期限) · VERIFIED-PROCEDURE-ONLY gate (unverified-seed/stale ⇒ no live submission) · kotoba-EAVT-native (ADR-2605262130, no RisingWave) · Murakumo-only inference (ADR-2605215000)
