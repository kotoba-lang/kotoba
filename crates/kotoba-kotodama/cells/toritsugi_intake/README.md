# toritsugi_intake — toritsugi (R0 scaffold)

take a member's consent + DID/SBT binding + need/life-event and open a
procedureGuide session for a single procedure. The member is the named
申請者本人 from this point on.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (consent-gated + own-procedure-only) + G4 (member is the named 申請者本人; toritsugi is an unofficial assistant, never an official 自治体 channel)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.procedureGuide
- **Ceiling**: CONSENT-GATED / OWN-PROCEDURE-ONLY · MEMBER-IS-APPLICANT (no impersonation, §2(c)) · kotoba-EAVT-native (ADR-2605262130) · Murakumo-only inference (ADR-2605215000)
