"""DB-free structural tests for normalize_semiconductor adapter.

These tests verify the function contract (return shape, key presence, domain
field) without touching RisingWave. SQL correctness is validated at integration
test time against a real DB.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ─── Helper ──────────────────────────────────────────────────────────────────

def _run_normalize(
    execute_return: int = 5,
    fetch_one_return: tuple[int] = (5,),
) -> dict[str, Any]:
    """Call normalize_semiconductor() with mocked DB helpers."""
    with (
        patch("kotodama.jukyu.adapter.execute", return_value=execute_return) as mock_exec,
        patch("kotodama.jukyu.adapter.fetch_one", return_value=fetch_one_return),
    ):
        from kotodama.jukyu.adapter import normalize_semiconductor
        result = normalize_semiconductor()
    return result


# ─── Return shape ─────────────────────────────────────────────────────────────

class TestNormalizeSemiconductorShape:
    def test_returns_dict(self):
        result = _run_normalize()
        assert isinstance(result, dict)

    def test_ok_is_true(self):
        result = _run_normalize()
        assert result["ok"] is True

    def test_domain_is_semiconductor(self):
        result = _run_normalize()
        assert result["domain"] == "semiconductor"

    def test_all_supply_node_keys_present(self):
        result = _run_normalize()
        for key in ("fabNodes", "socNodes", "emsNodes"):
            assert key in result, f"missing key: {key}"

    def test_all_dependency_keys_present(self):
        result = _run_normalize()
        for key in ("fabSocDeps", "socEmsDeps"):
            assert key in result, f"missing key: {key}"

    def test_company_operate_edges_key_present(self):
        result = _run_normalize()
        assert "companyOperateEdges" in result

    def test_balance_observations_key_present(self):
        result = _run_normalize()
        assert "balanceObservations" in result

    def test_company_exposures_key_present(self):
        result = _run_normalize()
        assert "companyExposures" in result

    def test_totals_keys_present(self):
        result = _run_normalize()
        for key in ("jukyuSupplyNodesTotal", "jukyuBalanceRowsTotal", "jukyuExposureRowsTotal"):
            assert key in result, f"missing total key: {key}"

    def test_totals_are_integers(self):
        result = _run_normalize()
        assert isinstance(result["jukyuSupplyNodesTotal"], int)
        assert isinstance(result["jukyuBalanceRowsTotal"], int)
        assert isinstance(result["jukyuExposureRowsTotal"], int)


# ─── DB call count ────────────────────────────────────────────────────────────

class TestNormalizeSemiconductorDbCalls:
    def test_execute_called_multiple_times(self):
        with (
            patch("kotodama.jukyu.adapter.execute", return_value=0) as mock_exec,
            patch("kotodama.jukyu.adapter.fetch_one", return_value=(0,)),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            normalize_semiconductor()
        # 7 DELETEs + 8 INSERTs + 1 combined companyOperateEdges = 16 execute calls
        assert mock_exec.call_count >= 14

    def test_fetch_one_called_three_times(self):
        with (
            patch("kotodama.jukyu.adapter.execute", return_value=0),
            patch("kotodama.jukyu.adapter.fetch_one", return_value=(0,)) as mock_fetch,
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            normalize_semiconductor()
        assert mock_fetch.call_count == 3

    def test_totals_use_semiconductor_domain_param(self):
        fetch_calls: list[tuple] = []

        def _mock_fetch(sql: str, params: tuple = ()) -> tuple:
            fetch_calls.append(params)
            return (0,)

        with (
            patch("kotodama.jukyu.adapter.execute", return_value=0),
            patch("kotodama.jukyu.adapter.fetch_one", side_effect=_mock_fetch),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            normalize_semiconductor()

        assert all(
            "semiconductor" in str(p) for p in fetch_calls
        ), f"expected 'semiconductor' in all fetch params: {fetch_calls}"


# ─── Idempotency (delete patterns) ───────────────────────────────────────────

class TestNormalizeSemiconductorIdempotency:
    def test_has_both_deletes_and_inserts(self):
        call_types: set[str] = set()

        def _mock_exec(sql: str, params: tuple = ()) -> int:
            if "DELETE" in sql.upper():
                call_types.add("DELETE")
            elif "INSERT" in sql.upper():
                call_types.add("INSERT")
            return 0

        with (
            patch("kotodama.jukyu.adapter.execute", side_effect=_mock_exec),
            patch("kotodama.jukyu.adapter.fetch_one", return_value=(0,)),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            normalize_semiconductor()

        assert "DELETE" in call_types, "adapter must issue DELETE statements"
        assert "INSERT" in call_types, "adapter must issue INSERT statements"

    def test_deletes_all_three_source_tables(self):
        source_tables_deleted: set[str] = set()

        def _mock_exec(sql: str, params: tuple = ()) -> int:
            if "DELETE" in sql.upper() and params:
                p = str(params[0])
                if "soc_design" in p:
                    source_tables_deleted.add("soc_design")
                if "ems_facility" in p:
                    source_tables_deleted.add("ems_facility")
                if "soc_design:fab" in p:
                    source_tables_deleted.add("soc_design:fab")
            return 0

        with (
            patch("kotodama.jukyu.adapter.execute", side_effect=_mock_exec),
            patch("kotodama.jukyu.adapter.fetch_one", return_value=(0,)),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            normalize_semiconductor()

        assert "soc_design" in source_tables_deleted
        assert "ems_facility" in source_tables_deleted
        assert "soc_design:fab" in source_tables_deleted


# ─── Error propagation ────────────────────────────────────────────────────────

class TestNormalizeSemiconductorErrors:
    def test_db_error_propagates(self):
        with (
            patch("kotodama.jukyu.adapter.execute", side_effect=RuntimeError("DB down")),
            patch("kotodama.jukyu.adapter.fetch_one", return_value=(0,)),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            with pytest.raises(RuntimeError, match="DB down"):
                normalize_semiconductor()

    def test_fetch_none_returns_zero_total(self):
        with (
            patch("kotodama.jukyu.adapter.execute", return_value=0),
            patch("kotodama.jukyu.adapter.fetch_one", return_value=None),
        ):
            from kotodama.jukyu.adapter import normalize_semiconductor
            result = normalize_semiconductor()
        assert result["jukyuSupplyNodesTotal"] == 0
        assert result["jukyuBalanceRowsTotal"] == 0
        assert result["jukyuExposureRowsTotal"] == 0
