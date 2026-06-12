# §1.16 Social Security pipeline — integration wiring (Layer 4, R0 doc-only)

Documents the three delivery seams of the 産土 (ubusuna) pipeline (ADR-2605302358)
**by reference** to existing substrate. **No live config is created at R0** — wiring
config (MCP `kotoba-kotodama.jsonld`, openmail signer, projection target) is R1 work, gated
on Council ratify. This doc is the build contract for that wiring; nothing here
enables an outward path. The cells' import-time `RuntimeError` (G11) remains the hard gate.

Companion to `SOCIAL-SECURITY-PIPELINE.md` (orchestration). Master: ADR-2605302358.

## Seam 1 — openmail (Stage 3 NOTIFY)

- **Cell**: `socialsecurity_notice`
- **Substrate**: `50-infra/openmail-postage/src/Postage.sol` (ADR-2605172200) + openmail SMTP bridge.
- **Wire (R1)**: `socialsecurity_notice` composes an `app.openmail.message` record → `Postage.payPostage(messageHash, recipientCount)` (USDC from Public Fund treasury, ADR-2605192145) → openmail publishes → SMTP bridge delivers to the member's inbox.
- **Inert at R0**: `OPENMAIL_POSTAGE_SIGNER_DID = None` → cell raises at import; no `payPostage` call, no send.
- **Gate binding**: G5 (opt-in/non-vexatious — record gated on `noticeEmail.consentOptIn=true`), G6 (recipient PII via `noticeEmail.recipientPiiRef` encrypted envelope, never `Postage` calldata), G3 (signer = member/community-operator DID, never platform key).
- **Postage funding note**: postage USDC is drawn from the Public Fund (10% tithe pool, ADR-2605192130), NOT from the member — consistent with N1 (no cash from adherent) and donation-only economics.

## Seam 2 — feed-post membrane (Stages 0 / 4 / 5 OUTREACH / PUBLISH / SOCIAL)

- **Cells**: `socialsecurity_outreach` (0/5), `socialsecurity_publish` (4)
- **Substrate**: feed-post membrane + feed-discover projection (ADR-2605231902), `50-infra/mst-projector/projection/`.
- **Wire (R1)**: cells write `app.bsky.feed.post` (invitation / transparency-metric / declaration) and the PII-free member record + aggregate `socialsecurity.metricReport` to the PDS/MST; feed-discover projects to the read path (kotoba-query at Phase 2.5).
- **Inert at R0**: `FEED_POST_MEMBRANE_PROJECTION_DID = None` (+ `CHARTER_RIDER_SCANNER_DID = None` for outreach) → cells raise at import; `outreachPost.published` / `metricReport` publish default false.
- **Gate binding**: G7 (outreach `adFreeAttest`/`noTrackerAttest`/`noMicrotargetAttest` const true), G1 (Charter Rider §2 scan before publish), G12 (publish aggregate-only — `metricReport.aggregateOnly` const true), G6 (member record PII-free), G13 (Transparent audit datom per publish).
- **Membrane note**: the feed-post membrane (ADR-2605231902) is preserved unchanged; this pipeline is a new producer into it, not a modification.

## Seam 3 — MCP facade (Stage 6 EXPOSE)

- **Cell**: `socialsecurity_mcp_facade`
- **Substrate**: kotoba-kotodama MCP tool facade (ADR-0087); facade actors live under `20-actors/kotoba-kotodama/mcp/<name>/kotoba-kotodama.jsonld` and surface tools at `mcp.etzhayyim.com`.
- **Wire (R1, deployable artifact — NOT created at R0)**: a `kotoba-kotodama.jsonld` for an MCP facade exposing:
  - **read tools** (open): `socialSecurity.declaration`, `socialSecurity.metrics`, `socialSecurity.eligibility`, `socialSecurity.status` (own-data, consent-bound)
  - **write tool** (member-signed): `socialSecurity.beginVow` → returns an **unsigned** vow payload; signed on the member's device; re-enters `socialsecurity_vow_intake`.
  - Target shape (R1):
    ```jsonc
    {
      "@context": "https://etzhayyim.com/ns/kotoba-kotodama/v1",
      "@id": "did:web:socialsecurity.etzhayyim.com",   // or a subpath of etzhayyim.com
      "name": "social-security-mcp",
      "runtimeType": "worker",
      "performerType": "service",
      "profile": { "operator": "etzhayyim", "protocols": ["mcp"],
        "capabilities": ["socialSecurity.declaration","socialSecurity.metrics",
                         "socialSecurity.eligibility","socialSecurity.status",
                         "socialSecurity.beginVow"] },
      "governance": { "raci": "responsible", "classification": "public" }
    }
    ```
- **Inert at R0**: `MCP_FACADE_REGISTRY_DID = None` + `COUNCIL_SS_PIPELINE_RATIFY_TX_HASH = None` → cell raises at import; no facade `kotoba-kotodama.jsonld` exists yet, so no deployable MCP surface.
- **Gate binding**: G3 (`beginVow` returns only an unsigned payload — server never signs), G6 (`status` = own-data, consent-bound), G12 (`metrics` aggregate-only). Any mint/persist from a signed `beginVow` result is gated downstream by `socialsecurity_vow_intake`'s own G11 sentinels.

## Seam 4 — toritate accounting (Stage 2 COMPUTE side-effect)

- **Cell**: `socialsecurity_eligibility` → reuses **existing** toritate cells `toritate_imputed_income_compute` + `toritate_commons_asset_value` (ADR-2605301020 / 2605262900). **No new accounting artifact created** — this is a reference seam.
- **Wire (R1)**: when `socialsecurity_eligibility` emits `socialsecurity.entitlement`, it feeds the in-kind provision into toritate's imputed-income flow (market-equivalent valuation, open method-versioned tables under `20-actors/toritate/valuation/`). Aggregate figures publish via Stage 4 (`socialsecurity.metricReport`); per-member figures stay encrypted (ADR-2605181100).
- **Inert at R0**: `TORITATE_IMPUTED_INCOME_FEED_DID = None` → `socialsecurity_eligibility` raises at import; no accounting write.
- **Gate binding**: G8 (cash≡0 — `entitlement.cashStipendUsdMicros` const 0 is toritate's N1 proof), G12 (aggregate-only — no per-member income leaderboard, ADR-2605301020 §7).
- **Note**: `token/benefit` reuse Adherent SBT (2605172600) + Public Fund (2605192145) + tithe (2605192130) — **no new Solidity** (ADR-2605302358 §6).

## R0 → R1 wiring checklist (what removes each seam's gate)

| Seam | R1 wiring action | Removes |
|---|---|---|
| openmail | set `OPENMAIL_POSTAGE_SIGNER_DID` (member/operator) + confirm Public Fund postage budget | `notice` import gate |
| feed-post | set `FEED_POST_MEMBRANE_PROJECTION_DID` + `CHARTER_RIDER_SCANNER_DID` | `outreach`/`publish` import gates |
| MCP | create `20-actors/kotoba-kotodama/mcp/social-security-mcp/kotoba-kotodama.jsonld` + set `MCP_FACADE_REGISTRY_DID` + `COUNCIL_SS_PIPELINE_RATIFY_TX_HASH` (Lv6+) | `mcp_facade` import gate (read tools only; write still vow-gated) |

**All three remain blocked at R0.** Even with seams wired (R1), the identity-level sentinels (`COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `SYBIL_FRAMEWORK_RATIFY_TX_HASH`) keep real email/post/mint/benefit off until Council Lv7+ §1.16 ratify (post 2026-06-19) — R2.
