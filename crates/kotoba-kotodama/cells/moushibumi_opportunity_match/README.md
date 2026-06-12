# moushibumi_opportunity_match — moushibumi (R0 scaffold)

proactively + NEUTRALLY match a consenting member's declared interest/locale
against open participation opportunities → `participationMatch`. Never a
candidate/party recommendation or vote prompt.

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (politically neutral) + G4 (consent + own-data-only) + G6 (PII/opinion encrypted) + G12 (no opinion-profiling)
- **Output Lexicon(s)**: com.etzhayyim.moushibumi.participationMatch
- **Ceiling**: NEUTRAL signal only (no partisan framing/vote prompt) · CONSENT-GATED / OWN-DATA-ONLY · PII/opinion only in com.etzhayyim.encrypted.* (ADR-2605181100) · Murakumo-only (ADR-2605215000)
