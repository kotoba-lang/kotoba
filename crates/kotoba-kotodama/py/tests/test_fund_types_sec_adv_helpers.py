"""Tests for pure helpers in ingest/fund/types.py and ingest/fund/sec_adv.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund.types import (
    drop_none,
    FundSourceConfig,
    RawArtifact,
    NormalizedFundManager,
    NormalizedFund,
    NormalizedInvestor,
    NormalizedInvestee,
    FundMetric,
    FundIntelBatch,
)
from kotodama.ingest.fund.sec_adv import (
    plan_sec_adv_shards,
    _first,
    _float_or_none,
)


# ─── drop_none ───────────────────────────────────────────────────────────────

def test_drop_none_removes_none_values() -> None:
    result = drop_none({"a": 1, "b": None, "c": "x"})
    assert result == {"a": 1, "c": "x"}


def test_drop_none_removes_empty_strings() -> None:
    result = drop_none({"a": "", "b": "hello"})
    assert result == {"b": "hello"}


def test_drop_none_all_valid() -> None:
    d = {"x": 0, "y": False, "z": 1}
    result = drop_none(d)
    assert result == {"x": 0, "y": False, "z": 1}


def test_drop_none_empty_dict() -> None:
    assert drop_none({}) == {}


def test_drop_none_all_none() -> None:
    result = drop_none({"a": None, "b": None})
    assert result == {}


# ─── FundSourceConfig.to_dict ─────────────────────────────────────────────

def test_fund_source_config_to_dict_basic() -> None:
    cfg = FundSourceConfig(source_id="sec-adv", source_kind="form-adv")
    d = cfg.to_dict()
    assert d["source_id"] == "sec-adv"
    assert d["source_kind"] == "form-adv"


def test_fund_source_config_to_dict_drops_empty_url() -> None:
    cfg = FundSourceConfig(source_id="sec-adv", source_kind="form-adv", source_url="")
    d = cfg.to_dict()
    assert "source_url" not in d


def test_fund_source_config_to_dict_includes_url_when_set() -> None:
    cfg = FundSourceConfig(source_id="sec-adv", source_kind="form-adv",
                           source_url="https://example.com/data")
    d = cfg.to_dict()
    assert d["source_url"] == "https://example.com/data"


def test_fund_source_config_shard_key_default() -> None:
    cfg = FundSourceConfig(source_id="x", source_kind="y")
    assert cfg.shard_key == "default"


# ─── RawArtifact.to_dict ──────────────────────────────────────────────────

def test_raw_artifact_to_dict_basic() -> None:
    a = RawArtifact(source_id="gleif", artifact_kind="json", uri="s3://b/k")
    d = a.to_dict()
    assert d["source_id"] == "gleif"
    assert d["uri"] == "s3://b/k"


def test_raw_artifact_to_dict_drops_none_byte_size() -> None:
    a = RawArtifact(source_id="x", artifact_kind="y", uri="z", byte_size=None)
    d = a.to_dict()
    assert "byte_size" not in d


def test_raw_artifact_to_dict_keeps_byte_size_when_set() -> None:
    a = RawArtifact(source_id="x", artifact_kind="y", uri="z", byte_size=1024)
    d = a.to_dict()
    assert d["byte_size"] == 1024


# ─── NormalizedFundManager.to_dict ───────────────────────────────────────

def test_normalized_fund_manager_to_dict_required_fields() -> None:
    mgr = NormalizedFundManager(manager_id="m1", manager_name="Acme Capital")
    d = mgr.to_dict()
    assert d["manager_id"] == "m1"
    assert d["manager_name"] == "Acme Capital"


def test_normalized_fund_manager_default_type() -> None:
    mgr = NormalizedFundManager(manager_id="m1", manager_name="Acme")
    assert mgr.manager_type == "organization"


def test_normalized_fund_manager_aum_none_dropped() -> None:
    mgr = NormalizedFundManager(manager_id="m1", manager_name="Acme", aum_amount=None)
    d = mgr.to_dict()
    assert "aum_amount" not in d


def test_normalized_fund_manager_aum_included_when_set() -> None:
    mgr = NormalizedFundManager(manager_id="m1", manager_name="Acme", aum_amount=1e9)
    d = mgr.to_dict()
    assert d["aum_amount"] == 1e9


# ─── NormalizedFund.to_dict ───────────────────────────────────────────────

def test_normalized_fund_required_fields() -> None:
    fund = NormalizedFund(fund_id="f1", name="Beta Fund", manager_id="m1")
    d = fund.to_dict()
    assert d["fund_id"] == "f1"
    assert d["name"] == "Beta Fund"
    assert d["manager_id"] == "m1"


def test_normalized_fund_vintage_none_dropped() -> None:
    fund = NormalizedFund(fund_id="f1", name="X", manager_id="m1", vintage_year=None)
    d = fund.to_dict()
    assert "vintage_year" not in d


def test_normalized_fund_vintage_kept_when_set() -> None:
    fund = NormalizedFund(fund_id="f1", name="X", manager_id="m1", vintage_year=2020)
    d = fund.to_dict()
    assert d["vintage_year"] == 2020


# ─── NormalizedInvestor / NormalizedInvestee ──────────────────────────────

def test_normalized_investor_to_dict() -> None:
    inv = NormalizedInvestor(investor_id="i1", investor_name="Pension Fund")
    d = inv.to_dict()
    assert d["investor_id"] == "i1"
    assert d["investor_name"] == "Pension Fund"
    assert d["investor_type"] == "lp"


def test_normalized_investee_to_dict() -> None:
    ie = NormalizedInvestee(investee_id="c1", investee_name="StartupCo")
    d = ie.to_dict()
    assert d["investee_id"] == "c1"
    assert d["investee_name"] == "StartupCo"
    assert d["investee_type"] == "company"


# ─── FundMetric.to_dict ───────────────────────────────────────────────────

def test_fund_metric_to_dict() -> None:
    m = FundMetric(subject_id="f1", metric_name="irr", value=0.18)
    d = m.to_dict()
    assert d["subject_id"] == "f1"
    assert d["metric_name"] == "irr"
    assert d["value"] == 0.18


def test_fund_metric_metric_kind_default() -> None:
    m = FundMetric(subject_id="f1", metric_name="irr", value=0.18)
    assert m.metric_kind == "unknown"


# ─── FundIntelBatch.to_dict ───────────────────────────────────────────────

def test_fund_intel_batch_to_dict_empty() -> None:
    b = FundIntelBatch(source_id="gleif")
    d = b.to_dict()
    assert d["sourceId"] == "gleif"
    assert d["managers"] == []
    assert d["funds"] == []
    assert d["investors"] == []
    assert d["investees"] == []
    assert d["metrics"] == []
    assert d["artifacts"] == []


def test_fund_intel_batch_to_dict_with_manager() -> None:
    mgr = NormalizedFundManager(manager_id="m1", manager_name="Alpha")
    b = FundIntelBatch(source_id="sec-adv", managers=[mgr])
    d = b.to_dict()
    assert len(d["managers"]) == 1
    assert d["managers"][0]["manager_id"] == "m1"


# ─── plan_sec_adv_shards ──────────────────────────────────────────────────

def test_plan_sec_adv_shards_count() -> None:
    shards = plan_sec_adv_shards(limit=5)
    assert len(shards) == 5


def test_plan_sec_adv_shards_source_id() -> None:
    shards = plan_sec_adv_shards(limit=1)
    assert shards[0].source_id == "sec-adv"


def test_plan_sec_adv_shards_shard_keys_unique() -> None:
    shards = plan_sec_adv_shards(limit=10)
    keys = [s.shard_key for s in shards]
    assert len(set(keys)) == 10


def test_plan_sec_adv_shards_limit_1() -> None:
    shards = plan_sec_adv_shards(limit=1)
    assert len(shards) == 1


def test_plan_sec_adv_shards_mode_forwarded() -> None:
    shards = plan_sec_adv_shards(mode="full", limit=2)
    assert all(s.mode == "full" for s in shards)


def test_plan_sec_adv_shards_capped_at_50() -> None:
    shards = plan_sec_adv_shards(limit=100)
    assert len(shards) == 50


# ─── _first ──────────────────────────────────────────────────────────────

def test_first_returns_first_non_empty() -> None:
    row = {"a": "", "b": "hello", "c": "world"}
    assert _first(row, "a", "b", "c") == "hello"


def test_first_returns_empty_if_all_missing() -> None:
    row = {"x": None, "y": ""}
    assert _first(row, "x", "y") == ""


def test_first_returns_first_key_when_available() -> None:
    row = {"name": "Alice", "display": "Bob"}
    assert _first(row, "name", "display") == "Alice"


def test_first_missing_keys_returns_empty() -> None:
    row = {}
    assert _first(row, "a", "b") == ""


# ─── _float_or_none ──────────────────────────────────────────────────────

def test_float_or_none_valid_string() -> None:
    assert _float_or_none("3.14") == 3.14


def test_float_or_none_with_commas() -> None:
    assert _float_or_none("1,234,567.89") == 1234567.89


def test_float_or_none_empty_string() -> None:
    assert _float_or_none("") is None


def test_float_or_none_none_input() -> None:
    assert _float_or_none(None) is None


def test_float_or_none_non_numeric_returns_none() -> None:
    assert _float_or_none("N/A") is None


def test_float_or_none_integer_string() -> None:
    assert _float_or_none("42") == 42.0
