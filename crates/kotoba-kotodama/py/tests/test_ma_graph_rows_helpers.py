"""Tests for _now_iso, _today, and graph_rows pure helpers in primitives/ma.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import ma as MA


# ─── _now_iso ────────────────────────────────────────────────────────────────

def test_ma_now_iso_ends_with_z() -> None:
    assert MA._now_iso().endswith("Z")


def test_ma_now_iso_matches_pattern() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", MA._now_iso())


def test_ma_now_iso_no_microseconds() -> None:
    assert "." not in MA._now_iso()


def test_ma_now_iso_has_t_separator() -> None:
    assert "T" in MA._now_iso()


# ─── _today ──────────────────────────────────────────────────────────────────

def test_ma_today_matches_date_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", MA._today())


def test_ma_today_no_time_component() -> None:
    assert "T" not in MA._today()


def test_ma_today_returns_string() -> None:
    assert isinstance(MA._today(), str)


# ─── graph_rows structure ────────────────────────────────────────────────────

def test_graph_rows_returns_dict() -> None:
    result = MA.graph_rows(dealId="deal-001")
    assert isinstance(result, dict)


def test_graph_rows_has_vertex_ma_deal_key() -> None:
    result = MA.graph_rows(dealId="deal-001")
    assert "vertex_ma_deal" in result
    assert len(result["vertex_ma_deal"]) == 1


def test_graph_rows_deal_has_vertex_id() -> None:
    result = MA.graph_rows(dealId="deal-001")
    deal = result["vertex_ma_deal"][0]
    assert "vertex_id" in deal
    assert deal["vertex_id"].startswith("at://")


def test_graph_rows_deal_id_propagated() -> None:
    result = MA.graph_rows(dealId="deal-abc")
    deal = result["vertex_ma_deal"][0]
    assert deal["deal_id"] == "deal-abc"


def test_graph_rows_side_propagated() -> None:
    result = MA.graph_rows(dealId="d001", side="buy-side")
    deal = result["vertex_ma_deal"][0]
    assert deal["side"] == "buy-side"


def test_graph_rows_status_propagated() -> None:
    result = MA.graph_rows(dealId="d001", status="active")
    deal = result["vertex_ma_deal"][0]
    assert deal["status"] == "active"


def test_graph_rows_sector_propagated() -> None:
    result = MA.graph_rows(dealId="d001", sector="technology")
    deal = result["vertex_ma_deal"][0]
    assert deal["sector"] == "technology"


def test_graph_rows_no_target_empty_candidate_list() -> None:
    result = MA.graph_rows(dealId="d001")
    assert result["vertex_ma_candidate"] == []
    assert result["edge_ma_deal_candidate"] == []


def test_graph_rows_target_creates_candidate() -> None:
    result = MA.graph_rows(dealId="d001", targetName="Acme Corp")
    assert len(result["vertex_ma_candidate"]) == 1
    candidate = result["vertex_ma_candidate"][0]
    assert candidate["candidate_name"] == "Acme Corp"
    assert candidate["candidate_kind"] == "target"


def test_graph_rows_target_creates_edge() -> None:
    result = MA.graph_rows(dealId="d001", targetName="Acme Corp")
    assert len(result["edge_ma_deal_candidate"]) == 1
    edge = result["edge_ma_deal_candidate"][0]
    assert "edge_id" in edge
    assert "src_vid" in edge and "dst_vid" in edge


def test_graph_rows_auto_generated_deal_id_when_empty() -> None:
    result = MA.graph_rows(
        dealId="",
        clientName="Client",
        targetName="Target",
        sector="tech",
    )
    deal = result["vertex_ma_deal"][0]
    assert deal["deal_id"]  # auto-generated, not empty


def test_graph_rows_expected_value_propagated() -> None:
    result = MA.graph_rows(dealId="d001", expectedValueUsd=1_000_000.0)
    deal = result["vertex_ma_deal"][0]
    assert deal["expected_value_usd"] == 1_000_000.0


def test_graph_rows_has_all_required_keys() -> None:
    result = MA.graph_rows(dealId="d001")
    expected_keys = {
        "vertex_ma_deal",
        "vertex_ma_candidate",
        "vertex_ma_valuation",
        "vertex_ma_match",
        "edge_ma_deal_candidate",
        "edge_ma_deal_buyer",
    }
    assert expected_keys.issubset(result.keys())


def test_graph_rows_created_date_is_date_format() -> None:
    result = MA.graph_rows(dealId="d001")
    created_date = result["vertex_ma_deal"][0]["created_date"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", created_date)
