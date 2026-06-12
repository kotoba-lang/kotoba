# kurashimori_send — kurashimori (R0 scaffold)

THE ONLY active-outbound cell. Default hands the remedyDraft back for member
self-send (mode=member-self-send). 代行 (mode=agent-on-behalf) — sending the
member's OWN notice via a lawful channel — is the GATED R3 exception, OFF until
the R3 gate is satisfied.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R2/R3.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G10 (lawful-channel-only + non-harassment) + G14 (verified-remedy-only) + G15 (self-send default; 代行 needs Council Lv7+ + 司法書士法/行政書士法 clearance)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.dispatchRecord
- **Ceiling**: LAWFUL-CHANNEL-ONLY + NON-HARASSMENT (never 威迫) · VERIFIED-REMEDY-ONLY · SELF-SEND-DEFAULT (代行 structurally double-gated via `DAIKOU_R3_GATE_TX`) · NO-PLATFORM-HELD-KEY (ADR-2605231525) · Murakumo-only (ADR-2605215000)
