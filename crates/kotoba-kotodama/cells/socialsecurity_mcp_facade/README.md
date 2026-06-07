# socialsecurity_mcp_facade - §1.16 Social Security pipeline (R0 scaffold)

Stage 6 (MCP expose). Expose the social security over MCP (ADR-0087) so any MCP client (Claude, an agent, a third-party app) can help a human discover and enroll.

- **READ tools** (open): `socialSecurity.declaration` · `socialSecurity.metrics` · `socialSecurity.eligibility` · `socialSecurity.status` (own-data, consent-bound)
- **WRITE tool** (member-signed): `socialSecurity.beginVow` → returns an **unsigned** vow payload for the member's wallet/passkey to sign locally; the signed result re-enters Stage 1 (socialsecurity_vow_intake).

Per ADR-2605302358. R0 scaffold — `cell.py` raises at import time until R1 (Council Lv6+ pipeline ratify + kotoba-kotodama MCP facade registry DID).

- **Pipeline group**: 産土 (ubusuna)
- **Murakumo node (proposed)**: gad
- **Gates**: G3 (beginVow returns unsigned payload; server never signs) · G6 (status = own-data, consent-bound) · G12 (aggregate-only metrics) · G11 (mint/persist gated downstream by vow_intake)
- **Output**: MCP tool registrations (read) + unsigned vow payload (beginVow)
- **Ceiling**: server holds NO key; the write surface only ever returns an unsigned payload signed on the member's device.
