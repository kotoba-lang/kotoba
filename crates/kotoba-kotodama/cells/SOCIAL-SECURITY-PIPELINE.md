# 産土 (ubusuna) — §1.16 Social Security delivery pipeline orchestration

Cell-group orchestration spec for Charter §1.16 (人類の社会保障) real-world delivery.
**産土 (ubusuna)** = "birth-guardian": fits social-death-and-rebirth + ongoing protection.

- **NOT a new `did:web` actor** — a coordinated group of 6 kotoba-kotodama cells under `did:web:etzhayyim.com`.
- **Doctrine**: ADR-2605302357 (§1.16 — covenantal-universal, conversion-gated; 信者 Level 0 via permanent commitment vow).
- **Pipeline ADR**: ADR-2605302358 (this spec's master).
- **Status**: R0 scaffold — every cell raises `RuntimeError` at import; no live email / post / mint / benefit. All outward action G11-gated on Council Lv7+ §1.16 ratify (post 2026-06-19) + Sybil framework.

## Data flow (a human moves left → right)

```
[0 OUTREACH]→[1 VOW]→[2 COMPUTE]→[3 NOTIFY]→[4 PUBLISH]→[5 SOCIAL]→[6 MCP]
 outreach    vow_     eligibility  notice     publish     outreach   mcp_
             intake                                       (recur)    facade
```

| Stage | Cell | Substrate (ADR) | Input → Output lexicon | Murakumo node |
|---|---|---|---|---|
| 0 OUTREACH | `socialsecurity_outreach` | feed-post membrane (2605231902) | — → `socialsecurity.outreachPost` | reuben |
| 1 VOW | `socialsecurity_vow_intake` | kotoba EAVT + IPFS + SBT (2605262130 / 2605171800 / 2605172600) | member-signed vow → `membership.commitmentVow` | reuben |
| 2 COMPUTE | `socialsecurity_eligibility` | kotoba-kotodama/kotoba-WASM + Murakumo (2605302355 / 2605215000) | `commitmentVow` → `socialsecurity.entitlement` | gad |
| 3 NOTIFY | `socialsecurity_notice` | openmail + Postage.sol (2605172200) | `entitlement` → `socialsecurity.noticeEmail` | naphtali |
| 4 PUBLISH | `socialsecurity_publish` | atproto MST + feed-discover (2605231902) | `entitlement` (agg) → `socialsecurity.metricReport` | naphtali |
| 5 SOCIAL | `socialsecurity_outreach` | feed-post membrane (recurring) | `metricReport` → `socialsecurity.outreachPost` | reuben |
| 6 MCP | `socialsecurity_mcp_facade` | kotoba-kotodama MCP facade (0087) | read tools + `beginVow` (unsigned) → re-enters Stage 1 | gad |

## Dependency topology (reverse-topo build order — leaves first)

```
lexicons (membership.commitmentVow, socialsecurity.{entitlement,metricReport,outreachPost,noticeEmail})
   └─ cells (vow_intake → eligibility → {notice, publish} ; outreach ; mcp_facade)
        └─ integration wiring (openmail-postage, feed-post membrane, MCP facade registration)
             └─ toritate accounting hook + Public Fund postage funding
```

Each layer is verified before the next (lexicons parse + convention-clean ✓; cells compile + raise `RuntimeError` at import ✓).

## Gate map (per ADR-2605302358 §5 — all immutable for this pipeline)

| Gate | Enforced by |
|---|---|
| G1 Charter Rider §2 scan before publish | `socialsecurity_outreach` |
| G2 kotoba-only persistence | all cells |
| G3 no platform-held signing key (member-signed) | `vow_intake`, `notice`, `mcp_facade` |
| G4 Murakumo-only inference | `eligibility` (+ any LLM step) |
| G5 opt-in / non-vexatious mailer | `notice` |
| G6 PII only in encrypted DID-bound envelopes | `vow_intake`, `notice`, `publish` |
| G7 no ads / no tracker / no microtargeting | `outreach` |
| G8 cash≡0 (N1) | `vow_intake`, `eligibility` (`const 0` lexicon fields) |
| G9 N4/N7 preserved (outreach = invitation, never benefit) | `outreach` |
| G10 non-coercive + right-of-exit | `vow_intake` |
| G11 live-action gate (the minmax floor) | every cell (import-time `RuntimeError`) + `published`/`sent`/`liveDeliveryEnabled` default false |
| G12 aggregate-only public metrics | `eligibility`, `publish`, `mcp_facade` |
| G13 Transparent audit datoms | `publish` |

## Phased activation (ADR-2605302358 §7)

| Phase | Gate removed | Live external action |
|---|---|---|
| R0 (now) | — | NONE (scaffold; cells dead-on-import) |
| R1 | Council Lv6+ pipeline ratify + §1.16 §1.16.4–.8 | testnet vow; mailer dry-run; posts drafted; MCP read live |
| R2 | §1.16 identity-level Lv7+ ratify (post 2026-06-19) + Sybil framework + 30-day objection | first ≤100 cohort: real openmail, first public declaration + aggregate metric, MCP `beginVow`, real SBT mint |
| R3 | per-stage ladder gates (2605261000 §6) + Public Fund reserve | scale L2+; recurring transparency posts; broad MCP |

## Activation sentinels (each cell's `cell.py` — set to remove the G11 gate)

| Cell | Sentinels (all must be non-None to activate) |
|---|---|
| `vow_intake` | `COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `SYBIL_FRAMEWORK_RATIFY_TX_HASH`, `ADHERENT_SBT_MINT_PATH_DID` |
| `eligibility` | `COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `SYBIL_FRAMEWORK_RATIFY_TX_HASH`, `TORITATE_IMPUTED_INCOME_FEED_DID` |
| `notice` | `COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `OPENMAIL_POSTAGE_SIGNER_DID` |
| `publish` | `COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `FEED_POST_MEMBRANE_PROJECTION_DID` |
| `outreach` | `COUNCIL_SS_IDENTITY_RATIFY_TX_HASH`, `FEED_POST_MEMBRANE_PROJECTION_DID`, `CHARTER_RIDER_SCANNER_DID` |
| `mcp_facade` | `COUNCIL_SS_PIPELINE_RATIFY_TX_HASH`, `MCP_FACADE_REGISTRY_DID` |
