# treasury_rebalance — Pregel Cell

**Trigger**: monthly cron (1st of month, 00:00 UTC)

**Effect**: Detect drift between observed 護持金庫 three-tier NAV split
(流動 / 準備 / 本財) and the constitutional target ratios. When drift
exceeds the threshold, build a Safe rebalance tx + TreasuryMirror oracle
update, then submit via `Governance.propose()`. Never moves funds
directly — every execution passes through the 72h governance timelock.

**Solidity contracts**:
[`50-infra/etzhayyim-chain-contracts/`](../../../../50-infra/etzhayyim-chain-contracts/)
(`TreasuryMirror.sol`, `Governance.sol`, `Constitution.sol`)

**Murakumo placement**: Leader `zebulun`, replica `asher`

**Per ADR**: [2605172300 §3.3 + §4](../../../../90-docs/adr/2605172300-etzhayyim-bi-asset-substrate.md)
(Kisha-Stream / Goji-Treasury — bi-asset substrate)

## State machine

```
[monthly cron tick]
  → load_nav                    (TreasuryMirror.tierLatest × 3)
  → load_constitution           (target_*_bps × 3 + kappa_bps)
  → compute_drift               (observed vs target, signed bps)
    │
    ├─ max(|drift|) > threshold → propose_rebalance_payload
    │                            → submit_to_governance (Governance.propose)
    │                            → emit_at_record (proposal trail) → END
    └─ within band / treasury empty → emit_skip_record → END
```

## Constitutional inputs (read from `Constitution.sol`)

| Key | Source | Default |
|---|---|---|
| `tier_liquid_bps` | mutable, ADR-2605172300 §4 | `1000` (10%) |
| `tier_reserve_bps` | mutable, ADR-2605172300 §4 | `6000` (60%) |
| `tier_corpus_bps` | mutable, ADR-2605172300 §4 | `3000` (30%) |
| `kappa_bps` | mutable, ADR-2605172300 §4 (within floor/ceiling band) | `300` (3%) |

Sum of the three tier targets must equal `10_000`; the cell does not
re-validate this — it is a constitutional invariant maintained by
`Constitution.sol` governance writes.

## Drift threshold

`drift_threshold_bps` defaults to `500` (5 % absolute deviation per
tier). Any tier exceeding the threshold flags `needs_rebalance = true`.

Override via cell state (e.g., for emergency tighter band):

```python
config = {"configurable": {"drift_threshold_bps": 250}}  # 2.5%
graph.invoke({"epoch_seconds": now}, config=config)
```

## Output AT Records

| Collection | When emitted |
|---|---|
| `com.etzhayyim.apps.payment.treasury-rebalance-proposal` | drift > threshold; carries `proposalId`, observed/target/drift bps, `descCid` |
| `com.etzhayyim.apps.payment.treasury-rebalance-skip` | within band or empty treasury; carries `reason` |

Both records anchor to Base via the existing
`mst-projector → ipfs-pinner → l2-anchor` pipeline (ADR-2605171800), so
each monthly tick (including the no-op skips) is publicly auditable.

## Ports

`build_graph()` takes four ports — all thin wrappers around
geth-private RPC + a PDS client:

| Port | Methods | Backed by |
|---|---|---|
| `treasury_port` | `tier_latest(tier)`, `build_rebalance_proposal(...)` | web3.py + `TreasuryMirror.sol` ABI |
| `constitution_port` | `get_mutable_uint(key)` | web3.py + `Constitution.sol` ABI |
| `governance_port` | `propose(targets, calldatas, desc_cid)` → `(proposalId, txHash)` | web3.py + `Governance.sol` ABI |
| `pds_port` | `create_record(collection, record)` → `at://…` | `@etzhayyim/sdk` PDS RPC |

A production wiring is provided by [`web3_ports.py`](web3_ports.py) —
mirror of `kotodama.eligibility.web3_ports`:

- `Web3Config` + `PdsConfig` dataclasses for connection + addresses + auth
- `build_production_ports(web3_cfg, pds_cfg)` returns the 4 ports wired
  against geth-private RPC + an `atproto`-Python PDS client
- ABI fragments (`TREASURY_MIRROR_ABI` / `CONSTITUTION_ABI` /
  `GOVERNANCE_ABI`) match the on-chain signatures in
  `50-infra/etzhayyim-chain-contracts/src/{TreasuryMirror,Constitution,Governance}.sol`
- `_keccak_key(name)` mirrors the on-chain `keccak256(text)` hashing
  used by `ConstitutionKeys.sol` so reads find the right slot

`web3` / `eth-account` / `atproto` imports are lazy so the module
stays test-environment-friendly. Install via:

```bash
uv pip install -e '20-actors/kotoba-kotodama/py[eligibility,atproto]'
```

The cell is also still unit-testable today via the fake ports under
`tests/test_cell.py`.

## Running

```bash
cd 20-actors/kotoba-kotodama/py
uv run pytest src/kotodama/../../cells/treasury_rebalance/tests -v
```

Deploy to leader node (after `Phase 1: Treasury Mainnet` clears
operational readiness):

```bash
kotoba-kotodama cell deploy --cell TreasuryRebalanceCell --schedule "0 0 1 * *"
kotoba-kotodama cell health --cell TreasuryRebalanceCell
```

## Invariants

- **No direct fund movement.** The cell only constructs proposal
  payloads. Every Safe transaction is gated by `Governance.propose`
  + 72h timelock (`Constitution.getMutable("timelock_secs")`).
- **κ band respected.** The cell reads `kappa_bps` but never proposes a
  change to it. κ adjustments require a separate proposal flow.
- **Skip is observable.** Even months where no proposal is emitted
  leave an AT Record trail — silence is never the cell's output.
- **Idempotent monthly tick.** Re-running the same `epoch_seconds`
  re-reads on-chain state; if NAV unchanged + drift unchanged, the
  next run is a no-op proposal-wise (but emits a fresh skip record).
