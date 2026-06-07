# kizashi_triage_referral — kizashi (R0 scaffold)

route a non-diagnostic attribution to the clinical-adjudication actors
(mitate / iyashi / kokoro) and escalate red-flag signs immediately. kizashi can
only REFER — it never closes a clinical loop itself.

Per ADR-2605312700. R0 scaffold — `cell.py` raises at import time until R2
(Council Lv6+ ≥4 + 30-day public + mitate R1 active for the shared
emergency-keyword lexicon).

- **Actor**: kizashi (兆) — `did:web:kizashi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: **G5 (emergency red-flag → immediate 受診/救急, never "wait for next scan")** + G3 (refer-only; targetActor const-enum {mitate, iyashi, kokoro}) + G6 (consent to share provenance) + G14 (Murakumo-only)
- **Output Lexicon(s)**: com.etzhayyim.kizashi.triageReferral
- **Ceiling**: REFER-ONLY (G3) + EMERGENCY-ESCALATION (G5) is constitutional — routes to mitate/iyashi/kokoro, never self-treats · Murakumo-only inference (ADR-2605215000)
