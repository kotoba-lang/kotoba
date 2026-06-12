# kurashimori_compose — kurashimori (R0 scaffold)

pull the chigiri template + resolved remedyTarget and help the member draft a
cooling-off 通知 / refund demand / complaint → `remedyDraft`. Drafting-assist only.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G5 (drafting-assist, no 作成代理) + G10 (lawful, non-threatening) + G6 (draft encrypted) + G8 (member confirms)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.remedyDraft
- **Ceiling**: DRAFTING-ASSIST-ONLY / NO-作成代理 · lawful non-harassment language · draft only in com.etzhayyim.encrypted.* (ADR-2605181100) · MEMBER-CONFIRMS · Murakumo-only (ADR-2605215000)
