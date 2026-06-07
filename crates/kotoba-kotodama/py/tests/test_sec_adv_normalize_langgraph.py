"""Tests for normalize_sec_adv_rows/csv (sec_adv.py) and langgraph_registry."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund.sec_adv import (
    normalize_sec_adv_rows,
    normalize_sec_adv_csv,
)
from kotodama.primitives import langgraph_registry


# ─── normalize_sec_adv_rows ──────────────────────────────────────────────────

def test_normalize_rows_empty_returns_empty() -> None:
    managers, funds = normalize_sec_adv_rows([])
    assert managers == []
    assert funds == []


def test_normalize_rows_row_without_name_skipped() -> None:
    managers, funds = normalize_sec_adv_rows([{"CIK": "123"}])
    assert managers == []


def test_normalize_rows_single_manager() -> None:
    row = {"Primary Business Name": "Acme Advisers", "CIK": "0001234567"}
    managers, funds = normalize_sec_adv_rows([row])
    assert len(managers) == 1
    assert managers[0].manager_name == "Acme Advisers"


def test_normalize_rows_manager_type_is_investment_adviser() -> None:
    row = {"Primary Business Name": "Beta Capital"}
    managers, _ = normalize_sec_adv_rows([row])
    assert managers[0].manager_type == "investment_adviser"


def test_normalize_rows_regulator_is_sec() -> None:
    row = {"Primary Business Name": "Gamma Partners"}
    managers, _ = normalize_sec_adv_rows([row])
    assert managers[0].regulator == "SEC"


def test_normalize_rows_aum_parsed_from_string() -> None:
    row = {
        "Primary Business Name": "Delta Fund",
        "Regulatory Assets Under Management": "1,500,000,000",
    }
    managers, _ = normalize_sec_adv_rows([row])
    assert managers[0].aum_amount == 1_500_000_000.0


def test_normalize_rows_aum_none_when_missing() -> None:
    row = {"Primary Business Name": "Epsilon Mgmt"}
    managers, _ = normalize_sec_adv_rows([row])
    assert managers[0].aum_amount is None


def test_normalize_rows_fund_created_when_private_fund_name() -> None:
    row = {
        "Primary Business Name": "Zeta Partners",
        "Private Fund Name": "Zeta Fund I",
    }
    managers, funds = normalize_sec_adv_rows([row])
    assert len(funds) == 1
    assert funds[0].name == "Zeta Fund I"


def test_normalize_rows_no_fund_without_fund_name() -> None:
    row = {"Primary Business Name": "Eta Advisers"}
    _, funds = normalize_sec_adv_rows([row])
    assert funds == []


def test_normalize_rows_deduplicates_managers() -> None:
    row = {"Primary Business Name": "Theta Capital", "CIK": "0009876543"}
    managers, _ = normalize_sec_adv_rows([row, row])
    assert len(managers) == 1


def test_normalize_rows_source_url_forwarded() -> None:
    row = {"Primary Business Name": "Iota Mgmt"}
    managers, _ = normalize_sec_adv_rows([row], source_url="https://sec.gov/x")
    assert managers[0].source_url == "https://sec.gov/x"


def test_normalize_rows_confidence_is_float() -> None:
    row = {"Primary Business Name": "Kappa LP"}
    managers, _ = normalize_sec_adv_rows([row])
    assert 0.0 < managers[0].confidence <= 1.0


def test_normalize_rows_fund_kind_is_private_fund() -> None:
    row = {
        "Primary Business Name": "Lambda Partners",
        "Private Fund Name": "Lambda I",
    }
    _, funds = normalize_sec_adv_rows([row])
    assert funds[0].fund_kind == "private_fund"


# ─── normalize_sec_adv_csv ────────────────────────────────────────────────────

def test_normalize_csv_minimal() -> None:
    csv_text = "Primary Business Name,CIK\nAlpha Advisers,0001111111\n"
    managers, funds = normalize_sec_adv_csv(csv_text)
    assert len(managers) == 1
    assert managers[0].manager_name == "Alpha Advisers"


def test_normalize_csv_empty_data_returns_empty() -> None:
    csv_text = "Primary Business Name,CIK\n"
    managers, funds = normalize_sec_adv_csv(csv_text)
    assert managers == []
    assert funds == []


def test_normalize_csv_with_fund() -> None:
    csv_text = "Primary Business Name,Private Fund Name\nBeta Mgmt,Beta Fund I\n"
    managers, funds = normalize_sec_adv_csv(csv_text)
    assert len(managers) == 1
    assert len(funds) == 1


def test_normalize_csv_multiple_rows() -> None:
    csv_text = (
        "Primary Business Name,CIK\n"
        "Firm A,0001000001\n"
        "Firm B,0001000002\n"
        "Firm C,0001000003\n"
    )
    managers, _ = normalize_sec_adv_csv(csv_text)
    assert len(managers) == 3


# ─── langgraph_registry ──────────────────────────────────────────────────────

def test_langgraph_registry_register_and_get() -> None:
    sentinel = object()
    langgraph_registry.register("test.graph.v1", sentinel)
    assert langgraph_registry.get("test.graph.v1") is sentinel


def test_langgraph_registry_get_unknown_returns_none() -> None:
    assert langgraph_registry.get("non.existent.graph") is None


def test_langgraph_registry_list_ids_includes_registered() -> None:
    langgraph_registry.register("test.graph.list", object())
    ids = langgraph_registry.list_ids()
    assert "test.graph.list" in ids


def test_langgraph_registry_list_ids_returns_list() -> None:
    ids = langgraph_registry.list_ids()
    assert isinstance(ids, list)


def test_langgraph_registry_overwrite() -> None:
    obj1 = object()
    obj2 = object()
    langgraph_registry.register("test.graph.overwrite", obj1)
    langgraph_registry.register("test.graph.overwrite", obj2)
    assert langgraph_registry.get("test.graph.overwrite") is obj2
