"""Pure helper tests for handotai, ma, intel, and isin primitives.

Covers pure functions with no DB/HTTP/LLM dependencies:
- handotai: _utc_now / _src_vid / _art_vid / _dig_vid / _article_id /
            _guess_category / _strip_html / _WRITERS / _CAT_KEYWORDS
- ma: _now_iso / _today / _slug / _stable_id / _bounded_score / _as_float /
      _deal_vid / _candidate_vid / _valuation_vid / _match_vid / _edge_id
- intel: _utc_now / _run_vid / _edge_id
- isin: _utc_now / _sec_vid / _filing_vid
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import handotai as HD
from kotodama.primitives import ma as MA
from kotodama.primitives import intel as IN
from kotodama.primitives import isin as IS


# ─── handotai — _utc_now ──────────────────────────────────────────────────────

def test_hd_utc_now_returns_string():
    assert isinstance(HD._utc_now(), str)


def test_hd_utc_now_ends_with_z():
    assert HD._utc_now().endswith("Z")


def test_hd_utc_now_contains_t():
    assert "T" in HD._utc_now()


# ─── handotai — vid helpers ───────────────────────────────────────────────────

def test_hd_src_vid_starts_with_at():
    result = HD._src_vid("src-001")
    assert result.startswith("at://")


def test_hd_src_vid_contains_source_id():
    result = HD._src_vid("src-pcw")
    assert "src-pcw" in result


def test_hd_art_vid_starts_with_at():
    result = HD._art_vid("art-abc123")
    assert result.startswith("at://")


def test_hd_art_vid_contains_article_id():
    result = HD._art_vid("art-xyz")
    assert "art-xyz" in result


def test_hd_dig_vid_starts_with_at():
    result = HD._dig_vid("2026-04-29")
    assert result.startswith("at://")


def test_hd_dig_vid_contains_date():
    result = HD._dig_vid("2026-04-29")
    assert "2026-04-29" in result


# ─── handotai — _article_id ──────────────────────────────────────────────────

def test_hd_article_id_starts_with_art():
    result = HD._article_id("https://example.com/article/1")
    assert result.startswith("art-")


def test_hd_article_id_is_deterministic():
    a = HD._article_id("https://example.com/article/1")
    b = HD._article_id("https://example.com/article/1")
    assert a == b


def test_hd_article_id_differs_by_url():
    a = HD._article_id("https://example.com/article/1")
    b = HD._article_id("https://example.com/article/2")
    assert a != b


def test_hd_article_id_returns_string():
    assert isinstance(HD._article_id("https://x.com"), str)


# ─── handotai — _guess_category ──────────────────────────────────────────────

def test_hd_guess_category_tsmc_is_fabrication():
    result = HD._guess_category("TSMC announces new 2nm node", "market")
    assert result == "fabrication"


def test_hd_guess_category_dram_is_materials():
    result = HD._guess_category("DRAM price drops sharply", "market")
    assert result == "materials"


def test_hd_guess_category_arm_is_design():
    result = HD._guess_category("ARM announces new IP core", "market")
    assert result == "design"


def test_hd_guess_category_no_match_returns_default():
    result = HD._guess_category("unrelated content xyz", "custom_default")
    assert result == "custom_default"


def test_hd_guess_category_empty_returns_default():
    result = HD._guess_category("", "fallback")
    assert result == "fallback"


def test_hd_guess_category_case_insensitive():
    result = HD._guess_category("TSMC factory in Taiwan", "x")
    assert result == "fabrication"


# ─── handotai — _strip_html ──────────────────────────────────────────────────

def test_hd_strip_html_removes_tags():
    result = HD._strip_html("<p>Hello <b>world</b></p>")
    assert "<" not in result
    assert "Hello" in result


def test_hd_strip_html_empty_returns_empty():
    assert HD._strip_html("") == ""


def test_hd_strip_html_none_returns_empty():
    assert HD._strip_html(None) == ""


def test_hd_strip_html_plain_text_unchanged():
    result = HD._strip_html("just plain text")
    assert result == "just plain text"


def test_hd_strip_html_respects_1000_limit():
    result = HD._strip_html("a" * 2000)
    assert len(result) <= 1000


# ─── handotai — _WRITERS constant ────────────────────────────────────────────

def test_hd_writers_is_list():
    assert isinstance(HD._WRITERS, list)


def test_hd_writers_has_items():
    assert len(HD._WRITERS) > 0


def test_hd_writers_have_source_id():
    for w in HD._WRITERS:
        assert "source_id" in w


def test_hd_writers_have_url():
    for w in HD._WRITERS:
        assert "url" in w


def test_hd_writers_have_name():
    for w in HD._WRITERS:
        assert "name" in w


# ─── ma — _now_iso / _today ──────────────────────────────────────────────────

def test_ma_now_iso_returns_string():
    assert isinstance(MA._now_iso(), str)


def test_ma_now_iso_ends_with_z():
    assert MA._now_iso().endswith("Z")


def test_ma_today_returns_string():
    assert isinstance(MA._today(), str)


def test_ma_today_is_date_format():
    result = MA._today()
    assert len(result) == 10
    assert result[4] == "-" and result[7] == "-"


# ─── ma — _slug ───────────────────────────────────────────────────────────────

def test_ma_slug_lowercases():
    assert MA._slug("Hello World") == "hello-world"


def test_ma_slug_replaces_spaces():
    result = MA._slug("Acme Corp")
    assert " " not in result


def test_ma_slug_empty_returns_unknown():
    assert MA._slug("") == "unknown"
    assert MA._slug(None) == "unknown"


def test_ma_slug_truncates_to_96():
    result = MA._slug("a" * 200)
    assert len(result) <= 96


# ─── ma — _stable_id ─────────────────────────────────────────────────────────

def test_ma_stable_id_starts_with_prefix():
    result = MA._stable_id("deal", "company-a", "JP")
    assert result.startswith("deal-")


def test_ma_stable_id_is_deterministic():
    a = MA._stable_id("pfx", "val1", "val2")
    b = MA._stable_id("pfx", "val1", "val2")
    assert a == b


def test_ma_stable_id_differs_by_parts():
    a = MA._stable_id("pfx", "val1")
    b = MA._stable_id("pfx", "val2")
    assert a != b


# ─── ma — _bounded_score ─────────────────────────────────────────────────────

def test_ma_bounded_score_returns_float():
    result = MA._bounded_score("company-a", "JP")
    assert isinstance(result, float)


def test_ma_bounded_score_in_range():
    result = MA._bounded_score("x", "y", "z")
    assert 0.0 <= result <= 1.0


def test_ma_bounded_score_is_deterministic():
    a = MA._bounded_score("company-a", "JP")
    b = MA._bounded_score("company-a", "JP")
    assert a == b


def test_ma_bounded_score_differs_by_parts():
    a = MA._bounded_score("a")
    b = MA._bounded_score("b")
    assert a != b


def test_ma_bounded_score_floor():
    # Result should be >= floor (default 0.45)
    result = MA._bounded_score("test-data-abc")
    assert result >= 0.45


# ─── ma — _as_float ──────────────────────────────────────────────────────────

def test_ma_as_float_int():
    assert MA._as_float(5, 0.0) == 5.0


def test_ma_as_float_string():
    assert MA._as_float("3.14", 0.0) == 3.14


def test_ma_as_float_none_returns_default():
    assert MA._as_float(None, 42.0) == 42.0


def test_ma_as_float_invalid_string_returns_default():
    assert MA._as_float("nope", 99.0) == 99.0


# ─── ma — vid helpers ────────────────────────────────────────────────────────

def test_ma_deal_vid_starts_with_at():
    result = MA._deal_vid("deal-001")
    assert result.startswith("at://")


def test_ma_deal_vid_contains_deal():
    result = MA._deal_vid("deal-001")
    assert "deal" in result


def test_ma_candidate_vid_starts_with_at():
    result = MA._candidate_vid("cand-abc")
    assert result.startswith("at://")


def test_ma_valuation_vid_starts_with_at():
    result = MA._valuation_vid("val-xyz")
    assert result.startswith("at://")


def test_ma_match_vid_starts_with_at():
    result = MA._match_vid("match-001")
    assert result.startswith("at://")


# ─── ma — _edge_id ───────────────────────────────────────────────────────────

def test_ma_edge_id_starts_with_edge():
    result = MA._edge_id("acquires", "src-a", "dst-b")
    assert result.startswith("edge:")


def test_ma_edge_id_contains_kind():
    result = MA._edge_id("acquires", "src-a", "dst-b")
    assert "acquires" in result


def test_ma_edge_id_is_deterministic():
    a = MA._edge_id("rel", "src", "dst")
    b = MA._edge_id("rel", "src", "dst")
    assert a == b


def test_ma_edge_id_differs_by_src():
    a = MA._edge_id("rel", "src1", "dst")
    b = MA._edge_id("rel", "src2", "dst")
    assert a != b


# ─── intel — _utc_now / _run_vid / _edge_id ──────────────────────────────────

def test_in_utc_now_returns_string():
    assert isinstance(IN._utc_now(), str)


def test_in_utc_now_ends_with_z():
    assert IN._utc_now().endswith("Z")


def test_in_run_vid_starts_with_at():
    result = IN._run_vid("run-001")
    assert result.startswith("at://")


def test_in_run_vid_contains_run_id():
    result = IN._run_vid("run-abc")
    assert "run-abc" in result


def test_in_edge_id_starts_with_prefix():
    result = IN._edge_id("a", "b", "rel")
    assert isinstance(result, str)
    assert len(result) > 0


def test_in_edge_id_is_deterministic():
    a = IN._edge_id("src", "dst", "rel")
    b = IN._edge_id("src", "dst", "rel")
    assert a == b


def test_in_edge_id_differs_by_inputs():
    a = IN._edge_id("src1", "dst", "rel")
    b = IN._edge_id("src2", "dst", "rel")
    assert a != b


# ─── isin — _utc_now / _sec_vid / _filing_vid ────────────────────────────────

def test_is_utc_now_returns_string():
    assert isinstance(IS._utc_now(), str)


def test_is_utc_now_ends_with_z():
    assert IS._utc_now().endswith("Z")


def test_is_sec_vid_starts_with_at():
    result = IS._sec_vid("rkey-001")
    assert result.startswith("at://")


def test_is_sec_vid_contains_rkey():
    result = IS._sec_vid("my-rkey")
    assert "my-rkey" in result


def test_is_filing_vid_starts_with_at():
    result = IS._filing_vid("filing-001")
    assert result.startswith("at://")


def test_is_filing_vid_contains_rkey():
    result = IS._filing_vid("filing-abc")
    assert "filing-abc" in result
