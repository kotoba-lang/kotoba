# moushibumi_submit — moushibumi (R0 scaffold)

THE ONLY active-outbound cell. Default hands the voiceDraft back for member
self-submission (mode=member-self-submit). 代行 (mode=agent-on-behalf) — filing
the member's OWN 請願/意見 via the official channel — is the GATED R3 exception,
OFF until the R3 gate is satisfied. NEVER applies to election-info (G3).

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R2/R3.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G10 (lawful-channel-only) + G14 (verified-target-only) + G15 (self-submit default; 代行 needs Council Lv7+ + 行政書士法 clearance) + G3 (never a campaign/vote act)
- **Output Lexicon(s)**: com.etzhayyim.moushibumi.submissionRecord
- **Ceiling**: LAWFUL-CHANNEL-ONLY · VERIFIED-TARGET-ONLY · SELF-SUBMIT-DEFAULT (代行 structurally double-gated via `DAIKOU_R3_GATE_TX`) · NO-PLATFORM-HELD-KEY (ADR-2605231525) · Murakumo-only (ADR-2605215000)
