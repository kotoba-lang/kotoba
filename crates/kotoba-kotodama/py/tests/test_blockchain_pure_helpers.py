"""Tests for pure helper functions in ingest/blockchain.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import blockchain as BC


# ─── _json_dumps ─────────────────────────────────────────────────────────────

def test_json_dumps_basic_dict() -> None:
    result = BC._json_dumps({"b": 2, "a": 1})
    assert result == '{"a":1,"b":2}'  # sort_keys=True


def test_json_dumps_sorted_keys() -> None:
    result = BC._json_dumps({"z": "last", "a": "first"})
    parsed = json.loads(result)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_json_dumps_returns_string() -> None:
    assert isinstance(BC._json_dumps({"x": 1}), str)


def test_json_dumps_no_spaces() -> None:
    result = BC._json_dumps({"k": "v"})
    assert " " not in result


def test_json_dumps_none() -> None:
    result = BC._json_dumps(None)
    assert result == "null"


def test_json_dumps_list() -> None:
    result = BC._json_dumps([1, 2, 3])
    assert result == "[1,2,3]"


def test_json_dumps_nested() -> None:
    result = BC._json_dumps({"a": {"b": 1}})
    assert "a" in result
    assert "b" in result


def test_json_dumps_deterministic() -> None:
    d = {"x": 1, "y": 2, "z": 3}
    assert BC._json_dumps(d) == BC._json_dumps(d)


# ─── _sha256_text ────────────────────────────────────────────────────────────

def test_sha256_text_returns_64_chars() -> None:
    result = BC._sha256_text("hello")
    assert len(result) == 64


def test_sha256_text_returns_hex() -> None:
    result = BC._sha256_text("hello")
    assert all(c in "0123456789abcdef" for c in result)


def test_sha256_text_deterministic() -> None:
    assert BC._sha256_text("world") == BC._sha256_text("world")


def test_sha256_text_differs_on_different_input() -> None:
    assert BC._sha256_text("a") != BC._sha256_text("b")


def test_sha256_text_empty_string() -> None:
    result = BC._sha256_text("")
    assert len(result) == 64


def test_sha256_text_known_value() -> None:
    # sha256("hello") = 2cf24dba...
    result = BC._sha256_text("hello")
    assert result.startswith("2cf24dba")


# ─── _hex_int ────────────────────────────────────────────────────────────────

def test_hex_int_none_returns_zero() -> None:
    assert BC._hex_int(None) == 0


def test_hex_int_integer_passthrough() -> None:
    assert BC._hex_int(42) == 42


def test_hex_int_hex_string() -> None:
    assert BC._hex_int("0x1a") == 26


def test_hex_int_hex_without_prefix() -> None:
    assert BC._hex_int("1a") == 26


def test_hex_int_zero() -> None:
    assert BC._hex_int(0) == 0


def test_hex_int_large_hex() -> None:
    assert BC._hex_int("0xff") == 255


def test_hex_int_returns_int_type() -> None:
    assert isinstance(BC._hex_int("0x10"), int)


# ─── _write_head_blocks ───────────────────────────────────────────────────────

def test_write_head_blocks_default_true(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", raising=False)
    assert BC._write_head_blocks() is True


def test_write_head_blocks_set_to_0_false(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "0")
    assert BC._write_head_blocks() is False


def test_write_head_blocks_set_to_false_string(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "false")
    assert BC._write_head_blocks() is False


def test_write_head_blocks_set_to_1_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "1")
    assert BC._write_head_blocks() is True


def test_write_head_blocks_set_to_true_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "true")
    assert BC._write_head_blocks() is True


def test_write_head_blocks_set_to_yes_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "yes")
    assert BC._write_head_blocks() is True


def test_write_head_blocks_set_to_on_true(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "on")
    assert BC._write_head_blocks() is True
