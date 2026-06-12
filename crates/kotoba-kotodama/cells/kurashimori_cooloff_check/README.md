# kurashimori_cooloff_check — kurashimori (R0 scaffold)

compute whether a member's contract is within a statutory cooling-off window
(contract date + type + remedyTarget 日数/起算 → deadline) → `coolingOffAssessment`.
An INFORMATIONAL date computation, NOT legal advice.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G5 (date-computation, NOT a legal opinion — `isLegalOpinion` const false) + G8 (non-fabrication) + G6 (contract detail encrypted)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.coolingOffAssessment
- **Ceiling**: INFORMATIONAL-DATE-COMPUTATION / NOT-A-LEGAL-OPINION (borderline → chigiri+counsel) · verified 日数 only · contract detail only in com.etzhayyim.encrypted.* (ADR-2605181100) · Murakumo-only (ADR-2605215000)
