"""Tests for pure helper functions in ingest/site_common_crawl.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import site_common_crawl as SCC


# ─── _truthy ─────────────────────────────────────────────────────────────────

def test_scc_truthy_one_is_true() -> None:
    assert SCC._truthy("1") is True


def test_scc_truthy_true_is_true() -> None:
    assert SCC._truthy("true") is True


def test_scc_truthy_yes_is_true() -> None:
    assert SCC._truthy("yes") is True


def test_scc_truthy_on_is_true() -> None:
    assert SCC._truthy("on") is True


def test_scc_truthy_case_insensitive() -> None:
    assert SCC._truthy("TRUE") is True
    assert SCC._truthy("YES") is True


def test_scc_truthy_zero_is_false() -> None:
    assert SCC._truthy("0") is False


def test_scc_truthy_false_is_false() -> None:
    assert SCC._truthy("false") is False


def test_scc_truthy_none_is_false() -> None:
    assert SCC._truthy(None) is False


def test_scc_truthy_empty_is_false() -> None:
    assert SCC._truthy("") is False


def test_scc_truthy_arbitrary_string_is_false() -> None:
    assert SCC._truthy("maybe") is False


# ─── _data_dir ───────────────────────────────────────────────────────────────

def test_scc_data_dir_explicit_arg(monkeypatch) -> None:
    result = SCC._data_dir("/custom/path")
    assert str(result) == "/custom/path"


def test_scc_data_dir_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SITE_CC_DATA_DIR", "/env/path")
    result = SCC._data_dir()
    assert str(result) == "/env/path"


def test_scc_data_dir_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SITE_CC_DATA_DIR", raising=False)
    monkeypatch.delenv("CC_DATA_DIR", raising=False)
    result = SCC._data_dir()
    assert isinstance(result, Path)


# ─── _etzhayyim_binary ────────────────────────────────────────────────────────────

def test_scc_etzhayyim_binary_from_env(monkeypatch) -> None:
    monkeypatch.setenv("etzhayyim_BIN", "/usr/local/bin/etzhayyim")
    result = SCC._etzhayyim_binary()
    assert result == "/usr/local/bin/etzhayyim"


def test_scc_etzhayyim_binary_default_fallback(monkeypatch) -> None:
    monkeypatch.delenv("etzhayyim_BIN", raising=False)
    result = SCC._etzhayyim_binary()
    assert isinstance(result, str)
    assert len(result) > 0


# ─── _repo_root ───────────────────────────────────────────────────────────────

def test_repo_root_env_var_takes_priority(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SITE_CC_REPO_ROOT", str(tmp_path))
    result = SCC._repo_root()
    assert result == tmp_path


def test_repo_root_repo_root_env_var(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SITE_CC_REPO_ROOT", raising=False)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    result = SCC._repo_root()
    assert result == tmp_path


def test_repo_root_returns_path_or_none(monkeypatch) -> None:
    monkeypatch.delenv("SITE_CC_REPO_ROOT", raising=False)
    monkeypatch.delenv("REPO_ROOT", raising=False)
    result = SCC._repo_root()
    assert result is None or isinstance(result, Path)


def test_repo_root_site_cc_takes_priority_over_repo_root(monkeypatch, tmp_path) -> None:
    site_cc_path = tmp_path / "site_cc"
    repo_root_path = tmp_path / "repo_root"
    monkeypatch.setenv("SITE_CC_REPO_ROOT", str(site_cc_path))
    monkeypatch.setenv("REPO_ROOT", str(repo_root_path))
    result = SCC._repo_root()
    assert result == site_cc_path


# ─── _artifact_stats ─────────────────────────────────────────────────────────

def test_artifact_stats_empty_dir_has_zero_counts(tmp_path) -> None:
    result = SCC._artifact_stats(tmp_path)
    assert result["graphSqlFiles"] == 0
    assert result["parquetPageFiles"] == 0
    assert result["domainIntelExists"] is False
    assert result["knowledgeGraphExists"] is False


def test_artifact_stats_data_dir_in_result(tmp_path) -> None:
    result = SCC._artifact_stats(tmp_path)
    assert result["dataDir"] == str(tmp_path)


def test_artifact_stats_returns_dict(tmp_path) -> None:
    result = SCC._artifact_stats(tmp_path)
    assert isinstance(result, dict)


def test_artifact_stats_domain_intel_detected(tmp_path) -> None:
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    intel = graph_dir / "domain_intel.jsonl.gz"
    intel.write_bytes(b"fake")
    result = SCC._artifact_stats(tmp_path)
    assert result["domainIntelExists"] is True
    assert result["domainIntelBytes"] == 4


def test_artifact_stats_knowledge_graph_detected(tmp_path) -> None:
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    kg = graph_dir / "knowledge_graph.sql"
    kg.write_text("SELECT 1")
    result = SCC._artifact_stats(tmp_path)
    assert result["knowledgeGraphExists"] is True
    assert result["knowledgeGraphBytes"] == 8


def test_artifact_stats_sql_files_counted(tmp_path) -> None:
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    for i in range(3):
        (graph_dir / f"did_batch_{i}.sql").write_text("")
    result = SCC._artifact_stats(tmp_path)
    assert result["graphSqlFiles"] == 3


def test_artifact_stats_parquet_files_counted(tmp_path) -> None:
    parquet_dir = tmp_path / "parquet-rs"
    parquet_dir.mkdir()
    for i in range(2):
        (parquet_dir / f"shard{i}_pages.parquet").write_bytes(b"x")
    result = SCC._artifact_stats(tmp_path)
    assert result["parquetPageFiles"] == 2


def test_artifact_stats_missing_files_bytes_zero(tmp_path) -> None:
    result = SCC._artifact_stats(tmp_path)
    assert result["domainIntelBytes"] == 0
    assert result["knowledgeGraphBytes"] == 0
