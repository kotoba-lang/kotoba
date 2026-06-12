# toritsugi_draft — toritsugi (R0 scaffold)

assist the member in filling the 様式/フォーム for a procedure and emit an
applicationDraft artifact the member reviews + owns. INPUT-ASSISTANCE, not
作成代理.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G5 (行政書士法 / UPL — input-assist only, never 官公署提出書類の作成代理) + G6 (draft PII only in encrypted DID-bound envelope) + G8 (member must confirm before submission)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.applicationDraft
- **Ceiling**: INPUT-ASSIST-ONLY / NO-作成代理 (the only representable `assistMode` is "input-assist") · PII-ENCRYPTED (com.etzhayyim.encrypted.*, ADR-2605181100; never inline PII) · MEMBER-CONFIRMS (`memberConfirmed`) before any submission · Murakumo-only inference (ADR-2605215000)
