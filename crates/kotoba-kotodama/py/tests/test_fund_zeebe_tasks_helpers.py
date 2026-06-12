"""Tests for pure helper functions in ingest/fund/zeebe_tasks.py."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund.zeebe_tasks import (
    _rows_from_any,
    _managers_from_any,
    _funds_from_any,
    task_fund_fetch_raw,
    task_fund_persist_artifact,
    task_fund_normalize_lp,
    task_fund_normalize_investment,
    task_fund_normalize_manager,
    task_fund_normalize_fund,
    task_fund_verify_coverage,
    task_fund_compute_returns,
    task_fund_enrich_entity,
    task_fund_plan_sources,
)


# ─── _rows_from_any ──────────────────────────────────────────────────────────

def test_rows_from_any_list_of_dicts() -> None:
    rows = _rows_from_any([{"a": 1}, {"b": 2}])
    assert rows == [{"a": 1}, {"b": 2}]


def test_rows_from_any_filters_non_dicts() -> None:
    rows = _rows_from_any([{"a": 1}, "not-a-dict", 42, None])
    assert rows == [{"a": 1}]


def test_rows_from_any_json_string() -> None:
    rows = _rows_from_any(json.dumps([{"x": 10}]))
    assert rows == [{"x": 10}]


def test_rows_from_any_empty_list() -> None:
    assert _rows_from_any([]) == []


def test_rows_from_any_none_returns_empty() -> None:
    assert _rows_from_any(None) == []


def test_rows_from_any_empty_string_returns_empty() -> None:
    assert _rows_from_any("") == []


def test_rows_from_any_invalid_json_raises() -> None:
    import pytest
    with pytest.raises(Exception):
        _rows_from_any("not json {")


def test_rows_from_any_json_non_list_returns_empty() -> None:
    assert _rows_from_any(json.dumps({"key": "value"})) == []


def test_rows_from_any_integer_returns_empty() -> None:
    assert _rows_from_any(42) == []


# ─── task_fund_fetch_raw ─────────────────────────────────────────────────────

def test_fetch_raw_returns_planned_status() -> None:
    result = asyncio.run(task_fund_fetch_raw(sourceId="sec-adv", shardKey="adv-00"))
    assert result["ok"] is True
    assert result["status"] == "planned"


def test_fetch_raw_echoes_source_id() -> None:
    result = asyncio.run(task_fund_fetch_raw(sourceId="gleif"))
    assert result["sourceId"] == "gleif"


def test_fetch_raw_artifact_is_none() -> None:
    result = asyncio.run(task_fund_fetch_raw())
    assert result["artifact"] is None


# ─── task_fund_persist_artifact ──────────────────────────────────────────────

def test_persist_artifact_empty_uri_returns_error() -> None:
    result = asyncio.run(task_fund_persist_artifact(artifactUri=""))
    assert result["ok"] is False
    assert "error" in result


def test_persist_artifact_success() -> None:
    result = asyncio.run(task_fund_persist_artifact(
        sourceId="sec-adv",
        artifactUri="s3://bucket/key.json",
        sha256="abc123",
        byteSize=1024,
        recordCount=100,
    ))
    assert result["ok"] is True
    assert result["artifact"]["uri"] == "s3://bucket/key.json"
    assert result["artifact"]["sha256"] == "abc123"
    assert result["artifact"]["byte_size"] == 1024
    assert result["artifact"]["record_count"] == 100


def test_persist_artifact_source_id_in_response() -> None:
    result = asyncio.run(task_fund_persist_artifact(
        sourceId="gleif", artifactUri="s3://x/y"
    ))
    assert result["artifact"]["source_id"] == "gleif"


# ─── task_fund_normalize_lp ──────────────────────────────────────────────────

def test_normalize_lp_returns_ok() -> None:
    result = asyncio.run(task_fund_normalize_lp(sourceId="sec-adv", rows=[]))
    assert result["ok"] is True


def test_normalize_lp_investors_is_empty() -> None:
    result = asyncio.run(task_fund_normalize_lp(rows=[{"x": 1}]))
    assert result["investors"] == []


def test_normalize_lp_counts_input_rows() -> None:
    result = asyncio.run(task_fund_normalize_lp(rows=[{"a": 1}, {"b": 2}]))
    assert result["recordsRead"] == 2


# ─── task_fund_normalize_investment ──────────────────────────────────────────

def test_normalize_investment_returns_ok() -> None:
    result = asyncio.run(task_fund_normalize_investment())
    assert result["ok"] is True


def test_normalize_investment_investees_and_investments_empty() -> None:
    result = asyncio.run(task_fund_normalize_investment(rows=[{"x": 1}]))
    assert result["investees"] == []
    assert result["investments"] == []


def test_normalize_investment_counts_rows() -> None:
    result = asyncio.run(task_fund_normalize_investment(rows=[{"a": 1}, {"b": 2}]))
    assert result["recordsRead"] == 2


# ─── task_fund_verify_coverage ───────────────────────────────────────────────

def test_verify_coverage_ok_when_written_lte_prepared() -> None:
    result = asyncio.run(task_fund_verify_coverage(recordsWritten=5, recordsPrepared=10))
    assert result["ok"] is True


def test_verify_coverage_ok_when_equal() -> None:
    result = asyncio.run(task_fund_verify_coverage(recordsWritten=5, recordsPrepared=5))
    assert result["ok"] is True


def test_verify_coverage_fail_when_written_gt_prepared() -> None:
    result = asyncio.run(task_fund_verify_coverage(recordsWritten=10, recordsPrepared=5))
    assert result["ok"] is False


def test_verify_coverage_echoes_counts() -> None:
    result = asyncio.run(task_fund_verify_coverage(recordsWritten=3, recordsPrepared=7))
    assert result["recordsWritten"] == 3
    assert result["recordsPrepared"] == 7


def test_verify_coverage_zero_zero_is_ok() -> None:
    result = asyncio.run(task_fund_verify_coverage(recordsWritten=0, recordsPrepared=0))
    assert result["ok"] is True


# ─── task_fund_compute_returns ───────────────────────────────────────────────

def test_compute_returns_ok_with_rows() -> None:
    result = asyncio.run(task_fund_compute_returns(metrics=[{"metricKind": "irr"}]))
    assert result["ok"] is True


def test_compute_returns_normalizes_metric_kind() -> None:
    result = asyncio.run(task_fund_compute_returns(metrics=[{"x": 1}]))
    assert result["ok"] is True
    assert result["metrics"][0]["metric_kind"] == "unknown"


def test_compute_returns_prefers_metric_kind_over_metricKind() -> None:
    result = asyncio.run(task_fund_compute_returns(
        metrics=[{"metric_kind": "irr", "metricKind": "moic"}]
    ))
    assert result["metrics"][0]["metric_kind"] == "irr"


def test_compute_returns_empty_metrics() -> None:
    result = asyncio.run(task_fund_compute_returns(metrics=[]))
    assert result["ok"] is True
    assert result["metrics"] == []


def test_compute_returns_has_warning() -> None:
    result = asyncio.run(task_fund_compute_returns())
    assert "warning" in result


# ─── task_fund_enrich_entity ─────────────────────────────────────────────────

def test_enrich_entity_requires_dict() -> None:
    result = asyncio.run(task_fund_enrich_entity(entity=None))
    assert result["ok"] is False
    assert "error" in result


def test_enrich_entity_passes_through_entity() -> None:
    entity = {"lei": "ABC", "legalName": "Acme Corp"}
    result = asyncio.run(task_fund_enrich_entity(entity=entity, gleifPayload={}))
    assert result["ok"] is True
    assert "entity" in result


# ─── task_fund_plan_sources ───────────────────────────────────────────────────

def test_plan_sources_sec_adv_returns_shards() -> None:
    result = asyncio.run(task_fund_plan_sources(sourceId="sec-adv", limit=3))
    assert result["ok"] is True
    assert len(result["shards"]) == 3


def test_plan_sources_unknown_source_returns_error() -> None:
    result = asyncio.run(task_fund_plan_sources(sourceId="unknown-source"))
    assert result["ok"] is False
    assert "error" in result


def test_plan_sources_all_returns_shards() -> None:
    result = asyncio.run(task_fund_plan_sources(sourceId="all", limit=2))
    assert result["ok"] is True


# ─── _managers_from_any ───────────────────────────────────────────────────────

def test_managers_from_any_list_of_dicts() -> None:
    data = [{"manager_id": "m1", "manager_name": "Acme Capital", "manager_type": "organization"}]
    result = _managers_from_any(data)
    assert len(result) == 1
    assert result[0].manager_id == "m1"
    assert result[0].manager_name == "Acme Capital"


def test_managers_from_any_empty_list() -> None:
    result = _managers_from_any([])
    assert result == []


def test_managers_from_any_none_returns_empty() -> None:
    result = _managers_from_any(None)
    assert result == []


def test_managers_from_any_json_string() -> None:
    data = json.dumps([{"manager_id": "m2", "manager_name": "Beta Fund", "manager_type": "company"}])
    result = _managers_from_any(data)
    assert len(result) == 1
    assert result[0].manager_id == "m2"


def test_managers_from_any_returns_list() -> None:
    result = _managers_from_any([{"manager_id": "m3", "manager_name": "Gamma", "manager_type": "organization"}])
    assert isinstance(result, list)


# ─── _funds_from_any ──────────────────────────────────────────────────────────

def test_funds_from_any_list_of_dicts() -> None:
    data = [{"fund_id": "f1", "name": "Alpha Fund I", "manager_id": "m1"}]
    result = _funds_from_any(data)
    assert len(result) == 1
    assert result[0].fund_id == "f1"
    assert result[0].name == "Alpha Fund I"


def test_funds_from_any_empty_list() -> None:
    assert _funds_from_any([]) == []


def test_funds_from_any_none_returns_empty() -> None:
    assert _funds_from_any(None) == []


def test_funds_from_any_json_string() -> None:
    data = json.dumps([{"fund_id": "f2", "name": "Beta Fund II", "manager_id": "m2"}])
    result = _funds_from_any(data)
    assert len(result) == 1
    assert result[0].fund_id == "f2"


def test_funds_from_any_returns_list() -> None:
    result = _funds_from_any([{"fund_id": "f3", "name": "Gamma", "manager_id": "m3"}])
    assert isinstance(result, list)


# ─── task_fund_normalize_manager ─────────────────────────────────────────────

def test_normalize_manager_unsupported_source_returns_error() -> None:
    result = asyncio.run(task_fund_normalize_manager(sourceId="unknown"))
    assert result["ok"] is False
    assert "unsupported" in result["error"]


def test_normalize_manager_sec_adv_empty_rows_returns_ok() -> None:
    result = asyncio.run(task_fund_normalize_manager(sourceId="sec-adv", rows=[]))
    assert result["ok"] is True


def test_normalize_manager_returns_managers_list() -> None:
    result = asyncio.run(task_fund_normalize_manager(sourceId="sec-adv", rows=[]))
    assert "managers" in result
    assert isinstance(result["managers"], list)


def test_normalize_manager_returns_funds_list() -> None:
    result = asyncio.run(task_fund_normalize_manager(sourceId="sec-adv", rows=[]))
    assert "funds" in result
    assert isinstance(result["funds"], list)


def test_normalize_manager_echoes_source_id() -> None:
    result = asyncio.run(task_fund_normalize_manager(sourceId="sec-adv", rows=[]))
    assert result["sourceId"] == "sec-adv"


# ─── task_fund_normalize_fund ────────────────────────────────────────────────

def test_normalize_fund_unsupported_source_returns_error() -> None:
    result = asyncio.run(task_fund_normalize_fund(sourceId="unknown"))
    assert result["ok"] is False


def test_normalize_fund_sec_adv_empty_rows_returns_ok() -> None:
    result = asyncio.run(task_fund_normalize_fund(sourceId="sec-adv", rows=[]))
    assert result["ok"] is True


def test_normalize_fund_returns_funds_list() -> None:
    result = asyncio.run(task_fund_normalize_fund(sourceId="sec-adv", rows=[]))
    assert "funds" in result
    assert isinstance(result["funds"], list)


def test_normalize_fund_echoes_source_id() -> None:
    result = asyncio.run(task_fund_normalize_fund(sourceId="sec-adv", rows=[]))
    assert result["sourceId"] == "sec-adv"
