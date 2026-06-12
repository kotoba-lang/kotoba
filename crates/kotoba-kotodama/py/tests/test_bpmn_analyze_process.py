from __future__ import annotations

import json
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")

    def _audf(*_args, **_kwargs):
        def _wrap(fn):
            return fn

        return _wrap

    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub

def _load_bpmn() -> types.ModuleType:
    src = _py_src / "kotodama" / "handlers" / "bpmn.py"
    spec = importlib.util.spec_from_file_location("_handler_bpmn_analyze_test", src)
    assert spec is not None and spec.loader is not None
    mod = types.ModuleType("_handler_bpmn_analyze_test")
    sys.modules["_handler_bpmn_analyze_test"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


bpmn = _load_bpmn()


def test_summarize_events_detects_bottlenecks_variants_and_errors() -> None:
    events_desc = [
        {
            "case_id": "case-2",
            "activity": "demo.render",
            "timestamp": "2026-04-29T10:04:00Z",
            "ts_ms": 4,
            "duration_ms": 120000,
            "status": "ok",
        },
        {
            "case_id": "case-1",
            "activity": "demo.publish",
            "timestamp": "2026-04-29T10:03:00Z",
            "ts_ms": 3,
            "duration_ms": 1000,
            "status": "error",
        },
        {
            "case_id": "case-1",
            "activity": "demo.render",
            "timestamp": "2026-04-29T10:02:00Z",
            "ts_ms": 2,
            "duration_ms": 90000,
            "status": "ok",
        },
        {
            "case_id": "case-1",
            "activity": "demo.script",
            "timestamp": "2026-04-29T10:01:00Z",
            "ts_ms": 1,
            "duration_ms": 3000,
            "status": "ok",
        },
    ]

    summary = bpmn._summarize_events(events_desc)

    assert summary["eventCount"] == 4
    assert summary["caseCount"] == 2
    assert summary["bottlenecks"][0]["activity"] == "demo.render"
    assert summary["bottlenecks"][0]["totalDurationMs"] == 210000
    assert summary["anomalies"]["errorEvents"][0]["activity"] == "demo.publish"
    assert summary["variants"][0]["sequence"] == "demo.script > demo.render > demo.publish"


def test_analyze_process_returns_stats_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        bpmn,
        "_fetch_audit_events",
        lambda _params: [
            {
                "case_id": "case-1",
                "activity": "demo.done",
                "timestamp": "2026-04-29T10:00:00Z",
                "ts_ms": 1,
                "duration_ms": 42,
                "status": "ok",
            }
        ],
    )

    out = json.loads(bpmn.analyze_process(json.dumps({"includeLlm": False, "limit": 10})))

    assert out["ok"] is True
    assert out["source"] == "vertex_repo_commit:com.etzhayyim.bpmn.audit"
    assert out["eventCount"] == 1
    assert out["llm"] is None
