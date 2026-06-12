# charter_attestation_request — Pregel Cell

**Trigger**: MST listener on `com.etzhayyim.apps.etzhayyim.charter-attestation-request`

**Effect**: LLM pre-analysis → Council Lv6+ dispatch → on ≥3 signatures → ChartersComplianceRegistry.attestNonAligned() tx on Base L2 + AT Record

**Solidity contracts**: [`50-infra/etzhayyim-charters-compliance/`](../../../../50-infra/etzhayyim-charters-compliance/)

**Murakumo placement**:
- Leader: `naphtali`
- Replicas: `asher` (failover)

**Per ADR**: [2605192230](../../../../90-docs/adr/2605192230-etzhayyim-three-tier-enforcement-implementation.md) (Three-Tier Enforcement) + [2605192200](../../../../90-docs/adr/2605192200-etzhayyim-ip-free-release-charter-rider.md) (Charter Rider v2.0)

## State machine

```
[MST event: charter-attestation-request]
  → load_request
  → validate_evidence
  → llm_analyze (Claude Sonnet 4.6, or Murakumo Gemma fallback)
    │
    ├─ forward_to_council → dispatch_to_council → collect_signatures (fixed-point) → quorum (≥3) → emit_onchain → emit_at_record → END
    ├─ request_more_evidence → emit_at_record (status: pending) → END
    └─ reject_unfounded → emit_at_record (status: rejected) → END
```

## State schema

See `cell.py` `CharterAttestationRequestState`.

## Checkpointing

Persists via `kotodama.checkpointer.MstCheckpointSaver` (per [ADR-2605191559](../../../../90-docs/adr/2605191559-ameno-mst-checkpointer-stage-2-activation.md)).

The graph **pauses** at `collect_signatures` until Council Lv6+ signatures arrive. New signature events re-enter the node with the updated `council_signatures` accumulator (LangGraph reducer = `add` to list).

## Running

```bash
# Single invocation (testing)
kotoba-kotodama cell invoke --cell CharterAttestationRequestCell --input <request-uri>

# As daemon (production)
kotoba-kotodama cell deploy --cell CharterAttestationRequestCell --node naphtali
```

## Testing

```bash
# Unit tests
uv run pytest tests/test_cell.py

# Integration with testnet
ETZ_NETWORK=testnet kotoba-kotodama cell test --cell CharterAttestationRequestCell
```

## See also

- [`council_deliberation/`](../council_deliberation/) — receives the dispatch
- [`charter_attestation_finalization/`](../charter_attestation_finalization/) — 30-day appeal window timer
- [`charter_rehabilitation/`](../charter_rehabilitation/) — teshuvah path
