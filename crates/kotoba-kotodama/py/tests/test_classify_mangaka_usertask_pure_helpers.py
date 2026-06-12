"""Tests for pure helpers in handlers/classify_t3.py:
_err, _skip, _build_user_prompt.

(mangaka_storyboard and user_task_sink are covered by test_more_handler_pure_functions.py.)
"""

from __future__ import annotations

import json
import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_classify_t3"
if _MOD_NAME in sys.modules:
    CT = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "classify" in k.lower() or "phishing" in k.lower() or "yabai" in k.lower()]:
            del _reg._HANDLERS[_k]
    except Exception:
        pass

    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    CT = _load_mod(_MOD_NAME, "kotodama/handlers/classify_t3.py")


# ─── _err ────────────────────────────────────────────────────────────────────

def test_err_returns_json_string() -> None:
    result = CT._err("something went wrong")
    obj = json.loads(result)
    assert obj["error"] == "something went wrong"


def test_err_includes_extra_kwargs() -> None:
    result = CT._err("oops", code=42)
    obj = json.loads(result)
    assert obj["code"] == 42
    assert obj["error"] == "oops"


def test_err_empty_message() -> None:
    obj = json.loads(CT._err(""))
    assert "error" in obj


def test_err_returns_string() -> None:
    assert isinstance(CT._err("x"), str)


# ─── _skip ───────────────────────────────────────────────────────────────────

def test_skip_returns_json_string() -> None:
    result = CT._skip("not-gray-zone")
    obj = json.loads(result)
    assert obj["skipped"] is True
    assert obj["reason"] == "not-gray-zone"


def test_skip_includes_extra_kwargs() -> None:
    result = CT._skip("low-score", t1Score=20)
    obj = json.loads(result)
    assert obj["t1Score"] == 20


def test_skip_always_has_skipped_true() -> None:
    obj = json.loads(CT._skip("any reason"))
    assert obj["skipped"] is True


def test_skip_returns_string() -> None:
    assert isinstance(CT._skip("x"), str)


# ─── _build_user_prompt ──────────────────────────────────────────────────────

def test_build_user_prompt_contains_t1_score() -> None:
    fields = {"t1Score": 72, "fromAddr": "x@y.com", "subject": "Win prize"}
    result = CT._build_user_prompt(fields)
    assert "72" in result


def test_build_user_prompt_contains_from_addr() -> None:
    fields = {"t1Score": 72, "fromAddr": "attacker@evil.com"}
    result = CT._build_user_prompt(fields)
    assert "attacker@evil.com" in result


def test_build_user_prompt_contains_subject() -> None:
    fields = {"t1Score": 72, "subject": "Click here NOW"}
    result = CT._build_user_prompt(fields)
    assert "Click here NOW" in result


def test_build_user_prompt_body_urls_included() -> None:
    fields = {"t1Score": 72, "bodyUrls": ["http://evil.com/hack"]}
    result = CT._build_user_prompt(fields)
    assert "http://evil.com/hack" in result


def test_build_user_prompt_limits_body_urls_to_5() -> None:
    urls = [f"http://site{i}.com" for i in range(10)]
    fields = {"t1Score": 72, "bodyUrls": urls}
    result = CT._build_user_prompt(fields)
    shown = sum(1 for u in urls[:5] if u in result)
    assert shown <= 5


def test_build_user_prompt_empty_body_urls_not_shown() -> None:
    fields = {"t1Score": 72, "bodyUrls": []}
    result = CT._build_user_prompt(fields)
    assert "Body URLs" not in result


def test_build_user_prompt_returns_string() -> None:
    assert isinstance(CT._build_user_prompt({}), str)


def test_build_user_prompt_spf_dkim_dmarc_shown() -> None:
    fields = {"t1Score": 72, "spf": "pass", "dkim": "fail", "dmarc": "none"}
    result = CT._build_user_prompt(fields)
    assert "pass" in result
    assert "fail" in result


def test_build_user_prompt_empty_fields_ok() -> None:
    result = CT._build_user_prompt({})
    assert isinstance(result, str)
    assert len(result) > 0
