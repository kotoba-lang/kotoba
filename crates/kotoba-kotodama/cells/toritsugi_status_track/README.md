# toritsugi_status_track — toritsugi (R0 scaffold)

track a submitted procedure's 処理状況 + 法定処理期間 clock, take in the
result/結果通知, and on refusal/partial outcome route a lawful appeal
(不服申立 / 審査請求) via chigiri.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R2
(Council Lv6+ ≥4 + 30-day public comment).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G6 (result/結果通知 PII only in encrypted DID-bound envelope) + G11 (Transparent Religious Force — track + appeal only, no coercion; lawful 不服申立 via chigiri)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.statusTrack
- **Ceiling**: PII-ENCRYPTED (com.etzhayyim.encrypted.*, ADR-2605181100; never inline PII) · TRANSPARENT-FORCE / LAWFUL-APPEAL-ONLY (審査請求 via chigiri) · Murakumo-only inference (ADR-2605215000)
