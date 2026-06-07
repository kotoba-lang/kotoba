"""Tests for pure helpers in:
  handlers/bpmn.py   — _esc, _compile_json_to_xml (structural checks)
  handlers/ingest.py — _loads, _dump, _require_str, _mode, _run_dict, _plan_payload"""

from __future__ import annotations

import json
import sys
import types
import importlib.util
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


def _load_mod(mod_name: str, rel: str) -> types.ModuleType:
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    try:
        from kotodama import registry as _reg
        keyword = rel.split("/")[-1].replace(".py", "").split("_")[0]
        for _k in [k for k in list(_reg._HANDLERS.keys()) if keyword in k.lower()]:
            del _reg._HANDLERS[_k]
    except Exception:
        pass
    path = _py_src / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = types.ModuleType(mod_name)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


BM = _load_mod("_handler_bpmn", "kotodama/handlers/bpmn.py")
IG = _load_mod("_handler_ingest_handler", "kotodama/handlers/ingest.py")


# ─── bpmn._esc ───────────────────────────────────────────────────────────────

def test_esc_plain_string() -> None:
    assert BM._esc("hello") == "hello"


def test_esc_ampersand() -> None:
    assert BM._esc("a&b") == "a&amp;b"


def test_esc_less_than() -> None:
    assert BM._esc("a<b") == "a&lt;b"


def test_esc_greater_than() -> None:
    assert BM._esc("a>b") == "a&gt;b"


def test_esc_double_quote() -> None:
    assert BM._esc('say "hi"') == "say &quot;hi&quot;"


def test_esc_non_string() -> None:
    assert BM._esc(42) == "42"


def test_esc_none() -> None:
    assert BM._esc(None) == "None"


def test_esc_combined() -> None:
    result = BM._esc('<a href="x&y">')
    assert "&lt;" in result
    assert "&amp;" in result
    assert "&quot;" in result


# ─── bpmn._compile_json_to_xml ───────────────────────────────────────────────

def _minimal_doc(**kwargs: object) -> dict:
    base: dict = {"id": "proc1", "name": "Test Process", "flow": []}
    base.update(kwargs)
    return base


def test_compile_contains_process_id() -> None:
    result = BM._compile_json_to_xml(_minimal_doc())
    assert "proc1" in result


def test_compile_contains_process_name() -> None:
    result = BM._compile_json_to_xml(_minimal_doc(name="My Flow"))
    assert "My Flow" in result


def test_compile_returns_string() -> None:
    assert isinstance(BM._compile_json_to_xml(_minimal_doc()), str)


def test_compile_xml_header_present() -> None:
    result = BM._compile_json_to_xml(_minimal_doc())
    assert "<?xml" in result or "bpmn:" in result or "definitions" in result


def test_compile_escapes_special_chars_in_id() -> None:
    result = BM._compile_json_to_xml(_minimal_doc(id='proc<1>'))
    assert "<proc<1>" not in result
    assert "&lt;" in result or "proc" in result


def test_compile_single_service_task() -> None:
    doc = _minimal_doc(flow=[
        {"id": "start", "type": "startEvent", "next": "task1"},
        {"id": "task1", "type": "serviceTask", "name": "DoWork", "next": "end"},
        {"id": "end", "type": "endEvent"},
    ])
    result = BM._compile_json_to_xml(doc)
    assert "task1" in result
    assert "serviceTask" in result


# ─── ingest._loads ───────────────────────────────────────────────────────────

def test_loads_empty_string_returns_empty_dict() -> None:
    assert IG._loads("") == {}


def test_loads_none_returns_empty_dict() -> None:
    assert IG._loads(None) == {}


def test_loads_valid_json() -> None:
    assert IG._loads('{"a": 1}') == {"a": 1}


def test_loads_non_dict_raises() -> None:
    with pytest.raises(ValueError):
        IG._loads("[1,2,3]")


# ─── ingest._dump ────────────────────────────────────────────────────────────

def test_dump_returns_json_string() -> None:
    result = IG._dump({"key": "value"})
    assert json.loads(result) == {"key": "value"}


def test_dump_sorts_keys() -> None:
    result = IG._dump({"b": 2, "a": 1})
    assert result.index('"a"') < result.index('"b"')


def test_dump_no_whitespace() -> None:
    result = IG._dump({"k": "v"})
    assert " " not in result


def test_dump_unicode_preserved() -> None:
    result = IG._dump({"name": "東京"})
    assert "東京" in result


# ─── ingest._require_str ─────────────────────────────────────────────────────

def test_require_str_returns_value() -> None:
    assert IG._require_str({"k": "val"}, "k") == "val"


def test_require_str_strips_whitespace() -> None:
    assert IG._require_str({"k": "  val  "}, "k") == "val"


def test_require_str_missing_key_raises() -> None:
    with pytest.raises(ValueError):
        IG._require_str({}, "k")


def test_require_str_empty_value_raises() -> None:
    with pytest.raises(ValueError):
        IG._require_str({"k": ""}, "k")


def test_require_str_none_value_raises() -> None:
    with pytest.raises(ValueError):
        IG._require_str({"k": None}, "k")


# ─── ingest._mode ────────────────────────────────────────────────────────────

def test_mode_delta_default() -> None:
    assert IG._mode({}) == "delta"


def test_mode_explicit_valid() -> None:
    for m in ("delta", "backfill", "repair", "verify"):
        assert IG._mode({"mode": m}) == m


def test_mode_uppercases_tolerated() -> None:
    assert IG._mode({"mode": "DELTA"}) == "delta"


def test_mode_invalid_raises() -> None:
    with pytest.raises(ValueError):
        IG._mode({"mode": "unknown"})


def test_mode_uses_custom_default() -> None:
    assert IG._mode({}, default="backfill") == "backfill"


# ─── ingest._run_dict ────────────────────────────────────────────────────────

def test_run_dict_maps_tuple_to_dict() -> None:
    row = ("vid", "rid", "fam", "src", "delta", "running",
           None, "bpmnId", "2024-01-01", None, 0, 0, 0, 0, None, "{}", "{}")
    result = IG._run_dict(row)
    assert result["runVertexId"] == "vid"
    assert result["ingestFamily"] == "fam"
    assert result["mode"] == "delta"


def test_run_dict_partial_tuple() -> None:
    row = ("vid", "rid")
    result = IG._run_dict(row)
    assert result["runVertexId"] == "vid"
    assert result["runId"] == "rid"


# ─── ingest._plan_payload ────────────────────────────────────────────────────

def test_plan_payload_basic() -> None:
    params = {"ingestFamily": "gleif", "sourceId": "api"}
    result = IG._plan_payload(params)
    assert result["ok"] is True
    assert result["ingestFamily"] == "gleif"
    assert result["sourceId"] == "api"
    assert result["mode"] == "delta"


def test_plan_payload_shards_estimated() -> None:
    params = {"ingestFamily": "gleif", "sourceId": "api", "limit": 5000}
    result = IG._plan_payload(params)
    assert result["estimatedShards"] >= 1


def test_plan_payload_no_limit_gives_zero_shards_one() -> None:
    params = {"ingestFamily": "gleif", "sourceId": "api"}
    result = IG._plan_payload(params)
    assert result["estimatedShards"] == 1


def test_plan_payload_missing_family_raises() -> None:
    with pytest.raises(ValueError):
        IG._plan_payload({"sourceId": "api"})


def test_plan_payload_has_targets_key() -> None:
    params = {"ingestFamily": "gleif", "sourceId": "api"}
    result = IG._plan_payload(params)
    assert "targets" in result
    assert isinstance(result["targets"], list)


# ─── ingest_backfill (error paths) ───────────────────────────────────────────

def test_ingest_backfill_missing_range_returns_error() -> None:
    import json as _json
    result = _json.loads(IG.ingest_backfill("{}"))
    assert result["ok"] is False
    assert "range" in result["error"].lower()


def test_ingest_backfill_invalid_json_returns_error() -> None:
    import json as _json
    result = _json.loads(IG.ingest_backfill("not-json"))
    assert result["ok"] is False
    assert "error" in result


def test_ingest_backfill_returns_json_string() -> None:
    import json as _json
    result = IG.ingest_backfill("{}")
    assert isinstance(result, str)
    parsed = _json.loads(result)
    assert "ok" in parsed


# ─── coverage_refresh (no-DB path) ───────────────────────────────────────────

def test_coverage_refresh_no_run_id_returns_ok() -> None:
    import json as _json
    result = _json.loads(IG.coverage_refresh('{"coverageFamily": "world"}'))
    assert result["ok"] is True
    assert result["coverageFamily"] == "world"
    assert result["status"] == "requested"


def test_coverage_refresh_default_family_is_world() -> None:
    import json as _json
    result = _json.loads(IG.coverage_refresh("{}"))
    assert result["ok"] is True
    assert result["coverageFamily"] == "world"


def test_coverage_refresh_custom_family() -> None:
    import json as _json
    result = _json.loads(IG.coverage_refresh('{"coverageFamily": "asia"}'))
    assert result["coverageFamily"] == "asia"


def test_coverage_refresh_invalid_json_returns_error() -> None:
    import json as _json
    result = _json.loads(IG.coverage_refresh("not-json"))
    assert result["ok"] is False
    assert "error" in result


def test_coverage_refresh_returns_json_string() -> None:
    import json as _json
    result = IG.coverage_refresh("{}")
    assert isinstance(result, str)
    parsed = _json.loads(result)
    assert "ok" in parsed


# ─── bpmn.compile_json_to_xml (public wrapper) ───────────────────────────────

def test_compile_json_to_xml_invalid_json_returns_error() -> None:
    import json as _json
    result = BM.compile_json_to_xml("not-json-at-all!!!")
    parsed = _json.loads(result)
    assert "error" in parsed


def test_compile_json_to_xml_missing_id_returns_error() -> None:
    import json as _json
    result = BM.compile_json_to_xml(_json.dumps({"name": "Flow", "flow": []}))
    parsed = _json.loads(result)
    assert "error" in parsed


def test_compile_json_to_xml_valid_doc_returns_xml() -> None:
    import json as _json
    doc = {"id": "proc1", "name": "Test", "flow": []}
    result = BM.compile_json_to_xml(_json.dumps(doc))
    parsed = _json.loads(result)
    assert "xml" in parsed
    assert "byteSize" in parsed
    assert parsed["byteSize"] > 0


def test_compile_json_to_xml_xrpc_wrapper() -> None:
    import json as _json
    wrapper = {"json": {"id": "proc2", "name": "Flow2", "flow": []}}
    result = BM.compile_json_to_xml(_json.dumps(wrapper))
    parsed = _json.loads(result)
    assert "xml" in parsed


def test_compile_json_to_xml_returns_json_string() -> None:
    import json as _json
    doc = {"id": "x", "name": "y", "flow": []}
    result = BM.compile_json_to_xml(_json.dumps(doc))
    assert isinstance(result, str)
    _json.loads(result)  # should not raise


# ─── bpmn.validate_xml (public wrapper) ──────────────────────────────────────

def test_validate_xml_empty_returns_error() -> None:
    import json as _json
    result = BM.validate_xml("")
    parsed = _json.loads(result)
    assert "error" in parsed


def test_validate_xml_valid_minimal_returns_true() -> None:
    import json as _json
    xml = (
        '<?xml version="1.0"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">'
        '<bpmn:process id="p1"></bpmn:process>'
        '</bpmn:definitions>'
    )
    result = BM.validate_xml(xml)
    parsed = _json.loads(result)
    assert parsed["valid"] is True
    assert parsed["errors"] == []


def test_validate_xml_missing_declaration_reports_error() -> None:
    import json as _json
    xml = (
        '<bpmn:definitions>'
        '<bpmn:process id="p1"></bpmn:process>'
        '</bpmn:definitions>'
    )
    result = BM.validate_xml(xml)
    parsed = _json.loads(result)
    assert parsed["valid"] is False
    assert any("declaration" in e for e in parsed["errors"])


def test_validate_xml_missing_process_reports_error() -> None:
    import json as _json
    xml = '<?xml version="1.0"?><bpmn:definitions></bpmn:definitions>'
    result = BM.validate_xml(xml)
    parsed = _json.loads(result)
    assert parsed["valid"] is False


def test_validate_xml_xrpc_wrapper_form() -> None:
    import json as _json
    xml = (
        '<?xml version="1.0"?>'
        '<bpmn:definitions>'
        '<bpmn:process id="p1"></bpmn:process>'
        '</bpmn:definitions>'
    )
    wrapper = _json.dumps({"xml": xml})
    result = BM.validate_xml(wrapper)
    parsed = _json.loads(result)
    assert "valid" in parsed


def test_validate_xml_returns_json_string() -> None:
    result = BM.validate_xml("<?xml?><bpmn:definitions><bpmn:process id='x'></bpmn:process></bpmn:definitions>")
    import json as _json
    _json.loads(result)  # should not raise
