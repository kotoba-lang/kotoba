"""Tests for _children_with_tag, _first_child, _find_first_tag in ingest/houbun.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import houbun as H


# ─── _children_with_tag ──────────────────────────────────────────────────────

def test_children_with_tag_finds_matching() -> None:
    node = {
        "tag": "Law",
        "children": [
            {"tag": "Article", "text": "Art 1"},
            {"tag": "Article", "text": "Art 2"},
            {"tag": "Chapter", "text": "Ch 1"},
        ],
    }
    result = H._children_with_tag(node, "Article")
    assert len(result) == 2
    assert all(c["tag"] == "Article" for c in result)


def test_children_with_tag_no_match_returns_empty() -> None:
    node = {"children": [{"tag": "Chapter"}]}
    assert H._children_with_tag(node, "Article") == []


def test_children_with_tag_empty_children() -> None:
    node = {"tag": "Law", "children": []}
    assert H._children_with_tag(node, "Article") == []


def test_children_with_tag_no_children_key() -> None:
    node = {"tag": "Law"}
    assert H._children_with_tag(node, "Article") == []


def test_children_with_tag_filters_non_dicts() -> None:
    node = {"children": [{"tag": "Article"}, "string-item", 42]}
    result = H._children_with_tag(node, "Article")
    assert len(result) == 1


def test_children_with_tag_filters_wrong_tag() -> None:
    node = {
        "children": [
            {"tag": "Article", "num": "1"},
            {"tag": "ArticleCaption", "text": "cap"},
        ]
    }
    result = H._children_with_tag(node, "Article")
    assert len(result) == 1
    assert result[0]["num"] == "1"


# ─── _first_child ────────────────────────────────────────────────────────────

def test_first_child_returns_first_matching() -> None:
    node = {
        "children": [
            {"tag": "Article", "num": "1"},
            {"tag": "Article", "num": "2"},
        ]
    }
    result = H._first_child(node, "Article")
    assert result is not None
    assert result["num"] == "1"


def test_first_child_returns_none_when_no_match() -> None:
    node = {"children": [{"tag": "Chapter"}]}
    assert H._first_child(node, "Article") is None


def test_first_child_empty_children_returns_none() -> None:
    node = {"children": []}
    assert H._first_child(node, "Article") is None


def test_first_child_no_children_key_returns_none() -> None:
    node = {"tag": "Law"}
    assert H._first_child(node, "Article") is None


# ─── _find_first_tag ─────────────────────────────────────────────────────────

def test_find_first_tag_finds_at_top_level() -> None:
    node = {"tag": "Article", "num": "1", "children": []}
    result = H._find_first_tag(node, "Article")
    assert result is not None
    assert result["tag"] == "Article"


def test_find_first_tag_finds_nested() -> None:
    tree = {
        "tag": "Law",
        "children": [
            {
                "tag": "LawBody",
                "children": [
                    {"tag": "Article", "num": "1", "children": []},
                ],
            }
        ],
    }
    result = H._find_first_tag(tree, "Article")
    assert result is not None
    assert result["tag"] == "Article"
    assert result["num"] == "1"


def test_find_first_tag_returns_none_when_missing() -> None:
    node = {"tag": "Law", "children": [{"tag": "Chapter"}]}
    assert H._find_first_tag(node, "Article") is None


def test_find_first_tag_searches_list() -> None:
    nodes = [
        {"tag": "Chapter", "children": []},
        {"tag": "Article", "num": "1", "children": []},
    ]
    result = H._find_first_tag(nodes, "Article")
    assert result is not None
    assert result["num"] == "1"


def test_find_first_tag_empty_list_returns_none() -> None:
    assert H._find_first_tag([], "Article") is None


def test_find_first_tag_non_dict_non_list_returns_none() -> None:
    assert H._find_first_tag("string", "Article") is None
    assert H._find_first_tag(None, "Article") is None
    assert H._find_first_tag(42, "Article") is None


def test_find_first_tag_returns_first_match_not_all() -> None:
    tree = {
        "tag": "Law",
        "children": [
            {"tag": "Article", "num": "1", "children": []},
            {"tag": "Article", "num": "2", "children": []},
        ],
    }
    result = H._find_first_tag(tree, "Article")
    assert result is not None
    assert result["num"] == "1"


def test_find_first_tag_deeply_nested() -> None:
    tree = {
        "tag": "Law",
        "children": [
            {
                "tag": "LawBody",
                "children": [
                    {
                        "tag": "Chapter",
                        "children": [
                            {
                                "tag": "Section",
                                "children": [
                                    {"tag": "Article", "num": "42", "children": []},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = H._find_first_tag(tree, "Article")
    assert result is not None
    assert result["num"] == "42"
