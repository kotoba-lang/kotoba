"""Unit tests for TreasuryRebalanceCell node functions and graph wiring.

Covers the four behaviors that matter constitutionally:

1. Drift below threshold → no proposal, skip record emitted (within_band).
2. Empty treasury → no proposal, skip record emitted (treasury_empty).
3. Drift above threshold → governance proposal submitted, proposal record emitted.
4. Threshold override via state propagates through compute_drift.

The cell never moves funds itself; these tests assert only that the
governance proposal path is taken (or not) and that NAV math matches
the constitutional bps semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from cell import (
    DEFAULT_DRIFT_THRESHOLD_BPS,
    TIER_CORPUS,
    TIER_LIQUID,
    TIER_RESERVE,
    compute_drift,
    emit_at_record,
    emit_skip_record,
    load_constitution,
    load_nav,
    propose_rebalance_payload,
    submit_to_governance,
)


# ─── Fake ports ──────────────────────────────────────────────────────


@dataclass
class FakeTreasuryPort:
    balances: dict[int, int]  # tier → USDC base units
    proposal_targets: list[str] = field(default_factory=lambda: ["0xTreasuryMirror"])
    proposal_calldatas: list[str] = field(default_factory=lambda: ["0xdeadbeef"])
    proposal_desc_cid: str = "bafyTreasuryRebalanceRationale"

    def tier_latest(self, tier: int) -> int:
        return self.balances.get(tier, 0)

    def build_rebalance_proposal(self, **kwargs: Any) -> tuple[list[str], list[str], str]:
        return self.proposal_targets, self.proposal_calldatas, self.proposal_desc_cid


@dataclass
class FakeConstitutionPort:
    mutables: dict[str, int]

    def get_mutable_uint(self, key: str) -> int:
        return self.mutables.get(key, 0)


@dataclass
class FakeGovernancePort:
    next_id: int = 1
    last_args: dict[str, Any] = field(default_factory=dict)

    def propose(self, *, targets, calldatas, desc_cid) -> tuple[int, str]:
        self.last_args = {"targets": targets, "calldatas": calldatas, "desc_cid": desc_cid}
        pid = self.next_id
        self.next_id += 1
        return pid, "0xgovernanceProposeTxHash"


@dataclass
class FakePdsPort:
    records: list[dict[str, Any]] = field(default_factory=list)

    def create_record(self, *, collection: str, record: dict[str, Any]) -> str:
        self.records.append({"collection": collection, "record": record})
        return f"at://did:web:etzhayyim.com/{collection}/rkey-{len(self.records)}"


# ─── Fixtures ────────────────────────────────────────────────────────


def _default_constitution() -> dict[str, int]:
    return {
        "tier_liquid_bps": 1000,   # 10%
        "tier_reserve_bps": 6000,  # 60%
        "tier_corpus_bps": 3000,   # 30%
        "kappa_bps": 300,
    }


# ─── load_nav ─────────────────────────────────────────────────────────


def test_load_nav_sums_three_tiers():
    port = FakeTreasuryPort(balances={TIER_LIQUID: 100, TIER_RESERVE: 600, TIER_CORPUS: 300})
    out = load_nav({"epoch_seconds": 1_000}, port)
    assert out["nav_liquid"] == 100
    assert out["nav_reserve"] == 600
    assert out["nav_corpus"] == 300
    assert out["nav_total"] == 1_000


# ─── load_constitution ───────────────────────────────────────────────


def test_load_constitution_passes_through_keys():
    port = FakeConstitutionPort(mutables=_default_constitution())
    out = load_constitution({}, port)
    assert out["target_liquid_bps"] == 1000
    assert out["target_reserve_bps"] == 6000
    assert out["target_corpus_bps"] == 3000
    assert out["kappa_bps"] == 300


# ─── compute_drift ───────────────────────────────────────────────────


def test_compute_drift_on_target_no_rebalance():
    """10:60:30 NAV against 10:60:30 target → zero drift."""
    state = {
        "nav_liquid": 100, "nav_reserve": 600, "nav_corpus": 300, "nav_total": 1_000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
    }
    out = compute_drift(state)
    assert out["observed_liquid_bps"] == 1000
    assert out["observed_reserve_bps"] == 6000
    assert out["observed_corpus_bps"] == 3000
    assert out["drift_liquid_bps"] == 0
    assert out["drift_reserve_bps"] == 0
    assert out["drift_corpus_bps"] == 0
    assert out["needs_rebalance"] is False
    assert out["skipped_reason"] == "within_band"
    assert out["drift_threshold_bps"] == DEFAULT_DRIFT_THRESHOLD_BPS


def test_compute_drift_within_threshold_no_rebalance():
    """Off-target but inside the 500 bps band → no rebalance."""
    # 12% liquid (+200 bps drift) — within 500 bps band.
    state = {
        "nav_liquid": 120, "nav_reserve": 580, "nav_corpus": 300, "nav_total": 1_000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
    }
    out = compute_drift(state)
    assert out["drift_liquid_bps"] == 200
    assert out["drift_reserve_bps"] == -200
    assert out["needs_rebalance"] is False


def test_compute_drift_above_threshold_triggers_rebalance():
    """20% liquid (+1000 bps drift) — exceeds default 500 bps band."""
    state = {
        "nav_liquid": 200, "nav_reserve": 500, "nav_corpus": 300, "nav_total": 1_000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
    }
    out = compute_drift(state)
    assert out["drift_liquid_bps"] == 1000
    assert out["drift_reserve_bps"] == -1000
    assert out["needs_rebalance"] is True
    assert "skipped_reason" not in out


def test_compute_drift_empty_treasury_skips():
    state = {
        "nav_liquid": 0, "nav_reserve": 0, "nav_corpus": 0, "nav_total": 0,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
    }
    out = compute_drift(state)
    assert out["needs_rebalance"] is False
    assert out["skipped_reason"] == "treasury_empty"


def test_compute_drift_threshold_override():
    """A tighter 100 bps threshold flips a previously within-band tier."""
    state = {
        "nav_liquid": 120, "nav_reserve": 580, "nav_corpus": 300, "nav_total": 1_000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
        "drift_threshold_bps": 100,
    }
    out = compute_drift(state)
    assert out["needs_rebalance"] is True


# ─── propose_rebalance_payload ────────────────────────────────────────


def test_propose_payload_delegates_to_treasury_port():
    port = FakeTreasuryPort(
        balances={},
        proposal_targets=["0xT1", "0xT2"],
        proposal_calldatas=["0xa", "0xb"],
        proposal_desc_cid="bafyRationale",
    )
    state = {
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
        "nav_liquid": 200, "nav_reserve": 500, "nav_corpus": 300,
    }
    out = propose_rebalance_payload(state, port)
    assert out["proposal_targets"] == ["0xT1", "0xT2"]
    assert out["proposal_calldatas"] == ["0xa", "0xb"]
    assert out["proposal_desc_cid"] == "bafyRationale"


# ─── submit_to_governance ─────────────────────────────────────────────


def test_submit_to_governance_records_proposal_id_and_tx():
    port = FakeGovernancePort()
    state = {
        "proposal_targets": ["0xT"],
        "proposal_calldatas": ["0xc"],
        "proposal_desc_cid": "bafyRationale",
    }
    out = submit_to_governance(state, port)
    assert out["proposal_id"] == 1
    assert out["proposal_tx_hash"] == "0xgovernanceProposeTxHash"
    assert port.last_args["targets"] == ["0xT"]
    assert port.last_args["desc_cid"] == "bafyRationale"


# ─── emit_at_record / emit_skip_record ────────────────────────────────


def test_emit_at_record_carries_full_payload():
    port = FakePdsPort()
    state = {
        "proposal_id": 42, "proposal_tx_hash": "0xtx", "proposal_desc_cid": "bafy",
        "nav_liquid": 200, "nav_reserve": 500, "nav_corpus": 300, "nav_total": 1_000,
        "observed_liquid_bps": 2000, "observed_reserve_bps": 5000, "observed_corpus_bps": 3000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
        "drift_liquid_bps": 1000, "drift_reserve_bps": -1000, "drift_corpus_bps": 0,
        "drift_threshold_bps": 500, "kappa_bps": 300, "epoch_seconds": 1_700_000_000,
    }
    out = emit_at_record(state, port)
    assert len(port.records) == 1
    rec = port.records[0]
    assert rec["collection"] == "com.etzhayyim.apps.payment.treasury-rebalance-proposal"
    assert rec["record"]["proposalId"] == 42
    assert rec["record"]["driftLiquidBps"] == 1000
    assert rec["record"]["kappaBps"] == 300
    assert out["at_record_uri"].startswith("at://")


def test_emit_skip_record_carries_reason():
    port = FakePdsPort()
    state = {
        "skipped_reason": "within_band",
        "nav_liquid": 100, "nav_reserve": 600, "nav_corpus": 300, "nav_total": 1_000,
        "observed_liquid_bps": 1000, "observed_reserve_bps": 6000, "observed_corpus_bps": 3000,
        "target_liquid_bps": 1000, "target_reserve_bps": 6000, "target_corpus_bps": 3000,
        "drift_threshold_bps": 500, "epoch_seconds": 1_700_000_000,
    }
    out = emit_skip_record(state, port)
    assert port.records[0]["collection"] == "com.etzhayyim.apps.payment.treasury-rebalance-skip"
    assert port.records[0]["record"]["reason"] == "within_band"
    assert out["at_record_uri"].startswith("at://")


# ─── End-to-end graph wiring ──────────────────────────────────────────


def _run_graph_sync(graph, initial_state):
    """Run a langgraph or langgraph-stub compiled graph synchronously.

    Real langgraph: graph.invoke(state).
    conftest stub: graph.ainvoke(state) via asyncio.
    """
    if hasattr(graph, "invoke"):
        try:
            return graph.invoke(initial_state)
        except (TypeError, AttributeError):
            pass
    import asyncio
    return asyncio.get_event_loop().run_until_complete(graph.ainvoke(initial_state))


@pytest.mark.parametrize(
    "balances,expects_proposal",
    [
        # Heavily over-allocated to liquid → proposal expected.
        ({TIER_LIQUID: 400, TIER_RESERVE: 400, TIER_CORPUS: 200}, True),
        # On-target — no proposal.
        ({TIER_LIQUID: 100, TIER_RESERVE: 600, TIER_CORPUS: 300}, False),
        # Empty treasury — skip (treasury_empty).
        ({TIER_LIQUID: 0, TIER_RESERVE: 0, TIER_CORPUS: 0}, False),
    ],
)
def test_graph_routes_to_correct_terminal(balances, expects_proposal):
    """Drive the compiled graph end-to-end via fake ports."""
    pytest.importorskip("langgraph.checkpoint.memory")
    from langgraph.checkpoint.memory import InMemorySaver
    from cell import build_graph

    treasury = FakeTreasuryPort(balances=balances)
    constitution = FakeConstitutionPort(mutables=_default_constitution())
    governance = FakeGovernancePort()
    pds = FakePdsPort()

    graph = build_graph(
        InMemorySaver(),
        treasury_port=treasury,
        constitution_port=constitution,
        governance_port=governance,
        pds_port=pds,
    )

    initial = {"epoch_seconds": 1_700_000_000}
    config = {"configurable": {"thread_id": "test-thread"}}
    final = graph.invoke(initial, config=config)

    if expects_proposal:
        assert final["needs_rebalance"] is True
        assert final["proposal_id"] == 1
        assert final["proposal_tx_hash"] == "0xgovernanceProposeTxHash"
        assert pds.records[0]["collection"] == "com.etzhayyim.apps.payment.treasury-rebalance-proposal"
    else:
        assert final["needs_rebalance"] is False
        assert pds.records[0]["collection"] == "com.etzhayyim.apps.payment.treasury-rebalance-skip"
