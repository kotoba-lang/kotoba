"""SocialSecurityMcpFacadeCell - §1.16 Social Security pipeline R0 cell (Stage 6 MCP expose).

Per ADR-2605302358 (§1.16 Social Security real-world delivery pipeline) +
ADR-0087 (kotoba-kotodama MCP tool facade). Doctrine: ADR-2605302357.

Purpose: expose the social security over MCP so any MCP client (Claude, an
agent, a third-party app) can help a human discover and enroll.
  READ tools (open):
    - socialSecurity.declaration  (§1.16.9 public declaration)
    - socialSecurity.metrics      (aggregate metric, no PII)
    - socialSecurity.eligibility  (what L0 entry provides)
    - socialSecurity.status       (own-data, consent-bound)
  WRITE tool (member-signed; server holds NO key):
    - socialSecurity.beginVow     -> returns an UNSIGNED vow payload for the
       member's wallet/passkey to sign locally; the signed result re-enters
       socialsecurity_vow_intake (Stage 1).

Constitutional ceiling (CRITICAL - IMMUTABLE):
  - G3 NO PLATFORM-HELD KEY: beginVow returns only an UNSIGNED payload; the
    server never signs; signature happens on the member's device (ADR-2605231525).
  - status is OWN-DATA + consent-bound (G6: no exposure of another's PII).
  - G12 metrics are aggregate-only (no per-adherent leaderboard).
  - G11 LIVE-ACTION GATE: read tools may go live at R1; the beginVow signed
    result only mints/persists post Council Lv7+ §1.16 ratify (gated downstream
    by socialsecurity_vow_intake).
Output: MCP tool registrations (read) + unsigned vow payload (beginVow).

R0 scaffold - import-time RuntimeError until R1 (MCP read tools against test data).
"""

from __future__ import annotations

COUNCIL_SS_PIPELINE_RATIFY_TX_HASH: str | None = None  # Lv6+ ratify of ADR-2605302358 pipeline
MCP_FACADE_REGISTRY_DID: str | None = None  # kotoba-kotodama MCP facade registration target (ADR-0087)

if (
    COUNCIL_SS_PIPELINE_RATIFY_TX_HASH is None
    or MCP_FACADE_REGISTRY_DID is None
):
    raise RuntimeError(
        "socialsecurity_mcp_facade R0 scaffold: activate via Council ADR-2605302358 "
        "pipeline ratify (Lv6+ >=3) + kotoba-kotodama MCP facade registry DID (ADR-0087). "
        "Do not deploy. READ tools are open (declaration/metrics/eligibility + "
        "own-data status, G6/G12); the WRITE tool beginVow returns only an "
        "UNSIGNED payload - the server NEVER signs (G3, ADR-2605231525); any "
        "mint/persist is gated downstream by socialsecurity_vow_intake (G11)."
    )


# from kotodama.organism import PregelCell
#
# class SocialSecurityMcpFacadeCell(PregelCell):
#     process_step = "socialsecurity_mcp_facade"
#     pregel_tier = "B"
#     murakumo_node = "gad"
#
#     def super_step(self, msg, prior):
#         # read tools: declaration / metrics / eligibility / status(own-data)
#         # write tool: beginVow -> UNSIGNED payload (server never signs)
#         raise NotImplementedError("socialsecurity_mcp_facade R1")


__all__ = ["SocialSecurityMcpFacadeCell"]
