# moushibumi_compose — moushibumi (R0 scaffold)

pull the chigiri template + resolved participationTarget and help the member
draft a 請願書 / 陳情 / public-comment opinion → `voiceDraft`. Drafting-assist only.

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G5 (行政書士法/UPL — drafting-assist, no 作成代理) + G6 (PII/opinion encrypted) + G8 (member confirms) + G3 (neutral)
- **Output Lexicon(s)**: com.etzhayyim.moushibumi.voiceDraft
- **Ceiling**: DRAFTING-ASSIST-ONLY / NO-作成代理 · draft only in com.etzhayyim.encrypted.* (ADR-2605181100; APPI special-care) · MEMBER-CONFIRMS before submission · Murakumo-only (ADR-2605215000)
