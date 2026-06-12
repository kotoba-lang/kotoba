# moushibumi_intake — moushibumi (R0 scaffold)

take a member's consent + DID/SBT + intent and open a `participationSession` for
a single 請願/陳情 or パブリックコメント act. The member is the named
請願者/意見提出者本人.

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G4 (consent + own-voice-only) + G3 (political neutrality)
- **Output Lexicon(s)**: com.etzhayyim.moushibumi.participationSession
- **Ceiling**: CONSENT-GATED / OWN-VOICE-ONLY · no partisan steering · kotoba-EAVT-native (ADR-2605262130) · Murakumo-only (ADR-2605215000)
