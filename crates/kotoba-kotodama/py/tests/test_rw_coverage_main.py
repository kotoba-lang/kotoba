from __future__ import annotations

import json
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import rw_coverage_main as C


class _Coverage:
    table_count = 3
    column_count = 12
    vertex_table_count = 1
    edge_table_count = 1
    graph_table_count = 2
    graph_table_ratio = 2 / 3


def test_build_coverage_payload(monkeypatch) -> None:
    monkeypatch.setattr(C, "live_migration_coverage", lambda schema: _Coverage())
    payload = C.build_coverage_payload("public")
    assert payload["ok"] is True
    assert payload["schema"] == "public"
    assert payload["tableCount"] == 3
    assert payload["columnCount"] == 12
    assert payload["graphTableCount"] == 2


def test_evaluate_thresholds_returns_failures() -> None:
    payload = {
        "tableCount": 3,
        "columnCount": 12,
        "vertexTableCount": 1,
        "edgeTableCount": 1,
        "graphTableRatio": 2 / 3,
    }
    failures = C.evaluate_thresholds(
        payload,
        min_tables=4,
        min_columns=20,
        min_vertex_tables=2,
        min_edge_tables=2,
        min_graph_ratio=0.9,
    )
    assert [failure["metric"] for failure in failures] == [
        "tableCount",
        "columnCount",
        "vertexTableCount",
        "edgeTableCount",
        "graphTableRatio",
    ]


def test_build_coverage_payload_marks_threshold_failure(monkeypatch) -> None:
    monkeypatch.setattr(C, "live_migration_coverage", lambda schema: _Coverage())
    payload = C.build_coverage_payload("public", min_tables=4)
    assert payload["ok"] is False
    assert payload["failedChecks"][0]["metric"] == "tableCount"


def test_main_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(C, "live_migration_coverage", lambda schema: _Coverage())
    assert C.main(["--schema", "public"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["schema"] == "public"


def test_main_returns_nonzero_on_threshold_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(C, "live_migration_coverage", lambda schema: _Coverage())
    assert C.main(["--min-tables", "4"]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["failedChecks"][0]["minimum"] == 4


def test_main_returns_nonzero_on_error(monkeypatch, capsys) -> None:
    def _raise(schema: str) -> _Coverage:
        raise RuntimeError(f"cannot reach {schema}")

    monkeypatch.setattr(C, "live_migration_coverage", _raise)
    assert C.main(["--schema", "dev"]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "cannot reach dev" in payload["error"]
