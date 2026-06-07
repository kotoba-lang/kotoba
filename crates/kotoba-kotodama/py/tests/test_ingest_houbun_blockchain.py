"""Tests for pure helper functions in ingest/houbun.py and ingest/blockchain.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import houbun as HB
from kotodama.ingest import blockchain as BC


# ─── houbun: _clean ──────────────────────────────────────────────────────────

def test_hb_clean_strips_whitespace() -> None:
    assert HB._clean("  hello  ") == "hello"


def test_hb_clean_collapses_spaces() -> None:
    result = HB._clean("a   b   c")
    assert "   " not in result


def test_hb_clean_none_returns_empty() -> None:
    assert HB._clean(None) == ""


def test_hb_clean_integer_converts() -> None:
    assert HB._clean(42) == "42"


# ─── houbun: _hash ───────────────────────────────────────────────────────────

def test_hb_hash_default_size() -> None:
    result = HB._hash("a", "b")
    assert len(result) == 12  # blake2b size=6 → 12 hex chars


def test_hb_hash_custom_size() -> None:
    result = HB._hash("x", size=8)
    assert len(result) == 16  # size=8 → 16 hex chars


def test_hb_hash_deterministic() -> None:
    a = HB._hash("part1", "part2")
    b = HB._hash("part1", "part2")
    assert a == b


def test_hb_hash_varies_with_input() -> None:
    a = HB._hash("a", "b")
    b = HB._hash("a", "c")
    assert a != b


# ─── houbun: _flatten ────────────────────────────────────────────────────────

def test_hb_flatten_string_passthrough() -> None:
    assert HB._flatten("hello") == "hello"


def test_hb_flatten_none_returns_empty() -> None:
    assert HB._flatten(None) == ""


def test_hb_flatten_list_joins() -> None:
    result = HB._flatten(["hello", "world"])
    assert "hello" in result
    assert "world" in result


def test_hb_flatten_dict_with_text_key() -> None:
    result = HB._flatten({"#text": "content"})
    assert result == "content"


def test_hb_flatten_dict_with_dollar_key() -> None:
    result = HB._flatten({"$": "dollar-text"})
    assert result == "dollar-text"


def test_hb_flatten_nested_children() -> None:
    node = {"children": ["part-a", "part-b"]}
    result = HB._flatten(node)
    assert "part-a" in result
    assert "part-b" in result


def test_hb_flatten_integer() -> None:
    assert HB._flatten(42) == "42"


def test_hb_flatten_skips_attr_keys() -> None:
    node = {"attr": "skip", "content": "keep"}
    result = HB._flatten(node)
    assert "skip" not in result
    assert "keep" in result


# ─── houbun: _children_with_tag ──────────────────────────────────────────────

def test_hb_children_with_tag_finds_matches() -> None:
    node = {"children": [{"tag": "Article", "text": "a"}, {"tag": "Preamble", "text": "b"}]}
    result = HB._children_with_tag(node, "Article")
    assert len(result) == 1
    assert result[0]["text"] == "a"


def test_hb_children_with_tag_no_match() -> None:
    node = {"children": [{"tag": "Preamble"}]}
    assert HB._children_with_tag(node, "Article") == []


def test_hb_children_with_tag_empty_node() -> None:
    assert HB._children_with_tag({}, "Article") == []


# ─── houbun: _first_child ────────────────────────────────────────────────────

def test_hb_first_child_returns_first_match() -> None:
    node = {"children": [{"tag": "Article", "id": 1}, {"tag": "Article", "id": 2}]}
    result = HB._first_child(node, "Article")
    assert result is not None
    assert result["id"] == 1


def test_hb_first_child_no_match_returns_none() -> None:
    node = {"children": [{"tag": "Preamble"}]}
    assert HB._first_child(node, "Article") is None


# ─── houbun: _find_first_tag ─────────────────────────────────────────────────

def test_hb_find_first_tag_nested() -> None:
    node = {"tag": "Root", "children": [{"tag": "Article", "val": "found"}]}
    result = HB._find_first_tag(node, "Article")
    assert result is not None
    assert result["val"] == "found"


def test_hb_find_first_tag_in_list() -> None:
    nodes = [{"tag": "Preamble"}, {"tag": "Article", "val": "yes"}]
    result = HB._find_first_tag(nodes, "Article")
    assert result is not None
    assert result["val"] == "yes"


def test_hb_find_first_tag_not_found() -> None:
    assert HB._find_first_tag({"tag": "Other"}, "Article") is None


# ─── blockchain: _json_dumps ─────────────────────────────────────────────────

def test_bc_json_dumps_sorted_keys() -> None:
    result = BC._json_dumps({"b": 2, "a": 1})
    assert result.index('"a"') < result.index('"b"')


def test_bc_json_dumps_no_spaces() -> None:
    result = BC._json_dumps({"key": "val"})
    assert " " not in result


def test_bc_json_dumps_non_ascii() -> None:
    result = BC._json_dumps({"text": "日本語"})
    assert "日本語" in result


# ─── blockchain: _sha256_text ────────────────────────────────────────────────

def test_bc_sha256_text_length() -> None:
    result = BC._sha256_text("hello")
    assert len(result) == 64


def test_bc_sha256_text_deterministic() -> None:
    a = BC._sha256_text("hello")
    b = BC._sha256_text("hello")
    assert a == b


def test_bc_sha256_text_varies() -> None:
    a = BC._sha256_text("hello")
    b = BC._sha256_text("world")
    assert a != b


# ─── blockchain: _hex_int ────────────────────────────────────────────────────

def test_bc_hex_int_none_returns_zero() -> None:
    assert BC._hex_int(None) == 0


def test_bc_hex_int_integer_passthrough() -> None:
    assert BC._hex_int(42) == 42


def test_bc_hex_int_hex_string() -> None:
    assert BC._hex_int("0x1a") == 26


def test_bc_hex_int_hex_string_no_prefix() -> None:
    assert BC._hex_int("1f") == 31


# ─── blockchain._write_head_blocks ───────────────────────────────────────────

def test_bc_write_head_blocks_default_true(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", raising=False)
    assert BC._write_head_blocks() is True


def test_bc_write_head_blocks_env_one_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "1")
    assert BC._write_head_blocks() is True


def test_bc_write_head_blocks_env_true_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "true")
    assert BC._write_head_blocks() is True


def test_bc_write_head_blocks_env_zero_false(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "0")
    assert BC._write_head_blocks() is False


def test_bc_write_head_blocks_env_false_false(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "false")
    assert BC._write_head_blocks() is False


def test_bc_write_head_blocks_returns_bool(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", raising=False)
    result = BC._write_head_blocks()
    assert isinstance(result, bool)
