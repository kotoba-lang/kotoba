# toritsugi_eligibility_match — toritsugi (R0 scaffold)

proactively match a CONSENTING member's OWN life-event/profile against the
available 制度/給付/手続き and raise a benefitMatch ("you may be eligible for X" —
the LINE-公式アカウント notify role). A soft signal only, NEVER an adjudication.

Per ADR-2605312030. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 ratify, post 2026-06-19).

- **Actor**: toritsugi (取次) — `did:web:toritsugi.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (consent-gated + own-data-only) + G5 (no eligibility/legal determination) + G12 (data-minimization)
- **Output Lexicon(s)**: com.etzhayyim.toritsugi.benefitMatch
- **Ceiling**: CONSENT-GATED / OWN-DATA-ONLY (never a third party) · NO-ELIGIBILITY-DETERMINATION (soft signal → guide → chigiri/licensed) · PII only in com.etzhayyim.encrypted.* (G6, ADR-2605181100) · NO fabricated entitlement (G8) · Murakumo-only inference (ADR-2605215000)
