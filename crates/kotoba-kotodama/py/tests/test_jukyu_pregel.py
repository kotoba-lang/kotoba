"""Unit tests for Jukyu Pregel pure helper functions.

All tests are DB-free: they exercise the pure Python helpers in
kotodama.jukyu.graph using synthetic in-memory data.
"""

from __future__ import annotations

from typing import Any

import pytest

from kotodama.jukyu.graph import (
    _CRITICAL_NODE_KINDS,
    _DAMPING,
    _HALT_DELTA,
    _MAX_ITER,
    _compute_company_exposures,
    _init_pressures_from_balance,
    _propagate_pressure_step,
    _transport_pressure_by_node,
    should_continue,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _balance(domain: str, country: str, demand: float, supply: float) -> dict[str, Any]:
    return {
        "domain": domain,
        "country_code": country,
        "demand_quantity": demand,
        "supply_quantity": supply,
        "balance_quantity": supply - demand,
    }


def _edge(
    src: str,
    dst: str,
    weight: float,
    domain: str = "naphtha",
    src_op: str = "",
    dst_op: str = "",
    src_kind: str = "refinery",
    dst_kind: str = "steam_cracker",
    src_country: str = "JP",
    dst_country: str = "JP",
    product_code: str = "NAPH",
    product_family: str = "petrochemical_feedstock",
) -> dict[str, Any]:
    return {
        "src_vid": src,
        "dst_vid": dst,
        "dependency_weight": weight,
        "domain": domain,
        "src_operator_did": src_op,
        "dst_operator_did": dst_op,
        "src_node_kind": src_kind,
        "dst_node_kind": dst_kind,
        "src_country_code": src_country,
        "dst_country_code": dst_country,
        "product_code": product_code,
        "product_family": product_family,
        "src_name": src_op or src,
        "dst_name": dst_op or dst,
    }


# ─── _init_pressures_from_balance ────────────────────────────────────────────


class TestInitPressures:
    def test_no_data_returns_empty(self) -> None:
        result = _init_pressures_from_balance([], [])
        assert result == {}

    def test_surplus_balance_gives_zero_pressure(self) -> None:
        balances = [_balance("naphtha", "JP", demand=100.0, supply=200.0)]
        chain = [_edge("node-a", "node-b", 0.8, src_country="JP", dst_country="JP")]
        result = _init_pressures_from_balance(balances, chain)
        assert result.get("node-a", 0.0) == 0.0
        assert result.get("node-b", 0.0) == 0.0

    def test_deficit_balance_assigns_pressure(self) -> None:
        # demand=200, supply=50 → balance=-150 → pressure=150/200=0.75
        balances = [_balance("naphtha", "JP", demand=200.0, supply=50.0)]
        chain = [_edge("node-a", "node-b", 0.8, src_country="JP", dst_country="JP")]
        result = _init_pressures_from_balance(balances, chain)
        assert result["node-a"] == pytest.approx(0.75)
        assert result["node-b"] == pytest.approx(0.75)

    def test_pressure_capped_at_one(self) -> None:
        # demand=10, supply=0 → balance=-10 → 10/10=1.0
        balances = [_balance("naphtha", "JP", demand=10.0, supply=0.0)]
        chain = [_edge("n", "m", 1.0, src_country="JP", dst_country="JP")]
        result = _init_pressures_from_balance(balances, chain)
        assert result["n"] <= 1.0

    def test_multiple_countries_independent(self) -> None:
        balances = [
            _balance("naphtha", "JP", demand=100.0, supply=50.0),  # pressure=0.5
            _balance("naphtha", "KR", demand=100.0, supply=90.0),  # pressure=0.1
        ]
        chain = [
            _edge("jp-node", "jp-node2", 0.5, src_country="JP", dst_country="JP"),
            _edge("kr-node", "kr-node2", 0.5, src_country="KR", dst_country="KR"),
        ]
        result = _init_pressures_from_balance(balances, chain)
        assert result["jp-node"] == pytest.approx(0.5)
        assert result["kr-node"] == pytest.approx(0.1)

    def test_takes_max_pressure_per_node(self) -> None:
        # node-a appears in both a high-pressure JP edge and a low-pressure KR edge
        balances = [
            _balance("naphtha", "JP", demand=100.0, supply=0.0),   # pressure=1.0
            _balance("naphtha", "KR", demand=100.0, supply=80.0),  # pressure=0.2
        ]
        chain = [
            _edge("node-a", "node-b", 0.5, src_country="JP", dst_country="JP"),
            _edge("node-a", "node-c", 0.5, src_country="KR", dst_country="KR"),
        ]
        result = _init_pressures_from_balance(balances, chain)
        assert result["node-a"] == pytest.approx(1.0)

    def test_ignores_nodes_with_no_matching_country(self) -> None:
        balances = [_balance("naphtha", "JP", demand=100.0, supply=0.0)]
        chain = [_edge("de-node", "fr-node", 0.5, src_country="DE", dst_country="FR")]
        result = _init_pressures_from_balance(balances, chain)
        # no pressure because DE/FR not in balance rows
        assert result.get("de-node", 0.0) == 0.0
        assert result.get("fr-node", 0.0) == 0.0


# ─── _propagate_pressure_step ─────────────────────────────────────────────────


class TestPropagatePressureStep:
    def test_no_edges_no_change(self) -> None:
        pressures = {"A": 0.5, "B": 0.0}
        new_p, delta = _propagate_pressure_step(pressures, [])
        assert new_p == pressures
        assert delta == 0.0

    def test_upstream_receives_pressure(self) -> None:
        # Edge A→B: A supplies B. B has pressure 0.8, weight 1.0 → A gets 0.8*0.70
        pressures = {"A": 0.0, "B": 0.8}
        chain = [_edge("A", "B", 1.0)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        expected_a = pytest.approx(0.8 * _DAMPING)
        assert new_p["A"] == expected_a
        assert new_p["B"] == pytest.approx(0.8)  # dst unchanged

    def test_damping_applied(self) -> None:
        pressures = {"A": 0.0, "B": 1.0}
        chain = [_edge("A", "B", 0.5)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        assert new_p["A"] == pytest.approx(0.5 * _DAMPING)

    def test_pressure_capped_at_one(self) -> None:
        pressures = {"A": 0.9, "B": 1.0}
        chain = [_edge("A", "B", 1.0)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        assert new_p["A"] <= 1.0

    def test_max_delta_computed(self) -> None:
        pressures = {"A": 0.0, "B": 1.0}
        chain = [_edge("A", "B", 1.0)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        # A changed from 0.0 to DAMPING, B unchanged
        assert delta == pytest.approx(_DAMPING)

    def test_zero_weight_edge_skipped(self) -> None:
        pressures = {"A": 0.0, "B": 1.0}
        chain = [_edge("A", "B", 0.0)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        assert new_p["A"] == pytest.approx(0.0)
        assert delta == 0.0

    def test_convergence_after_multiple_steps(self) -> None:
        # Simulate multiple supersteps until delta < HALT_DELTA
        pressures: dict[str, float] = {"A": 0.0, "B": 0.0, "C": 0.5}
        chain = [
            _edge("A", "B", 0.8),
            _edge("B", "C", 0.6),
        ]
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        # After convergence, upstream A should have acquired some pressure
        assert pressures["A"] > 0.0
        assert pressures["B"] > 0.0

    def test_no_pressure_at_dst_means_no_propagation(self) -> None:
        pressures = {"A": 0.0, "B": 0.0}
        chain = [_edge("A", "B", 1.0)]
        new_p, delta = _propagate_pressure_step(pressures, chain)
        assert new_p["A"] == 0.0
        assert delta == 0.0


# ─── _compute_company_exposures ───────────────────────────────────────────────


class TestComputeCompanyExposures:
    def test_no_data_returns_empty(self) -> None:
        result = _compute_company_exposures({}, [], [])
        assert result == []

    def test_single_company_operator(self) -> None:
        node_pressures = {"node-1": 0.8, "node-2": 0.3}
        chain = [
            _edge(
                "node-1", "node-2", 0.9,
                src_op="did:web:operator-a.example",
                dst_op="did:web:operator-b.example",
                src_kind="refinery",
                dst_kind="steam_cracker",
            )
        ]
        result = _compute_company_exposures(node_pressures, chain, [])
        companies = {r["company_did"]: r for r in result}
        assert "did:web:operator-a.example" in companies
        assert "did:web:operator-b.example" in companies

    def test_risk_score_between_zero_and_one(self) -> None:
        node_pressures = {"n": 0.9}
        chain = [_edge("n", "m", 1.0, src_op="did:web:op.example", src_kind="refinery")]
        result = _compute_company_exposures(node_pressures, chain, [])
        for row in result:
            assert 0.0 <= row["risk_score"] <= 1.0

    def test_confidence_between_zero_and_one(self) -> None:
        node_pressures = {"n": 0.5}
        chain = [_edge("n", "m", 0.5, src_op="did:web:op.example")]
        result = _compute_company_exposures(node_pressures, chain, [])
        for row in result:
            assert 0.0 <= row["confidence"] <= 1.0

    def test_critical_node_increases_structural_pressure(self) -> None:
        # refinery is in _CRITICAL_NODE_KINDS → higher structural_pressure
        node_pressures_critical = {"n-refinery": 0.5}
        node_pressures_non_critical = {"n-office": 0.5}

        chain_critical = [
            _edge("n-refinery", "m", 0.5, src_op="did:web:op.example", src_kind="refinery")
        ]
        chain_non_critical = [
            _edge("n-office", "m", 0.5, src_op="did:web:op.example", src_kind="office")
        ]

        r_critical = _compute_company_exposures(node_pressures_critical, chain_critical, [])
        r_non = _compute_company_exposures(node_pressures_non_critical, chain_non_critical, [])

        sp_critical = r_critical[0]["structural_pressure"] if r_critical else 0.0
        sp_non = r_non[0]["structural_pressure"] if r_non else 0.0
        assert sp_critical >= sp_non

    def test_zero_pressure_gives_low_risk(self) -> None:
        node_pressures = {"n": 0.0, "m": 0.0}
        chain = [_edge("n", "m", 0.5, src_op="did:web:op.example")]
        result = _compute_company_exposures(node_pressures, chain, [])
        for row in result:
            assert row["risk_score"] < 0.3  # low risk when no pressure

    def test_high_pressure_gives_high_risk(self) -> None:
        node_pressures = {"n": 1.0, "m": 1.0}
        chain = [
            _edge("n", "m", 1.0, src_op="did:web:op.example", src_kind="refinery"),
        ]
        balances = [_balance("naphtha", "JP", demand=200.0, supply=0.0)]
        result = _compute_company_exposures(node_pressures, chain, balances)
        for row in result:
            assert row["risk_score"] > 0.3

    def test_price_pressure_from_balance(self) -> None:
        node_pressures = {"n": 0.0}
        chain = [
            _edge("n", "m", 0.5, src_op="did:web:op.example",
                  src_country="JP", domain="naphtha")
        ]
        # Severe deficit → high price pressure
        balances = [_balance("naphtha", "JP", demand=100.0, supply=0.0)]
        result_deficit = _compute_company_exposures(node_pressures, chain, balances)
        result_surplus = _compute_company_exposures(
            node_pressures, chain,
            [_balance("naphtha", "JP", demand=100.0, supply=200.0)]
        )
        pp_deficit = result_deficit[0]["price_pressure"] if result_deficit else 0.0
        pp_surplus = result_surplus[0]["price_pressure"] if result_surplus else 0.0
        assert pp_deficit > pp_surplus

    def test_deduplicates_vids_per_company(self) -> None:
        # Same company appears as operator in two edges → counted once per vid
        node_pressures = {"n1": 0.5, "n2": 0.4}
        chain = [
            _edge("n1", "n2", 0.7, src_op="did:web:same-op.example"),
            _edge("n2", "n3", 0.7, src_op="did:web:same-op.example"),
        ]
        result = _compute_company_exposures(node_pressures, chain, [])
        companies = [r for r in result if r["company_did"] == "did:web:same-op.example"]
        assert len(companies) == 1


# ─── vessel / transportation context ─────────────────────────────────────────


class TestTransportContext:
    def test_transport_pressure_maps_to_connected_nodes(self) -> None:
        rows = [{
            "src_vid": "terminal-a",
            "dst_vid": "cracker-b",
            "status": "delayed",
            "route_risk_score": 0.2,
            "eta_delay_hours": 12.0,
        }]
        pressure = _transport_pressure_by_node(rows)
        assert pressure["terminal-a"] == pytest.approx(0.75)
        assert pressure["cracker-b"] == pytest.approx(0.75)

    def test_transport_entity_becomes_exposure(self) -> None:
        chain = [_edge(
            "terminal-a",
            "cracker-b",
            0.8,
            domain="crude_oil",
            src_country="SG",
            dst_country="JP",
            product_code="CRUD",
            product_family="crude_oil",
        )]
        balances = [_balance("crude_oil", "JP", demand=100.0, supply=75.0)]
        transport = [{
            "leg_id": "cargo-1",
            "domain": "crude_oil",
            "src_vid": "terminal-a",
            "dst_vid": "cracker-b",
            "carrier_did": "le:carrier:abc",
            "carrier_name": "Example Carrier SA",
            "vessel_imo": "9300001",
            "vessel_name": "Example Trader",
            "origin_locode": "SGSIN",
            "destination_locode": "JPTYO",
            "product_code": "CRUD",
            "product_family": "crude_oil",
            "status": "diverted",
            "route_risk_score": 0.82,
            "eta_delay_hours": 30.0,
        }]
        exposures = _compute_company_exposures(
            {"terminal-a": 0.0, "cracker-b": 0.25},
            chain,
            balances,
            transport,
        )
        carrier = next(row for row in exposures if row["company_did"] == "le:carrier:abc")
        assert carrier["company_name"] == "Example Carrier SA"
        assert carrier["risk_score"] > 0.0
        assert "mv_jukyu_transport_context" in carrier["evidence_json"]


# ─── should_continue ──────────────────────────────────────────────────────────


class TestShouldContinue:
    def test_returns_propagate_initially(self) -> None:
        state = {"pregelIter": 0, "pregelMaxDelta": 1.0}
        assert should_continue(state) == "propagate"  # type: ignore[arg-type]

    def test_halts_at_max_iter(self) -> None:
        state = {"pregelIter": _MAX_ITER, "pregelMaxDelta": 1.0}
        assert should_continue(state) == "write_signals"  # type: ignore[arg-type]

    def test_halts_when_delta_below_threshold(self) -> None:
        state = {"pregelIter": 2, "pregelMaxDelta": _HALT_DELTA - 0.001}
        assert should_continue(state) == "write_signals"  # type: ignore[arg-type]

    def test_continues_when_iter_low_and_delta_high(self) -> None:
        state = {"pregelIter": 3, "pregelMaxDelta": 0.5}
        assert should_continue(state) == "propagate"  # type: ignore[arg-type]

    def test_halts_exactly_at_max_iter(self) -> None:
        # iter == _MAX_ITER should halt, iter == _MAX_ITER - 1 should continue
        state_at = {"pregelIter": _MAX_ITER, "pregelMaxDelta": 1.0}
        state_before = {"pregelIter": _MAX_ITER - 1, "pregelMaxDelta": 1.0}
        assert should_continue(state_at) == "write_signals"  # type: ignore[arg-type]
        assert should_continue(state_before) == "propagate"  # type: ignore[arg-type]

    def test_handles_missing_fields_gracefully(self) -> None:
        # Empty state defaults to iter=0, delta=1.0 → continue
        assert should_continue({}) == "propagate"  # type: ignore[arg-type]

    def test_halts_exactly_at_halt_delta(self) -> None:
        state = {"pregelIter": 1, "pregelMaxDelta": _HALT_DELTA}
        # delta == _HALT_DELTA: strictly less than → should still propagate
        assert should_continue(state) == "propagate"  # type: ignore[arg-type]


# ─── End-to-end Pregel iteration ─────────────────────────────────────────────


class TestPregelEndToEnd:
    def test_pressure_propagates_along_chain(self) -> None:
        """A→B→C chain: shortage at C propagates back through B to A."""
        balances = [_balance("naphtha", "JP", demand=200.0, supply=50.0)]
        chain = [
            _edge("A", "B", 0.9, src_country="JP", dst_country="JP"),
            _edge("B", "C", 0.9, src_country="JP", dst_country="JP"),
        ]
        pressures = _init_pressures_from_balance(balances, chain)
        # Run until convergence
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        # All nodes should have some pressure since JP has a shortage
        assert pressures.get("A", 0.0) > 0.0
        assert pressures.get("B", 0.0) > 0.0
        assert pressures.get("C", 0.0) > 0.0

    def test_isolated_surplus_country_stays_at_zero(self) -> None:
        """Surplus country: no pressure should propagate."""
        balances = [_balance("naphtha", "DE", demand=50.0, supply=200.0)]
        chain = [_edge("A", "B", 0.9, src_country="DE", dst_country="DE")]
        pressures = _init_pressures_from_balance(balances, chain)
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        assert pressures.get("A", 0.0) == 0.0
        assert pressures.get("B", 0.0) == 0.0

    def test_exposures_produced_after_propagation(self) -> None:
        balances = [_balance("naphtha", "JP", demand=200.0, supply=0.0)]
        chain = [
            _edge(
                "node-supply", "node-demand", 0.8,
                src_op="did:web:supplier.example",
                dst_op="did:web:consumer.example",
                src_kind="refinery",
                dst_kind="steam_cracker",
                src_country="JP", dst_country="JP",
            )
        ]
        pressures = _init_pressures_from_balance(balances, chain)
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        exposures = _compute_company_exposures(pressures, chain, balances)
        assert len(exposures) >= 1
        for e in exposures:
            assert "company_did" in e
            assert "risk_score" in e
            assert e["risk_score"] >= 0.0
