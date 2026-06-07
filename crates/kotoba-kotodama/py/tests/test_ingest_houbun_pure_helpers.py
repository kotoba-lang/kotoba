"""Tests for pure helpers in ingest/houbun.py:
_clean, _hash, _flatten, _children_with_tag, _first_child, _find_first_tag,
task_houbun_write_graph, task_houbun_fetch_egov_jpn, task_houbun_plan_egov_jpn."""

from __future__ import annotations

import asyncio

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import houbun as IH  # noqa: E402


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_clean_collapses_whitespace() -> None:
    assert IH._clean("foo  bar") == "foo bar"


def test_clean_strips_leading_trailing() -> None:
    assert IH._clean("  hello  ") == "hello"


def test_clean_none_returns_empty() -> None:
    assert IH._clean(None) == ""


def test_clean_empty_string() -> None:
    assert IH._clean("") == ""


def test_clean_newlines_collapsed() -> None:
    result = IH._clean("a\n\nb")
    assert "\n" not in result
    assert "a" in result and "b" in result


def test_clean_tabs_collapsed() -> None:
    result = IH._clean("a\t\tb")
    assert "\t" not in result


def test_clean_plain_string_unchanged() -> None:
    assert IH._clean("simple") == "simple"


# ─── _hash ───────────────────────────────────────────────────────────────────

def test_hash_returns_12_hex() -> None:
    result = IH._hash("jpn", "S001", "1", "2024-01-01")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_deterministic() -> None:
    a = IH._hash("jpn", "S001", "1", "2024-01-01")
    b = IH._hash("jpn", "S001", "1", "2024-01-01")
    assert a == b


def test_hash_different_inputs_differ() -> None:
    a = IH._hash("jpn", "S001", "1")
    b = IH._hash("jpn", "S002", "1")
    assert a != b


def test_hash_empty_strings_ok() -> None:
    result = IH._hash("", "", "")
    assert len(result) == 12


def test_hash_single_arg() -> None:
    result = IH._hash("only")
    assert len(result) == 12


# ─── _flatten ────────────────────────────────────────────────────────────────

def test_flatten_string() -> None:
    assert IH._flatten("hello world") == "hello world"


def test_flatten_none_returns_empty() -> None:
    assert IH._flatten(None) == ""


def test_flatten_int() -> None:
    assert IH._flatten(42) == "42"


def test_flatten_float() -> None:
    result = IH._flatten(3.14)
    assert "3" in result


def test_flatten_list_joined() -> None:
    result = IH._flatten(["hello", "world"])
    assert "hello" in result
    assert "world" in result


def test_flatten_dict_hash_text_key() -> None:
    result = IH._flatten({"#text": "article text"})
    assert "article text" in result


def test_flatten_dict_dollar_key() -> None:
    result = IH._flatten({"$": "paragraph text"})
    assert "paragraph text" in result


def test_flatten_dict_children_key() -> None:
    result = IH._flatten({"children": [{"#text": "child"}]})
    assert "child" in result


def test_flatten_dict_skips_at_prefix_keys() -> None:
    result = IH._flatten({"@attr": "ignored", "#text": "kept"})
    assert "ignored" not in result
    assert "kept" in result


def test_flatten_dict_skips_underscore_prefix_keys() -> None:
    result = IH._flatten({"_meta": "ignored", "#text": "kept"})
    assert "ignored" not in result
    assert "kept" in result


def test_flatten_nested_dict() -> None:
    obj = {"Paragraph": {"Sentence": "content"}}
    result = IH._flatten(obj)
    assert "content" in result


def test_flatten_list_with_none_skipped() -> None:
    result = IH._flatten(["a", None, "b"])
    assert "a" in result
    assert "b" in result


def test_flatten_whitespace_collapsed() -> None:
    result = IH._flatten("hello   world")
    assert "  " not in result


# ─── _children_with_tag ──────────────────────────────────────────────────────

def test_children_with_tag_returns_matching() -> None:
    node = {"children": [{"tag": "Article"}, {"tag": "Paragraph"}, {"tag": "Article"}]}
    result = IH._children_with_tag(node, "Article")
    assert len(result) == 2


def test_children_with_tag_empty_when_none_match() -> None:
    node = {"children": [{"tag": "Paragraph"}]}
    result = IH._children_with_tag(node, "Article")
    assert result == []


def test_children_with_tag_no_children_key() -> None:
    result = IH._children_with_tag({}, "Article")
    assert result == []


def test_children_with_tag_none_node() -> None:
    import pytest
    with pytest.raises((AttributeError, TypeError)):
        IH._children_with_tag(None, "Article")


def test_children_with_tag_skips_non_dict_children() -> None:
    node = {"children": ["bad", {"tag": "Article"}]}
    result = IH._children_with_tag(node, "Article")
    assert len(result) == 1


def test_children_with_tag_preserves_order() -> None:
    node = {"children": [{"tag": "A", "n": 1}, {"tag": "B"}, {"tag": "A", "n": 2}]}
    result = IH._children_with_tag(node, "A")
    assert result[0]["n"] == 1
    assert result[1]["n"] == 2


# ─── _first_child ────────────────────────────────────────────────────────────

def test_first_child_returns_first_match() -> None:
    node = {"children": [{"tag": "A", "n": 1}, {"tag": "A", "n": 2}]}
    result = IH._first_child(node, "A")
    assert result is not None
    assert result["n"] == 1


def test_first_child_returns_none_when_missing() -> None:
    node = {"children": [{"tag": "B"}]}
    result = IH._first_child(node, "A")
    assert result is None


def test_first_child_empty_children() -> None:
    node = {"children": []}
    assert IH._first_child(node, "A") is None


def test_first_child_none_node() -> None:
    import pytest
    with pytest.raises((AttributeError, TypeError)):
        IH._first_child(None, "A")


# ─── _find_first_tag ─────────────────────────────────────────────────────────

def test_find_first_tag_direct_match() -> None:
    node = {"tag": "Article", "value": "found"}
    result = IH._find_first_tag(node, "Article")
    assert result is not None
    assert result["value"] == "found"


def test_find_first_tag_nested_match() -> None:
    node = {"tag": "LawBody", "children": [
        {"tag": "Section", "children": [
            {"tag": "Article", "value": "nested"}
        ]}
    ]}
    result = IH._find_first_tag(node, "Article")
    assert result is not None
    assert result["value"] == "nested"


def test_find_first_tag_returns_none_when_missing() -> None:
    node = {"tag": "LawBody", "children": [{"tag": "Section"}]}
    result = IH._find_first_tag(node, "Article")
    assert result is None


def test_find_first_tag_none_input() -> None:
    result = IH._find_first_tag(None, "Article")
    assert result is None


def test_find_first_tag_non_dict_input() -> None:
    result = IH._find_first_tag("string", "Article")
    assert result is None


def test_find_first_tag_returns_first_dfs_match() -> None:
    node = {"tag": "Root", "children": [
        {"tag": "Article", "n": 1},
        {"tag": "Article", "n": 2},
    ]}
    result = IH._find_first_tag(node, "Article")
    assert result["n"] == 1


# ─── _legacy_article_node ─────────────────────────────────────────────────────

def test_legacy_article_node_dict_returns_article_tag() -> None:
    result = IH._legacy_article_node({"ArticleTitle": "Title One"})
    assert result["tag"] == "Article"


def test_legacy_article_node_non_dict_wraps_in_sentence() -> None:
    result = IH._legacy_article_node("plain text")
    assert result["tag"] == "Article"
    assert result["children"][0]["tag"] == "Sentence"


def test_legacy_article_node_extracts_article_title() -> None:
    result = IH._legacy_article_node({"ArticleTitle": "The Title", "ArticleCaption": "Cap"})
    tags = [c["tag"] for c in result["children"]]
    assert "ArticleTitle" in tags
    assert "ArticleCaption" in tags


def test_legacy_article_node_preserves_at_attr() -> None:
    result = IH._legacy_article_node({"@": {"Num": "1"}, "ArticleTitle": "T"})
    assert result.get("attr") == {"Num": "1"}


def test_legacy_article_node_empty_dict_returns_article() -> None:
    result = IH._legacy_article_node({})
    assert result["tag"] == "Article"
    assert result["children"] == []


def test_legacy_article_node_returns_dict() -> None:
    result = IH._legacy_article_node({"x": "y"})
    assert isinstance(result, dict)


def test_legacy_article_node_skips_at_key_in_children() -> None:
    result = IH._legacy_article_node({"@": {"n": "1"}, "Content": "body"})
    tags = [c["tag"] for c in result["children"]]
    assert "@" not in tags
    assert "Content" in tags


# ─── task_houbun_fetch_egov_jpn early-return ─────────────────────────────────

def test_fetch_egov_jpn_no_law_id_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_fetch_egov_jpn(runId="run1"))
    assert result["ok"] is False
    assert "lawId" in result["error"]


def test_fetch_egov_jpn_missing_both_ids_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_fetch_egov_jpn(runId="run1", lawId="", shardKey=""))
    assert result["ok"] is False


def test_fetch_egov_jpn_error_returns_dict() -> None:
    result = asyncio.run(IH.task_houbun_fetch_egov_jpn(runId="run1"))
    assert isinstance(result, dict)


# ─── task_houbun_write_graph early-return paths ──────────────────────────────

def test_write_graph_unsupported_source_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_write_graph(sourceId="gleif"))
    assert result["ok"] is False
    assert "unsupported" in result["error"]


def test_write_graph_rw_not_healthy_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_write_graph(rwHealthy=False))
    assert result["ok"] is False
    assert "rwHealthy" in result["error"]


def test_write_graph_healthy_false_overrides_rw_healthy() -> None:
    result = asyncio.run(IH.task_houbun_write_graph(rwHealthy=True, healthy=False))
    assert result["ok"] is False


def test_write_graph_missing_payload_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_write_graph(rwHealthy=True, normalizedPayload=None))
    assert result["ok"] is False
    assert "normalizedPayload" in result["error"]


def test_write_graph_empty_payload_returns_error() -> None:
    result = asyncio.run(IH.task_houbun_write_graph(rwHealthy=True, normalizedPayload={}))
    assert result["ok"] is False


# ─── task_houbun_plan_egov_jpn with lawId ────────────────────────────────────

def test_plan_egov_jpn_with_law_id_returns_single_shard() -> None:
    result = asyncio.run(IH.task_houbun_plan_egov_jpn(lawId="123ABC"))
    assert result["ok"] is True
    assert result["plannedShards"] == 1
    assert result["lawId"] == "123ABC"


def test_plan_egov_jpn_with_law_id_shards_has_entry() -> None:
    result = asyncio.run(IH.task_houbun_plan_egov_jpn(lawId="L99"))
    assert len(result["shards"]) == 1
    assert result["shards"][0]["lawId"] == "L99"


def test_plan_egov_jpn_with_law_id_returns_dict() -> None:
    result = asyncio.run(IH.task_houbun_plan_egov_jpn(lawId="X1"))
    assert isinstance(result, dict)


def test_plan_egov_jpn_source_id_in_result() -> None:
    result = asyncio.run(IH.task_houbun_plan_egov_jpn(lawId="X1"))
    assert "sourceId" in result


def test_plan_egov_jpn_first_shard_has_shard_key() -> None:
    result = asyncio.run(IH.task_houbun_plan_egov_jpn(lawId="ABC123"))
    assert result["firstShard"]["shardKey"] == "ABC123"
