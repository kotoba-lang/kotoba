"""Tests for pure helpers in handlers/kouza.py:
_dump, _loads, _now_iso, _hash, _record_did, _core_sync_endpoint, _int_param."""

from __future__ import annotations

import json
import os
import re
import sys
import types
import importlib.util
from pathlib import Path
from unittest.mock import patch

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_kouza"
if _MOD_NAME in sys.modules:
    KZ = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "kouza" in k.lower()]:
            del _reg._HANDLERS[_k]
    except Exception:
        pass

    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    KZ = _load_mod(_MOD_NAME, "kotodama/handlers/kouza.py")


def test_dump_returns_string():
    assert isinstance(KZ._dump({"a": 1}), str)

def test_dump_is_valid_json():
    result = KZ._dump({"x": [1, 2, 3]})
    assert json.loads(result) == {"x": [1, 2, 3]}

def test_dump_sorts_keys():
    result = KZ._dump({"z": 1, "a": 2})
    assert result.index('"a"') < result.index('"z"')

def test_dump_no_whitespace():
    result = KZ._dump({"key": "value"})
    assert " " not in result

def test_dump_empty_dict():
    assert KZ._dump({}) == "{}"

def test_loads_parses_json_object():
    assert KZ._loads('{"k": "v"}') == {"k": "v"}

def test_loads_empty_string_returns_empty_dict():
    assert KZ._loads("") == {}

def test_loads_invalid_json_raises():
    import pytest
    with pytest.raises(Exception):
        KZ._loads("not-json")

def test_loads_non_object_raises_value_error():
    import pytest
    with pytest.raises(ValueError, match="object"):
        KZ._loads("[1, 2, 3]")

def test_loads_nested_values_preserved():
    result = KZ._loads('{"a": {"b": [1, 2]}}')
    assert result["a"]["b"] == [1, 2]

def test_now_iso_format():
    result = KZ._now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)

def test_now_iso_ends_with_z():
    assert KZ._now_iso().endswith("Z")

def test_now_iso_no_microseconds():
    assert "." not in KZ._now_iso()

def test_hash_returns_24_hex_chars():
    result = KZ._hash({"key": "value"})
    assert len(result) == 24
    assert all(c in "0123456789abcdef" for c in result)

def test_hash_deterministic():
    assert KZ._hash({"a": 1}) == KZ._hash({"a": 1})

def test_hash_sorts_keys():
    assert KZ._hash({"z": 1, "a": 2}) == KZ._hash({"a": 2, "z": 1})

def test_hash_different_values_differ():
    assert KZ._hash({"a": 1}) != KZ._hash({"a": 2})

def test_hash_works_on_string():
    assert len(KZ._hash("hello")) == 24

def test_hash_works_on_list():
    assert len(KZ._hash([1, 2, 3])) == 24

def test_record_did_format():
    result = KZ._record_did("did:web:kouza.etzhayyim.com", "com.etzhayyim.apps.kouza.connection", "rkey123")
    assert result == "at://did:web:kouza.etzhayyim.com/com.etzhayyim.apps.kouza.connection/rkey123"

def test_record_did_starts_with_at():
    assert KZ._record_did("owner", "collection", "rkey").startswith("at://")

def test_record_did_contains_all_parts():
    result = KZ._record_did("did:web:x", "com.etzhayyim.apps.x.y", "rk001")
    assert "did:web:x" in result
    assert "com.etzhayyim.apps.x.y" in result
    assert "rk001" in result

def test_core_sync_endpoint_empty_when_no_env():
    env = {k: v for k, v in os.environ.items() if k != "KOUZA_CORE_URL"}
    with patch.dict(os.environ, env, clear=True):
        assert KZ._core_sync_endpoint() == ""

def test_core_sync_endpoint_builds_url_from_env():
    with patch.dict(os.environ, {"KOUZA_CORE_URL": "https://kouza.example.com"}):
        result = KZ._core_sync_endpoint()
        assert result.startswith("https://kouza.example.com")
        assert KZ.NS in result

def test_core_sync_endpoint_strips_trailing_slash():
    with patch.dict(os.environ, {"KOUZA_CORE_URL": "https://kouza.example.com/"}):
        result = KZ._core_sync_endpoint()
        assert result.count("//") == 1  # only the protocol ://

def test_int_param_returns_default_when_missing():
    assert KZ._int_param({}, "limit", 10, 1, 100) == 10

def test_int_param_returns_provided_value():
    assert KZ._int_param({"limit": 25}, "limit", 10, 1, 100) == 25

def test_int_param_converts_string_to_int():
    assert KZ._int_param({"limit": "50"}, "limit", 10, 1, 100) == 50

def test_int_param_raises_for_non_int_string():
    import pytest
    with pytest.raises(ValueError, match="integer"):
        KZ._int_param({"limit": "abc"}, "limit", 10, 1, 100)

def test_int_param_raises_below_minimum():
    import pytest
    with pytest.raises(ValueError, match="between"):
        KZ._int_param({"limit": 0}, "limit", 10, 1, 100)

def test_int_param_raises_above_maximum():
    import pytest
    with pytest.raises(ValueError, match="between"):
        KZ._int_param({"limit": 200}, "limit", 10, 1, 100)

def test_int_param_boundary_minimum_ok():
    assert KZ._int_param({"x": 1}, "x", 5, 1, 10) == 1

def test_int_param_boundary_maximum_ok():
    assert KZ._int_param({"x": 10}, "x", 5, 1, 10) == 10
