# moushibumi_status_track — moushibumi (R0 scaffold)

track a submitted petition/comment's outcome — 議会 採択/不採択, or an agency's
公示 of 提出意見を考慮した結果及びその理由 (行政手続法 §43) → `statusTrack`.

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R2.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G6 (outcome PII encrypted) + G11 (Transparent Religious Force — track only, aggregate-first, 1 SBT = 1 vote)
- **Output Lexicon(s)**: com.etzhayyim.moushibumi.statusTrack
- **Ceiling**: PII only in com.etzhayyim.encrypted.* (ADR-2605181100) · TRANSPARENT-FORCE / no coercion / aggregate-first · Murakumo-only (ADR-2605215000)
