# toritsugi_submit — toritsugi (R0 scaffold)

THE ONLY active-outbound cell. Default hands the applicationDraft back to the
member for self-submission (mode=member-self-submit). The 代行
(mode=agent-on-behalf) path — filing the member's OWN procedure via the official
channel — is the GATED R3 exception and is OFF until the R3 gate is satisfied.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R2
(member-self-submit) / R3 (代行).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G10 (lawful-channel-only) + G14 (verified-procedure-only) + G15 (member-self-submission default; 代行 needs per-submission consent + 行政書士法 clearance + Council Lv7+)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.submissionRecord
- **Ceiling**: LAWFUL-CHANNEL-ONLY (only external mutation = a lawful submission via an official channel with member authorization) · VERIFIED-PROCEDURE-ONLY · SELF-SUBMIT-DEFAULT (代行 structurally double-gated via `DAIKOU_R3_GATE_TX`) · NO-PLATFORM-HELD-KEY (ADR-2605231525, member/community-operator-signed) · Murakumo-only inference (ADR-2605215000)
