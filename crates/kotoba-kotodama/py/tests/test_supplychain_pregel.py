"""DB-free unit tests for supplychain Pregel pure functions.

All tests use synthetic in-memory data and do not touch the database.
"""

from __future__ import annotations

import pytest

from kotodama.supplychain.graph import (
    _DAMPING,
    _DEFAULT_DOMAIN,
    _HALT_DELTA,
    _MAX_ITER,
    _compute_company_exposures,
    _init_pressures_from_balance,
    _propagate_pressure_step,
    should_continue,
    SupplychainState,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _balance(
    country: str,
    demand: float,
    supply: float,
    domain: str = _DEFAULT_DOMAIN,
    product_code: str = "motor",
) -> dict:
    return {
        "domain": domain,
        "country_code": country,
        "demand_quantity": demand,
        "supply_quantity": supply,
        "balance_quantity": supply - demand,
        "product_code": product_code,
        "product_family": "cleaning_robot_material",
    }


def _edge(
    src: str,
    dst: str,
    weight: float,
    domain: str = _DEFAULT_DOMAIN,
    src_kind: str = "supplier",
    dst_kind: str = "material",
    src_country: str = "JP",
    dst_country: str = "JP",
    src_op: str = "",
    dst_op: str = "",
) -> dict:
    return {
        "src_vid": src,
        "dst_vid": dst,
        "dependency_weight": weight,
        "domain": domain,
        "src_node_kind": src_kind,
        "dst_node_kind": dst_kind,
        "src_country_code": src_country,
        "dst_country_code": dst_country,
        "src_operator_did": src_op,
        "dst_operator_did": dst_op,
        "product_code": "motor",
        "product_family": "cleaning_robot_material",
        "src_name": src_op or src,
        "dst_name": dst_op or dst,
    }


# ─── _init_pressures_from_balance ────────────────────────────────────────────

class TestInitPressures:
    def test_shortage_maps_to_positive_pressure(self):
        balance = [_balance("JP", demand=10.0, supply=2.0)]
        edges = [_edge("supplier-A", "material-M", 1.0)]
        pressures = _init_pressures_from_balance(balance, edges)
        assert pressures.get("material-M", 0.0) > 0.0
        assert pressures.get("supplier-A", 0.0) > 0.0

    def test_surplus_maps_to_zero_pressure(self):
        balance = [_balance("JP", demand=5.0, supply=20.0)]
        edges = [_edge("supplier-A", "material-M", 1.0)]
        pressures = _init_pressures_from_balance(balance, edges)
        assert pressures.get("material-M", 0.0) == 0.0
        assert pressures.get("supplier-A", 0.0) == 0.0

    def test_pressure_capped_at_one(self):
        balance = [_balance("JP", demand=1.0, supply=0.0)]
        edges = [_edge("supplier-A", "material-M", 1.0)]
        pressures = _init_pressures_from_balance(balance, edges)
        assert pressures.get("material-M", 0.0) <= 1.0

    def test_empty_chain_returns_empty(self):
        balance = [_balance("JP", demand=10.0, supply=0.0)]
        pressures = _init_pressures_from_balance(balance, [])
        assert pressures == {}

    def test_empty_balance_returns_zero_pressures(self):
        edges = [_edge("supplier-A", "material-M", 1.0)]
        pressures = _init_pressures_from_balance([], edges)
        assert all(v == 0.0 for v in pressures.values())

    def test_multiple_domains_isolated(self):
        balance = [
            _balance("JP", demand=10.0, supply=0.0, domain="cleaning_robot"),
            _balance("CN", demand=10.0, supply=10.0, domain="automotive"),
        ]
        edges = [
            _edge("s1", "m1", 1.0, domain="cleaning_robot", src_country="JP", dst_country="JP"),
            _edge("s2", "m2", 1.0, domain="automotive", src_country="CN", dst_country="CN"),
        ]
        pressures = _init_pressures_from_balance(balance, edges)
        assert pressures.get("m1", 0.0) > 0.0
        assert pressures.get("m2", 0.0) == 0.0

    def test_node_appears_in_multiple_edges(self):
        balance = [_balance("JP", demand=8.0, supply=2.0)]
        edges = [
            _edge("supplier-A", "shared-mat", 1.0),
            _edge("shared-mat", "assembly-X", 0.8, src_kind="material", dst_kind="assembly"),
        ]
        pressures = _init_pressures_from_balance(balance, edges)
        assert "shared-mat" in pressures


# ─── _propagate_pressure_step ─────────────────────────────────────────────────

class TestPropagatePressureStep:
    def test_upstream_pressure_propagates(self):
        # material has pressure → supplier should get pressure
        initial = {"material-M": 0.8, "supplier-A": 0.0}
        edges = [_edge("supplier-A", "material-M", 1.0)]
        new, delta = _propagate_pressure_step(initial, edges)
        assert new["supplier-A"] > 0.0
        assert delta > 0.0

    def test_damping_applied(self):
        initial = {"material-M": 1.0, "supplier-A": 0.0}
        edges = [_edge("supplier-A", "material-M", 1.0)]
        new, _ = _propagate_pressure_step(initial, edges)
        expected = 1.0 * 1.0 * _DAMPING
        assert abs(new["supplier-A"] - expected) < 1e-9

    def test_pressure_capped_at_one(self):
        initial = {"material-M": 1.0, "supplier-A": 0.99}
        edges = [_edge("supplier-A", "material-M", 1.0)]
        new, _ = _propagate_pressure_step(initial, edges)
        assert new["supplier-A"] <= 1.0

    def test_zero_weight_edge_no_propagation(self):
        initial = {"material-M": 0.9, "supplier-A": 0.0}
        edges = [_edge("supplier-A", "material-M", 0.0)]
        new, delta = _propagate_pressure_step(initial, edges)
        assert new["supplier-A"] == 0.0
        assert delta == 0.0

    def test_no_pressure_no_propagation(self):
        initial = {"material-M": 0.0, "supplier-A": 0.0}
        edges = [_edge("supplier-A", "material-M", 1.0)]
        new, delta = _propagate_pressure_step(initial, edges)
        assert new["supplier-A"] == 0.0
        assert delta == 0.0

    def test_multi_hop_chain(self):
        # raw-material → sub-component → assembly → package
        initial = {
            "raw-mat": 0.0,
            "sub-comp": 0.0,
            "assembly": 0.0,
            "package": 0.8,
        }
        edges = [
            _edge("raw-mat", "sub-comp", 0.9),
            _edge("sub-comp", "assembly", 0.8),
            _edge("assembly", "package", 0.7),
        ]
        p1, _ = _propagate_pressure_step(initial, edges)
        p2, _ = _propagate_pressure_step(p1, edges)
        # Pressure should propagate back: assembly→sub-comp→raw-mat
        assert p1.get("assembly", 0.0) > 0.0
        assert p2.get("sub-comp", 0.0) > 0.0

    def test_max_delta_is_maximum_change(self):
        initial = {"m1": 0.5, "m2": 0.3}
        edges = [_edge("m2", "m1", 0.0)]  # no change
        _, delta = _propagate_pressure_step(initial, edges)
        assert delta == 0.0

    def test_empty_edges_no_change(self):
        initial = {"material-M": 0.7}
        new, delta = _propagate_pressure_step(initial, [])
        assert new == initial
        assert delta == 0.0


# ─── _compute_company_exposures ───────────────────────────────────────────────

class TestComputeCompanyExposures:
    def _run(self, pressures, edges, balance=None):
        return _compute_company_exposures(pressures, edges, balance or [])

    def test_single_supplier_gets_score(self):
        pressures = {"supplier-A": 0.9, "material-M": 0.7}
        edges = [_edge("supplier-A", "material-M", 1.0, src_op="did:lei:AAA", dst_op="")]
        result = self._run(pressures, edges)
        assert any(r["company_did"] == "did:lei:AAA" for r in result)

    def test_risk_score_bounded(self):
        pressures = {"s": 1.0, "m": 1.0}
        edges = [_edge("s", "m", 1.0, src_op="did:lei:X", dst_op="did:lei:Y")]
        result = self._run(pressures, edges)
        for r in result:
            assert 0.0 <= r["risk_score"] <= 0.95

    def test_zero_pressure_low_risk(self):
        # With zero node pressures only structural_pressure (0.10 weight) contributes.
        # Use non-critical node kinds to ensure structural_pressure is also 0.
        pressures = {"s": 0.0, "m": 0.0}
        edges = [_edge("s", "m", 1.0, src_op="did:lei:Z", dst_op="",
                        src_kind="pipeline", dst_kind="pipeline")]
        result = self._run(pressures, edges)
        for r in result:
            assert r["risk_score"] == 0.0

    def test_missing_operator_did_skipped(self):
        pressures = {"s": 0.9, "m": 0.8}
        edges = [_edge("s", "m", 1.0)]  # no operator DIDs
        result = self._run(pressures, edges)
        assert result == []

    def test_price_pressure_from_balance(self):
        pressures = {"s": 0.5, "m": 0.5}
        edges = [_edge("s", "m", 1.0, src_op="did:lei:P", dst_op="", src_country="JP")]
        balance = [_balance("JP", demand=10.0, supply=2.0)]
        result = self._run(pressures, edges, balance)
        company = next((r for r in result if r["company_did"] == "did:lei:P"), None)
        assert company is not None
        assert company["price_pressure"] > 0.0

    def test_confidence_always_positive(self):
        pressures = {"s": 0.6, "m": 0.4}
        edges = [_edge("s", "m", 0.8, src_op="did:lei:C")]
        result = self._run(pressures, edges)
        for r in result:
            assert r["confidence"] > 0.0

    def test_multiple_companies(self):
        pressures = {"s1": 0.8, "m1": 0.6, "s2": 0.4, "m2": 0.3}
        edges = [
            _edge("s1", "m1", 1.0, src_op="did:lei:AA"),
            _edge("s2", "m2", 0.5, src_op="did:lei:BB"),
        ]
        result = self._run(pressures, edges)
        dids = {r["company_did"] for r in result}
        assert "did:lei:AA" in dids
        assert "did:lei:BB" in dids

    def test_domain_and_country_captured(self):
        pressures = {"s": 0.5}
        edges = [_edge("s", "m", 0.8, src_op="did:lei:X", src_country="CN")]
        result = self._run(pressures, edges)
        assert result[0]["country_code"] == "CN"

    def test_structural_pressure_from_critical_nodes(self):
        from kotodama.supplychain.graph import _CRITICAL_NODE_KINDS
        kind = next(iter(_CRITICAL_NODE_KINDS))
        pressures = {"s": 0.5, "m": 0.5}
        edges = [_edge("s", "m", 0.8, src_op="did:lei:X", src_kind=kind)]
        result = self._run(pressures, edges)
        assert result[0]["structural_pressure"] > 0.0


# ─── should_continue ─────────────────────────────────────────────────────────

class TestShouldContinue:
    def _state(self, iter_num: int, max_delta: float) -> SupplychainState:
        s: SupplychainState = {}
        s["pregelIter"] = iter_num
        s["pregelMaxDelta"] = max_delta
        return s

    def test_continues_below_max_iter_and_high_delta(self):
        assert should_continue(self._state(0, 1.0)) == "propagate"

    def test_halts_at_max_iter(self):
        assert should_continue(self._state(_MAX_ITER, 1.0)) == "write_signals"

    def test_halts_above_max_iter(self):
        assert should_continue(self._state(_MAX_ITER + 3, 0.5)) == "write_signals"

    def test_halts_on_converged_delta(self):
        assert should_continue(self._state(2, _HALT_DELTA - 0.001)) == "write_signals"

    def test_continues_on_delta_exactly_at_threshold(self):
        assert should_continue(self._state(2, _HALT_DELTA)) == "propagate"

    def test_missing_state_defaults_continue(self):
        assert should_continue({}) == "propagate"

    def test_iter_zero_always_continues(self):
        assert should_continue(self._state(0, 0.5)) == "propagate"


# ─── End-to-end Pregel loop (pure, no DB) ────────────────────────────────────

class TestPregelEndToEnd:
    def _run_pregel(self, balance, chain):
        pressures = _init_pressures_from_balance(balance, chain)
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        return pressures

    def test_converges_for_simple_chain(self):
        balance = [_balance("JP", demand=10.0, supply=2.0)]
        chain = [
            _edge("raw-sup", "material-M", 0.9),
            _edge("material-M", "assembly-P", 0.8, src_kind="material", dst_kind="assembly"),
        ]
        pressures = self._run_pregel(balance, chain)
        # All reachable nodes should have non-zero pressure
        assert pressures.get("material-M", 0.0) > 0.0
        assert pressures.get("raw-sup", 0.0) > 0.0

    def test_no_shortage_zero_pressure_throughout(self):
        balance = [_balance("JP", demand=5.0, supply=20.0)]
        chain = [_edge("sup", "mat", 1.0)]
        pressures = self._run_pregel(balance, chain)
        assert all(v == 0.0 for v in pressures.values())

    def test_exposure_scores_sum_to_less_than_n(self):
        balance = [_balance("JP", demand=10.0, supply=1.0)]
        chain = [
            _edge("s1", "m1", 0.9, src_op="did:lei:X"),
            _edge("s2", "m2", 0.7, src_op="did:lei:Y"),
        ]
        pressures = _init_pressures_from_balance(balance, chain)
        for _ in range(_MAX_ITER):
            pressures, delta = _propagate_pressure_step(pressures, chain)
            if delta < _HALT_DELTA:
                break
        exposures = _compute_company_exposures(pressures, chain, balance)
        total = sum(r["risk_score"] for r in exposures)
        assert total < len(exposures)  # scores bounded < 1 each
