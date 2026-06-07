# toritsugi_guide — toritsugi (R0 scaffold)

pull the chigiri procedure template + the resolved toritsugi.procedure and render
a step-by-step 案内 + 必要書類 checklist into the member's procedureGuide session.
Guidance only.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G5 (行政書士法 / UPL boundary — no advice + no 作成代理) + G8 (non-fabrication — cite 根拠法令 + provenance)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.procedureGuide
- **Ceiling**: 行政書士法/UPL-BOUNDARY (情報提供 + 案内 + 伴走 only; legal/tax characterization + 作成代理 + appeals → chigiri + licensed counsel; tax → toritate) · NON-FABRICATION · pulls templates from the chigiri template feed only · Murakumo-only inference (ADR-2605215000)
