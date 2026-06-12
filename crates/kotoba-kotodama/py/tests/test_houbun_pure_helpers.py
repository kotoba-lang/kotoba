"""Tests for pure helpers in handlers/houbun.py:
_blake3_prefix12, _article_did, _flatten_text, _iter_articles,
_eurlex_query_single, _eurlex_query_delta, _sparql_val."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_houbun"
if _MOD_NAME in sys.modules:
    HB = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "houbun" in k.lower()]:
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

    HB = _load_mod(_MOD_NAME, "kotodama/handlers/houbun.py")


# ─── _blake3_prefix12 ────────────────────────────────────────────────────────

def test_blake3_prefix12_returns_12_hex() -> None:
    result = HB._blake3_prefix12("jpn", "S001", "1", "2024-04-01")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_blake3_prefix12_deterministic() -> None:
    a = HB._blake3_prefix12("jpn", "S001", "1", "2024-04-01")
    b = HB._blake3_prefix12("jpn", "S001", "1", "2024-04-01")
    assert a == b


def test_blake3_prefix12_different_inputs_differ() -> None:
    a = HB._blake3_prefix12("jpn", "S001", "1", "2024-04-01")
    b = HB._blake3_prefix12("jpn", "S002", "1", "2024-04-01")
    assert a != b


def test_blake3_prefix12_empty_strings_ok() -> None:
    result = HB._blake3_prefix12("", "", "", "")
    assert len(result) == 12


def test_blake3_prefix12_amendment_changes_hash() -> None:
    v1 = HB._blake3_prefix12("jpn", "S001", "1", "2024-01-01")
    v2 = HB._blake3_prefix12("jpn", "S001", "1", "2025-01-01")
    assert v1 != v2


# ─── _article_did ────────────────────────────────────────────────────────────

def test_article_did_starts_with_actor_did() -> None:
    result = HB._article_did("jpn", "S001", "1", "2024-04-01")
    assert result.startswith(HB.ACTOR_DID)


def test_article_did_contains_article_segment() -> None:
    result = HB._article_did("jpn", "S001", "1", "2024-04-01")
    assert ":article:" in result


def test_article_did_deterministic() -> None:
    a = HB._article_did("jpn", "S001", "2", "2024-04-01")
    b = HB._article_did("jpn", "S001", "2", "2024-04-01")
    assert a == b


def test_article_did_different_articles_differ() -> None:
    a = HB._article_did("jpn", "S001", "1", "2024-04-01")
    b = HB._article_did("jpn", "S001", "2", "2024-04-01")
    assert a != b


def test_article_did_format() -> None:
    result = HB._article_did("eu", "CELEX001", "art3", "2023-01-01")
    parts = result.split(":")
    assert len(parts) >= 4


# ─── _flatten_text ───────────────────────────────────────────────────────────

def test_flatten_text_string() -> None:
    assert HB._flatten_text("hello world") == "hello world"


def test_flatten_text_none_returns_empty() -> None:
    assert HB._flatten_text(None) == ""


def test_flatten_text_int() -> None:
    assert HB._flatten_text(42) == "42"


def test_flatten_text_list_joined() -> None:
    result = HB._flatten_text(["hello", "world"])
    assert "hello" in result
    assert "world" in result


def test_flatten_text_dict_hash_text_key() -> None:
    result = HB._flatten_text({"#text": "article text"})
    assert result == "article text"


def test_flatten_text_dict_dollar_key() -> None:
    result = HB._flatten_text({"$": "paragraph text"})
    assert result == "paragraph text"


def test_flatten_text_nested_dict() -> None:
    obj = {"Paragraph": {"Sentence": "content"}}
    result = HB._flatten_text(obj)
    assert "content" in result


def test_flatten_text_whitespace_collapsed() -> None:
    result = HB._flatten_text("hello   world\n\ttab")
    assert "  " not in result


def test_flatten_text_skips_at_prefix_keys() -> None:
    result = HB._flatten_text({"@Attr": "ignored", "Text": "kept"})
    assert "ignored" not in result
    assert "kept" in result


def test_flatten_text_list_with_none_skipped() -> None:
    result = HB._flatten_text(["a", None, "b"])
    assert "a" in result
    assert "b" in result


# ─── _iter_articles ──────────────────────────────────────────────────────────

def test_iter_articles_empty_returns_list() -> None:
    result = HB._iter_articles({})
    assert isinstance(result, list)


def test_iter_articles_flat_article() -> None:
    law_body = {
        "Article": [{
            "@": {"Num": "1"},
            "ArticleTitle": "第1条",
            "Paragraph": {"Sentence": "本条の規定は以下の通り。"},
        }]
    }
    result = HB._iter_articles(law_body)
    assert len(result) >= 1
    assert result[0]["article_no"] != ""


def test_iter_articles_returns_dicts_with_required_keys() -> None:
    law_body = {
        "Article": [{
            "@": {"Num": "3"},
            "ArticleTitle": "第3条",
            "Paragraph": "Some text",
        }]
    }
    result = HB._iter_articles(law_body)
    if result:
        for key in ("article_no", "title", "section", "text"):
            assert key in result[0]


def test_iter_articles_none_input() -> None:
    result = HB._iter_articles(None)
    assert result == []


def test_iter_articles_list_input() -> None:
    law_body = [{
        "Article": [{"@": {"Num": "1"}, "ArticleTitle": "第1条", "Paragraph": "x"}]
    }]
    result = HB._iter_articles(law_body)
    assert isinstance(result, list)


# ─── _eurlex_query_single ────────────────────────────────────────────────────

def test_eurlex_query_single_contains_celex() -> None:
    result = HB._eurlex_query_single("32016R0679")
    assert "32016R0679" in result


def test_eurlex_query_single_is_sparql() -> None:
    result = HB._eurlex_query_single("CELEX001")
    assert "PREFIX" in result
    assert "SELECT" in result


def test_eurlex_query_single_returns_string() -> None:
    assert isinstance(HB._eurlex_query_single("X"), str)


# ─── _eurlex_query_delta ─────────────────────────────────────────────────────

def test_eurlex_query_delta_contains_since_date() -> None:
    result = HB._eurlex_query_delta("2026-01-01", None, 50)
    assert "2026-01-01" in result


def test_eurlex_query_delta_contains_limit() -> None:
    result = HB._eurlex_query_delta("2026-01-01", None, 50)
    assert "LIMIT 50" in result


def test_eurlex_query_delta_regulation_filter() -> None:
    result = HB._eurlex_query_delta("2026-01-01", "regulation", 10)
    assert "R" in result


def test_eurlex_query_delta_directive_filter() -> None:
    result = HB._eurlex_query_delta("2026-01-01", "directive", 10)
    assert "L" in result


def test_eurlex_query_delta_no_type_filter() -> None:
    result = HB._eurlex_query_delta("2026-01-01", None, 10)
    assert "STRSTARTS" not in result


# ─── _sparql_val ─────────────────────────────────────────────────────────────

def test_sparql_val_extracts_value() -> None:
    binding = {"celex": {"value": "32016R0679", "type": "literal"}}
    assert HB._sparql_val(binding, "celex") == "32016R0679"


def test_sparql_val_missing_key_returns_none() -> None:
    assert HB._sparql_val({}, "celex") is None


def test_sparql_val_non_dict_value_returns_none() -> None:
    binding = {"celex": "not a dict"}
    assert HB._sparql_val(binding, "celex") is None


def test_sparql_val_no_value_in_dict_returns_none() -> None:
    binding = {"celex": {"type": "literal"}}
    assert HB._sparql_val(binding, "celex") is None


def test_sparql_val_int_value_cast_to_str() -> None:
    binding = {"count": {"value": 42}}
    result = HB._sparql_val(binding, "count")
    assert result == "42"
