"""Tests for pure helper functions in ingest/core.py and ingest/houbun.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import core as C
from kotodama.ingest import houbun as H


# ─── ingest/core.py pure helpers ─────────────────────────────────────────────

def test_slug_alphanumeric_passthrough() -> None:
    assert C._slug("hello") == "hello"


def test_slug_lowercases() -> None:
    assert C._slug("HelloWorld") == "helloworld"


def test_slug_replaces_special_chars_with_dash() -> None:
    result = C._slug("hello world!")
    assert " " not in result
    assert "!" not in result
    assert "hello" in result
    assert "world" in result


def test_slug_collapses_consecutive_separators() -> None:
    result = C._slug("a--b")
    assert "a" in result
    assert "b" in result
    assert "--" not in result


def test_slug_empty_returns_unknown() -> None:
    assert C._slug("") == "unknown"
    assert C._slug("   ") == "unknown"
    assert C._slug("!!!") == "unknown"


def test_slug_truncates_at_160() -> None:
    assert len(C._slug("a" * 300)) <= 160


def test_run_vertex_id_starts_with_did() -> None:
    vid = C.run_vertex_id("my-run-001")
    assert vid.startswith("at://did:web:ingest.etzhayyim.com/")


def test_run_vertex_id_contains_slug() -> None:
    vid = C.run_vertex_id("family-source-full-abc123")
    assert "family-source-full-abc123" in vid


def test_run_vertex_id_collection_in_path() -> None:
    vid = C.run_vertex_id("run-001")
    assert "com.etzhayyim.apps.ingest.run" in vid


def test_cursor_vertex_id_starts_with_did() -> None:
    vid = C.cursor_vertex_id("houbun", "jpn", "main")
    assert vid.startswith("at://did:web:ingest.etzhayyim.com/")


def test_cursor_vertex_id_collection_in_path() -> None:
    vid = C.cursor_vertex_id("houbun", "jpn", "main")
    assert "com.etzhayyim.apps.ingest.cursor" in vid


def test_cursor_vertex_id_deterministic() -> None:
    a = C.cursor_vertex_id("family", "source", "shard")
    b = C.cursor_vertex_id("family", "source", "shard")
    assert a == b


def test_cursor_vertex_id_varies_by_family() -> None:
    a = C.cursor_vertex_id("fam-a", "src", "shard")
    b = C.cursor_vertex_id("fam-b", "src", "shard")
    assert a != b


def test_artifact_vertex_id_starts_with_did() -> None:
    vid = C.artifact_vertex_id("run-001", "html", "https://example.com/page")
    assert vid.startswith("at://did:web:ingest.etzhayyim.com/")


def test_artifact_vertex_id_collection_in_path() -> None:
    vid = C.artifact_vertex_id("run-001", "html", "https://example.com/page")
    assert "com.etzhayyim.apps.ingest.artifact" in vid


def test_artifact_vertex_id_deterministic() -> None:
    a = C.artifact_vertex_id("run", "html", "https://example.com/")
    b = C.artifact_vertex_id("run", "html", "https://example.com/")
    assert a == b


def test_artifact_vertex_id_varies_by_uri() -> None:
    a = C.artifact_vertex_id("run", "html", "https://a.com/")
    b = C.artifact_vertex_id("run", "html", "https://b.com/")
    assert a != b


# ─── ingest/houbun.py pure helpers ──────────────────────────────────────────

def test_houbun_clean_strips_whitespace() -> None:
    assert H._clean("  hello  ") == "hello"


def test_houbun_clean_none_returns_empty() -> None:
    assert H._clean(None) == ""


def test_houbun_clean_collapses_internal_whitespace() -> None:
    result = H._clean("a  b\tc")
    assert "  " not in result
    assert "a" in result and "b" in result and "c" in result


def test_houbun_hash_deterministic() -> None:
    assert H._hash("a", "b", "c") == H._hash("a", "b", "c")


def test_houbun_hash_varies_with_parts() -> None:
    assert H._hash("x") != H._hash("y")


def test_houbun_hash_length_default() -> None:
    h = H._hash("test")
    assert len(h) == 12  # digest_size=6 → 12 hex chars


def test_houbun_hash_custom_size() -> None:
    h = H._hash("test", size=4)
    assert len(h) == 8


def test_flatten_none_returns_empty() -> None:
    assert H._flatten(None) == ""


def test_flatten_string_strips_whitespace() -> None:
    assert H._flatten("  hello  ") == "hello"


def test_flatten_integer() -> None:
    assert H._flatten(42) == "42"


def test_flatten_list_joins_parts() -> None:
    result = H._flatten(["a", "b", "c"])
    assert "a" in result and "b" in result and "c" in result


def test_flatten_dict_text_key() -> None:
    assert H._flatten({"#text": "hello"}) == "hello"


def test_flatten_dict_dollar_key() -> None:
    assert H._flatten({"$": "world"}) == "world"


def test_flatten_dict_children_key() -> None:
    result = H._flatten({"children": ["a", "b"]})
    assert "a" in result and "b" in result


def test_flatten_dict_skips_tag_attr_keys() -> None:
    payload = {"tag": "Article", "attr": {"Num": "1"}, "children": ["content"]}
    result = H._flatten(payload)
    assert "Article" not in result
    assert "content" in result


def test_flatten_dict_skips_at_underscore_prefixed_keys() -> None:
    payload = {"@attr": "ignored", "_meta": "ignored", "body": "kept"}
    result = H._flatten(payload)
    assert "ignored" not in result
    assert "kept" in result


def test_flatten_nested_dict() -> None:
    payload = {"outer": {"inner": "deep value"}}
    assert "deep value" in H._flatten(payload)


def test_children_with_tag_returns_matching() -> None:
    node = {
        "children": [
            {"tag": "ArticleTitle", "children": ["第一条"]},
            {"tag": "Paragraph", "children": ["本文"]},
            {"tag": "ArticleTitle", "children": ["第二条"]},
        ]
    }
    result = H._children_with_tag(node, "ArticleTitle")
    assert len(result) == 2


def test_children_with_tag_empty_on_no_match() -> None:
    node = {"children": [{"tag": "Paragraph", "children": ["text"]}]}
    assert H._children_with_tag(node, "Article") == []


def test_children_with_tag_missing_children_key() -> None:
    assert H._children_with_tag({}, "Article") == []


def test_first_child_returns_first_match() -> None:
    node = {
        "children": [
            {"tag": "ArticleTitle", "children": ["第一条"]},
            {"tag": "Paragraph", "children": ["本文"]},
        ]
    }
    result = H._first_child(node, "ArticleTitle")
    assert result is not None
    assert result["tag"] == "ArticleTitle"


def test_first_child_returns_none_on_miss() -> None:
    node = {"children": [{"tag": "Paragraph", "children": ["text"]}]}
    assert H._first_child(node, "Article") is None


def test_find_first_tag_finds_in_list() -> None:
    nodes = [
        {"tag": "Chapter", "children": []},
        {"tag": "Article", "children": [], "attr": {"Num": "1"}},
    ]
    result = H._find_first_tag(nodes, "Article")
    assert result is not None
    assert result["tag"] == "Article"


def test_find_first_tag_finds_nested() -> None:
    root = {
        "tag": "LawBody",
        "children": [
            {
                "tag": "Chapter",
                "children": [
                    {"tag": "Article", "children": [], "attr": {"Num": "1"}}
                ],
            }
        ],
    }
    result = H._find_first_tag(root, "Article")
    assert result is not None
    assert result["tag"] == "Article"


def test_find_first_tag_returns_none_on_miss() -> None:
    root = {"tag": "LawBody", "children": [{"tag": "Chapter", "children": []}]}
    assert H._find_first_tag(root, "Article") is None


def test_find_first_tag_non_dict_returns_none() -> None:
    assert H._find_first_tag("not a dict", "Article") is None
    assert H._find_first_tag(42, "Article") is None


def test_iter_articles_extracts_article_nodes() -> None:
    root = {
        "tag": "LawBody",
        "children": [
            {
                "tag": "Article",
                "attr": {"Num": "1"},
                "children": [
                    {"tag": "ArticleTitle", "children": ["第一条"]},
                    {"tag": "Paragraph", "children": ["本文"]},
                ],
            }
        ],
    }
    out = H._iter_articles(root)
    assert len(out) == 1
    assert out[0]["article_no"] == "第一条"
    assert "本文" in out[0]["text"]


def test_iter_articles_threads_chapter_label() -> None:
    root = {
        "tag": "LawBody",
        "children": [
            {
                "tag": "Chapter",
                "children": [
                    {"tag": "ChapterTitle", "children": ["第一章 総則"]},
                    {
                        "tag": "Article",
                        "attr": {"Num": "1"},
                        "children": [
                            {"tag": "ArticleTitle", "children": ["第一条"]},
                        ],
                    },
                ],
            }
        ],
    }
    out = H._iter_articles(root)
    assert len(out) == 1
    assert out[0]["section"] == "第一章 総則"


def test_iter_articles_empty_returns_empty_list() -> None:
    assert H._iter_articles(None) == []
    assert H._iter_articles({}) == []
    assert H._iter_articles([]) == []
