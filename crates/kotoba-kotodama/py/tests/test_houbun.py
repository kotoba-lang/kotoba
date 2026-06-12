"""
Unit tests for kotodama.handlers.houbun (ADR-0052 Phase 1).

Pure-function coverage:
- Article DID hash is deterministic + distinct across inputs.
- DID format matches `did:web:houbun.etzhayyim.com:article:{12hex}`.
- _flatten_text handles str / list / nested dicts / #text / attribute keys.
- _iter_articles extracts <Article> nodes and threads chapter label into section.

Handler coverage (async):
- ingestStatuteJpn rejects missing params.
- ingestStatuteJpn aborts cleanly if aiohttp is stubbed out.

DB writes are not exercised — _ingest_one is skipped when aiohttp fetch
is short-circuited. Full integration lands when the VKE Helm chart
smoke rolls.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() registers cleanly without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub

# Load houbun.py directly — bypasses handlers/__init__.py which eagerly
# imports shinka (needs langgraph) and causes NSID double-registration.
_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/houbun.py"
_spec = importlib.util.spec_from_file_location("_houbun_under_test", _src)
H = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(H)  # type: ignore[union-attr]

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Article DID hash
# ---------------------------------------------------------------------------


def test_article_did_deterministic():
    a = H._article_did("jpn", "129AC0000000089", "第九条", "")
    b = H._article_did("jpn", "129AC0000000089", "第九条", "")
    assert a == b
    assert a.startswith("did:web:houbun.etzhayyim.com:article:")
    assert len(a.rsplit(":", 1)[-1]) == 12


def test_article_did_varies_with_amendment():
    base = H._article_did("jpn", "129AC0000000089", "第九条", "")
    amended = H._article_did("jpn", "129AC0000000089", "第九条", "2023-04-01")
    assert base != amended


def test_article_did_varies_with_statute():
    a = H._article_did("jpn", "law-a", "第一条", "")
    b = H._article_did("jpn", "law-b", "第一条", "")
    assert a != b


def test_blake3_prefix12_is_12_hex():
    h = H._blake3_prefix12("jpn", "x", "y", "z")
    assert len(h) == 12
    assert all(ch in "0123456789abcdef" for ch in h)


# ---------------------------------------------------------------------------
# _flatten_text
# ---------------------------------------------------------------------------


def test_flatten_text_handles_primitives():
    assert H._flatten_text(None) == ""
    assert H._flatten_text("  hello   world  ") == "hello world"
    assert H._flatten_text(42) == "42"


def test_flatten_text_handles_lists():
    assert H._flatten_text(["a", "b", "c"]) == "a b c"


def test_flatten_text_handles_text_key():
    assert H._flatten_text({"#text": "foo"}) == "foo"
    assert H._flatten_text({"$": "bar"}) == "bar"


def test_flatten_text_skips_attribute_keys():
    payload = {"@attr": "ignored", "_meta": "ignored", "body": "kept"}
    assert H._flatten_text(payload) == "kept"


def test_flatten_text_nested_dict():
    payload = {"Article": {"ArticleTitle": "第九条", "Paragraph": "本文"}}
    out = H._flatten_text(payload)
    assert "第九条" in out
    assert "本文" in out


# ---------------------------------------------------------------------------
# _iter_articles
# ---------------------------------------------------------------------------


def test_iter_articles_flat_list():
    body = {
        "Article": [
            {
                "@": {"Num": "1"},
                "ArticleTitle": "第一条",
                "ArticleCaption": "(目的)",
                "Paragraph": "この法律は、民事に関する基本を定めるものとする。",
            },
            {
                "@": {"Num": "2"},
                "ArticleTitle": "第二条",
                "ArticleCaption": "(定義)",
                "Paragraph": "この法律において、次の用語はそれぞれ次の意味を有する。",
            },
        ]
    }
    out = H._iter_articles(body)
    assert len(out) == 2
    assert out[0]["article_no"] == "第一条"
    assert out[0]["title"] == "(目的)"
    assert "民事" in out[0]["text"]
    assert out[1]["article_no"] == "第二条"


def test_iter_articles_threads_chapter_label():
    body = {
        "Chapter": [
            {
                "ChapterTitle": "第一章 総則",
                "Article": [
                    {
                        "@": {"Num": "1"},
                        "ArticleTitle": "第一条",
                        "Paragraph": "総則の条文",
                    }
                ],
            },
            {
                "ChapterTitle": "第二章 契約",
                "Article": [
                    {
                        "@": {"Num": "521"},
                        "ArticleTitle": "第五百二十一条",
                        "Paragraph": "契約の成立",
                    }
                ],
            },
        ]
    }
    out = H._iter_articles(body)
    assert len(out) == 2
    assert out[0]["section"] == "第一章 総則"
    assert out[1]["section"] == "第二章 契約"
    assert "契約の成立" in out[1]["text"]


def test_iter_articles_empty_body_returns_empty_list():
    assert H._iter_articles(None) == []
    assert H._iter_articles({}) == []
    assert H._iter_articles({"Foo": "bar"}) == []


# ---------------------------------------------------------------------------
# Handler top-level (input validation only)
# ---------------------------------------------------------------------------


def test_ingestStatuteJpn_requires_lawid_or_since():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_statute_jpn.__wrapped__("{}")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestStatuteJpn_rejects_invalid_json():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_statute_jpn.__wrapped__("not-json")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestStatuteJpn_guards_missing_aiohttp():
    import asyncio
    from unittest.mock import patch
    with patch.object(H, "aiohttp", new=None):
        out = json.loads(asyncio.run(H.ingest_statute_jpn.__wrapped__(json.dumps({"lawId": "x"}))))  # type: ignore[attr-defined]
    assert "error" in out
    assert "aiohttp" in out["error"]


# ---------------------------------------------------------------------------
# Phase 2 — USA / EU / UN input validation
# ---------------------------------------------------------------------------


def test_ingestStatuteUsa_rejects_invalid_json():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_statute_usa.__wrapped__("not-json")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestStatuteUsa_rejects_unknown_collection():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_statute_usa.__wrapped__(json.dumps({"collection": "XYZ"}))))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestStatuteUsa_guards_missing_aiohttp():
    import asyncio
    from unittest.mock import patch
    with patch.object(H, "aiohttp", new=None):
        out = json.loads(asyncio.run(H.ingest_statute_usa.__wrapped__(json.dumps({"collection": "CFR"}))))  # type: ignore[attr-defined]
    assert "error" in out and "aiohttp" in out["error"]


def test_ingestEurLex_requires_celex_or_since():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_eur_lex.__wrapped__("{}")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestEurLex_rejects_invalid_json():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_eur_lex.__wrapped__("not-json")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestEurLex_guards_missing_aiohttp():
    import asyncio
    from unittest.mock import patch
    with patch.object(H, "aiohttp", new=None):
        out = json.loads(asyncio.run(H.ingest_eur_lex.__wrapped__(json.dumps({"celex": "32016R0679"}))))  # type: ignore[attr-defined]
    assert "error" in out and "aiohttp" in out["error"]


def test_ingestTreatyUn_requires_reg_or_since():
    import asyncio
    out = json.loads(asyncio.run(H.ingest_treaty_un.__wrapped__("{}")))  # type: ignore[attr-defined]
    assert "error" in out


def test_ingestTreatyUn_guards_missing_aiohttp():
    import asyncio
    from unittest.mock import patch
    with patch.object(H, "aiohttp", new=None):
        out = json.loads(asyncio.run(H.ingest_treaty_un.__wrapped__(json.dumps({"unRegNo": "123"}))))  # type: ignore[attr-defined]
    assert "error" in out and "aiohttp" in out["error"]


# ---------------------------------------------------------------------------
# EUR-Lex SPARQL helpers (no network)
# ---------------------------------------------------------------------------


def test_eurlex_query_single_includes_celex():
    q = H._eurlex_query_single("32016R0679")
    assert "32016R0679" in q
    assert "SELECT" in q and "LIMIT 1" in q


def test_eurlex_query_delta_applies_type_filter():
    q_reg = H._eurlex_query_delta("2024-01-01", "regulation", 50)
    q_dir = H._eurlex_query_delta("2024-01-01", "directive", 50)
    q_dec = H._eurlex_query_delta("2024-01-01", "decision", 50)
    assert 'SUBSTR(?celex, 6, 1) = "R"' in q_reg
    assert 'SUBSTR(?celex, 6, 1) = "L"' in q_dir
    assert 'SUBSTR(?celex, 6, 1) = "D"' in q_dec
    assert "LIMIT 50" in q_reg


def test_sparql_val_extracts_value():
    assert H._sparql_val({"x": {"value": "hello"}}, "x") == "hello"
    assert H._sparql_val({"x": {"value": 42}}, "x") == "42"
    assert H._sparql_val({}, "x") is None
    assert H._sparql_val({"x": None}, "x") is None
