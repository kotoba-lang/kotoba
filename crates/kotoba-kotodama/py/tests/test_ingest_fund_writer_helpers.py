"""Tests for pure helper functions in ingest/fund/writer.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund import writer as FW
from kotodama.ingest.fund.types import NormalizedFundManager, NormalizedFund


def _make_manager(**kwargs) -> NormalizedFundManager:
    defaults = {
        "manager_id": "mgr-001",
        "manager_name": "Acme Capital",
        "manager_type": "organization",
        "source_url": "https://example.com",
        "confidence": 0.9,
    }
    defaults.update(kwargs)
    return NormalizedFundManager(**defaults)


def _make_fund(**kwargs) -> NormalizedFund:
    defaults = {
        "fund_id": "fund-001",
        "name": "Acme Fund I",
        "fund_kind": "private_equity",
        "manager_id": "mgr-001",
        "manager_name": "Acme Capital",
        "source_url": "https://example.com",
        "confidence": 0.9,
    }
    defaults.update(kwargs)
    return NormalizedFund(**defaults)


# ─── manager_row ─────────────────────────────────────────────────────────────

def test_fw_manager_row_has_vertex_id() -> None:
    manager = _make_manager()
    row = FW.manager_row(manager)
    assert "vertex_id" in row
    assert row["vertex_id"].startswith("at://")


def test_fw_manager_row_has_manager_fields() -> None:
    manager = _make_manager(manager_name="Test Capital")
    row = FW.manager_row(manager)
    assert row["manager_name"] == "Test Capital"
    assert row["manager_id"] == "mgr-001"


def test_fw_manager_row_no_none_values() -> None:
    manager = _make_manager()
    row = FW.manager_row(manager)
    # All None values should be explicitly set or omitted
    assert "vertex_id" in row
    assert "created_date" in row


# ─── fund_row ────────────────────────────────────────────────────────────────

def test_fw_fund_row_has_vertex_id() -> None:
    fund = _make_fund()
    row = FW.fund_row(fund)
    assert "vertex_id" in row
    assert row["vertex_id"].startswith("at://")


def test_fw_fund_row_has_fund_fields() -> None:
    fund = _make_fund(name="My Fund II", fund_kind="hedge_fund")
    row = FW.fund_row(fund)
    assert row["name"] == "My Fund II"
    assert row["fund_kind"] == "hedge_fund"


def test_fw_fund_row_has_manager_did() -> None:
    fund = _make_fund(manager_id="mgr-abc")
    row = FW.fund_row(fund)
    assert "manager_did" in row
    assert "mgr-abc" in row["manager_did"]


# ─── managed_by_edge ─────────────────────────────────────────────────────────

def test_fw_managed_by_edge_has_required_keys() -> None:
    fund = _make_fund()
    edge = FW.managed_by_edge(fund)
    assert "edge_id" in edge
    assert "src_vid" in edge
    assert "dst_vid" in edge
    assert edge["relationship"] == "managed_by"


def test_fw_managed_by_edge_links_fund_to_manager() -> None:
    fund = _make_fund(fund_id="f1", manager_id="m1")
    edge = FW.managed_by_edge(fund)
    assert "f1" in edge["src_vid"] or "f-1" in edge["src_vid"] or "f1" in edge["src_vid"].lower()
    assert "m1" in edge["dst_vid"] or "m-1" in edge["dst_vid"] or "m1" in edge["dst_vid"].lower()


# ─── graph_rows ──────────────────────────────────────────────────────────────

def test_fw_graph_rows_structure() -> None:
    managers = [_make_manager()]
    funds = [_make_fund()]
    result = FW.graph_rows(managers, funds)
    assert "vertex_fund_manager" in result
    assert "vertex_fund" in result
    assert "edge_fund_managed_by" in result


def test_fw_graph_rows_counts() -> None:
    managers = [_make_manager(), _make_manager(manager_id="mgr-002", manager_name="Beta Capital")]
    funds = [_make_fund(), _make_fund(fund_id="fund-002", name="Beta Fund")]
    result = FW.graph_rows(managers, funds)
    assert len(result["vertex_fund_manager"]) == 2
    assert len(result["vertex_fund"]) == 2
    assert len(result["edge_fund_managed_by"]) == 2


def test_fw_graph_rows_empty_inputs() -> None:
    result = FW.graph_rows([], [])
    assert result["vertex_fund_manager"] == []
    assert result["vertex_fund"] == []
    assert result["edge_fund_managed_by"] == []
