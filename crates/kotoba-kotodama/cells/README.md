# kotoba-kotodama/cells — Religious-Corp Pregel Cell Catalog

This directory contains the Pregel (LangGraph) cells that implement
**etzhayyim religious-corp governance, enforcement, and stewardship** per
[ADR-2605192415](../../../90-docs/adr/2605192415-etzhayyim-religious-corp-daemon-architecture.md).

These cells are **Tier B (Per-Domain)** in the 3-layer actor hierarchy:

- **Tier A — Per-Adherent**: `PhenotypeAgent` per SBT (code-generated per [ADR-2605171300](../../../90-docs/adr/2605171300-open-unispsc-generative-agent-fleet.md) pattern). Lives in `unispsc_agents/` style directory; not catalogued here.
- **Tier B — Per-Domain**: cells in this directory. Each cell has a leader + N replicas across the [Murakumo Mac mini fleet](../../../50-infra/murakumo/fleet.toml).
- **Tier C — Per-Decision**: `CouncilDeliberationCell` (generic) instantiated per attestation request.

## Catalog (15 cells)

| Cell | Domain | Trigger | Murakumo node (leader) | Solidity contracts |
|---|---|---|---|---|
| [`charter_attestation_request/`](charter_attestation_request/) | Charter Compliance | MST listener | naphtali | ChartersComplianceRegistry |
| `charter_attestation_finalization/` | Charter Compliance | timer + MST listener | naphtali | ChartersComplianceRegistry |
| `charter_rehabilitation/` | Charter Compliance | MST listener | naphtali | ChartersComplianceRegistry |
| [`land_donation_processing/`](land_donation_processing/) | Land Trust | MST listener | judah | LandRegistry, PublicLandRegistry |
| `land_stewardship_monitoring/` | Land Trust | monthly cron | simeon | LandRegistry |
| `land_dispute_resolution/` | Land Trust | MST listener | judah | LandRegistry |
| [`steward_succession/`](steward_succession/) | Land Trust | MST listener + heartbeat | judah | LandRegistry |
| `eligibility/` (existing, [ADR-2605172300](../../../90-docs/adr/2605172300-etzhayyim-bi-asset-substrate.md)) | Economic | 6-hour cron | zebulun | KishaStream, Phenotype |
| [`treasury_rebalance/`](treasury_rebalance/) | Economic | monthly cron | zebulun | TreasuryMirror, Governance |
| `public_fund_grant/` ([ADR-2605192145](../../../90-docs/adr/2605192145-etzhayyim-public-fund-architecture.md)) | Economic | MST listener | zebulun | PublicFundGovernance |
| [`tithe_routing/`](tithe_routing/) | Economic | MST listener | zebulun | TitheRouter |
| `force_authorization/` | Force | MST listener | benjamin | ForceAuthorization |
| `force_log_monitoring/` | Force | daily cron + MST listener | benjamin | ForceAuthorization |
| [`ethics_content_classifier/`](ethics_content_classifier/) | Ethics | synchronous API | benjamin | (no Solidity, off-chain) |
| `adherent_attestation/` | Membership | MST listener | levi | AdherentRegistry, EtzhayyimMembership |
| `council_level_advancement/` | Membership | weekly cron | levi | EtzhayyimMembership |
| [`council_deliberation/`](council_deliberation/) (generic, **Tier C**) | Council | escalation from other cells | levi (orchestrator) | ChartersComplianceRegistry, ForceAuthorization, others |

## L5 routing-around cells (2026-05-25 wave, scaffold-only)

Per [ADR-2605242330](../../../90-docs/adr/2605242330-gov-procedure-pregel-mcp-coverage.md) §3.5 and the L5 ladder ADRs below, three cells operationalize the religious-corp's *parallel substrate* for state functions within the religious boundary (per [ADR-2605192100](../../../90-docs/adr/2605192100-etzhayyim-mission-charter.md) §1.12). All three ship as **Council-attestation-gated scaffolds**: their `cell.py` raises `RuntimeError` at import time until Council ratifies activation. They are listed here for review and Council-bootstrap preparation — they are NOT live.

| Cell | State function substituted | Gate count | Open Council questions | ADR |
|---|---|---|---|---|
| [`member_registry/`](member_registry/) | 住民登録 (resident registration) | 1 (attestation tx) | 0 | [ADR-2605250100](../../../90-docs/adr/2605250100-l5-routing-around-member-registry-cell.md) |
| [`religious_marriage/`](religious_marriage/) | 婚姻届 (marriage certificate) | 2 (attestation + constitutional resolution) | 3 (gender / polygamy / cross-religion) | [ADR-2605250200](../../../90-docs/adr/2605250200-l5-religious-marriage-cell.md) |
| [`religious_corp_taxation/`](religious_corp_taxation/) | 法人税申告 (corporate tax filing) — INTERNAL substrate only, not a state-tax discharge | 3 (+ legal counsel opinion CID) | 4 (legal-status / cross-jurisdiction / Council-veto / personal-tax-advisory) | [ADR-2605250300](../../../90-docs/adr/2605250300-l5-religious-corp-taxation-cell.md) |

### L5 constitutional invariants

- L5 cells operate ONLY within the religious boundary. Records they emit have no state-recognised legal force.
- Each new L5 cell requires its own ADR + Council attestation. No L5 cell ships activated.
- L5 cells substitute for adherents ONLY. Non-adherents are not in scope.
- Charter Rider §2(a)-(h) prohibitions apply to L5 substrate (commercial activity ban is universal).
- The 4-th state function (出生 / 死亡 / 戸籍) is NOT on the L5 roadmap — those need a separate ADR resolving "non-consenting minor adherent" and "SBT revocation on death" semantics first.

## Per-cell structure

Each cell directory contains:

```
{cell_name}/
├── README.md                 # cell-specific docs (input/output Lexicon, state schema)
├── cell.py                   # LangGraph StateGraph definition (entrypoint)
├── nodes.py                  # individual node functions
├── prompts/                  # LLM prompts (if cell uses LLM)
│   └── ...
└── tests/
    └── test_cell.py
```

## Common dependencies

All cells use:

- **Checkpointing**: `kotodama.checkpointer.MstCheckpointSaver` ([ADR-2605191559](../../../90-docs/adr/2605191559-ameno-mst-checkpointer-stage-2-activation.md))
- **MST listener**: `kotodama.listener.MstListener` (subscribes to specific Lexicons)
- **Web3 ports**: `kotodama.eligibility.web3_ports.{GethPrivatePort, BaseL2Port}` ([ADR-2605172300](../../../90-docs/adr/2605172300-etzhayyim-bi-asset-substrate.md) §3)
- **Cell key**: rotated quarterly per [ADR-2605192415](../../../90-docs/adr/2605192415-etzhayyim-religious-corp-daemon-architecture.md) §9

## Cell key rotation

```bash
# Quarterly (or on Council Lv6+ request)
kotoba-kotodama cell rotate-key --cell-all --council-sigs <sig1>,<sig2>,<sig3>
```

## Common deployment commands (from etzhayyim-cli)

```bash
# Deploy a cell to its leader node (per fleet.toml)
kotoba-kotodama cell deploy --cell CharterAttestationRequestCell

# Check health of all cells
kotoba-kotodama cell health --all

# Stream logs from a cell
kotoba-kotodama cell logs --cell LandDonationProcessingCell --tail

# Inspect current checkpoint state
kotoba-kotodama cell state --cell EligibilityCell --thread-id <id>
```

## See also

- [`50-infra/murakumo/fleet.toml`](../../../50-infra/murakumo/fleet.toml) — node ↔ cell placement
- [`70-tools/etzhayyim-cli/`](../../../70-tools/etzhayyim-cli/) — `kotoba-kotodama cell ...` commands
- [`60-apps/etzhayyim-cell-fleet-dashboard/`](../../../60-apps/etzhayyim-cell-fleet-dashboard/) — monitoring SPA
- [ADR-2605192415](../../../90-docs/adr/2605192415-etzhayyim-religious-corp-daemon-architecture.md) — master design
- [ADR-2605171800](../../../90-docs/adr/2605171800-langgraph-mst-ipfs-l2-anchor-pipeline.md) — checkpoint pipeline foundation
