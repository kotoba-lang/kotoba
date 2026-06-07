# socialsecurity_notice - §1.16 Social Security pipeline (R0 scaffold)

Stage 3 (NOTIFY). Send a **real email** to a consented member via openmail (ADR-2605172200): welcome + vow confirmation (CID + SBT id) + how to receive Level-0 in-kind benefits.

Per ADR-2605302358. R0 scaffold — `cell.py` raises at import time until R2 (Council Lv7+ §1.16 ratify + openmail postage signer DID).

- **Pipeline group**: 産土 (ubusuna)
- **Murakumo node (proposed)**: naphtali
- **Gates**: G5 (opt-in / non-vexatious / unsubscribe-honored) · G6 (PII in encrypted envelope) · G3 (member/operator-signed, no platform mail key) · G11 (sent=false pre-ratify)
- **Output Lexicon(s)**: com.etzhayyim.socialsecurity.noticeEmail
- **Ceiling**: opt-in only; unsubscribe always honored; on-chain postage (Postage.sol), Public-Fund-funded; PII only via encrypted envelope.
