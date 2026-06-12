# kurashimori_intake — kurashimori (R0 scaffold)

take a member's consent + DID/SBT + the consumer matter (OWN) and open a
`complaintSession`. The member is the named complainant.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (consent + own-matter-only) + G4 (transparent; not an official センター)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.complaintSession
- **Ceiling**: CONSENT-GATED / OWN-MATTER-ONLY · unofficial assistant · kotoba-EAVT-native (ADR-2605262130) · Murakumo-only (ADR-2605215000)
