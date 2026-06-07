"""Pure helper tests for jp_fiscal, handotai, and onion_crawl primitives.

Covers pure functions with no DB/HTTP dependencies:
- jp_fiscal: _utc_now / _today / _ubo_vid / _contract_vid / _is_dup_error /
             _OWNER_DID / _MINISTRY_URLS / _DEFAULT_MINISTRIES
- handotai: _utc_now / _src_vid / _art_vid / _dig_vid / _article_id /
            _guess_category / _strip_html / _OWNER_DID / _WRITERS /
            _CAT_KEYWORDS
- onion_crawl: _utc_now / _today / _sha / _onion_host_from_url /
               _onion_slug / _site_vid / _page_vid / _crawl_vid /
               _site_did / _clean_text / _extract_title / _extract_links /
               _classify / OWNER_DID / THREAT_KEYWORDS
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import jp_fiscal as JF
from kotodama.primitives import handotai as HT
from kotodama.primitives import onion_crawl as OC


# ─── jp_fiscal — _utc_now ────────────────────────────────────────────────────

def test_jf_utc_now_returns_string():
    assert isinstance(JF._utc_now(), str)


def test_jf_utc_now_ends_with_z():
    assert JF._utc_now().endswith("Z")


def test_jf_utc_now_contains_t():
    assert "T" in JF._utc_now()


# ─── jp_fiscal — _today ──────────────────────────────────────────────────────

def test_jf_today_returns_string():
    assert isinstance(JF._today(), str)


def test_jf_today_format():
    result = JF._today()
    parts = result.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4  # year


# ─── jp_fiscal — _ubo_vid ────────────────────────────────────────────────────

def test_jf_ubo_vid_starts_with_at():
    result = JF._ubo_vid("S20260101001")
    assert result.startswith("at://")


def test_jf_ubo_vid_contains_doc_id():
    result = JF._ubo_vid("S20260101001")
    assert "S20260101001" in result


def test_jf_ubo_vid_contains_owner_did():
    result = JF._ubo_vid("S001")
    assert "jp-fiscal.etzhayyim.com" in result


def test_jf_ubo_vid_contains_edinet_prefix():
    result = JF._ubo_vid("S001")
    assert "edinet-" in result


# ─── jp_fiscal — _contract_vid ───────────────────────────────────────────────

def test_jf_contract_vid_starts_with_at():
    result = JF._contract_vid("mof", "CNT-001", 1)
    assert result.startswith("at://")


def test_jf_contract_vid_contains_ministry():
    result = JF._contract_vid("mlit", "CNT-002", 1)
    assert "mlit" in result


def test_jf_contract_vid_sanitizes_slashes():
    result = JF._contract_vid("meti", "A/B/C", 1)
    assert "/" not in result.split("/com.etzhayyim.apps.jpFiscal.contract/")[1]


def test_jf_contract_vid_seq_fallback():
    result = JF._contract_vid("mhlw", "", 42)
    assert "mhlw" in result


# ─── jp_fiscal — _is_dup_error ───────────────────────────────────────────────

def test_jf_is_dup_error_already_exists():
    assert JF._is_dup_error(Exception("record already exists"))


def test_jf_is_dup_error_duplicate():
    assert JF._is_dup_error(Exception("duplicate key value"))


def test_jf_is_dup_error_unique():
    assert JF._is_dup_error(Exception("unique constraint violation"))


def test_jf_is_dup_error_other_error():
    assert not JF._is_dup_error(Exception("connection refused"))


def test_jf_is_dup_error_case_insensitive():
    assert JF._is_dup_error(Exception("ALREADY EXISTS in table"))


# ─── jp_fiscal — constants ───────────────────────────────────────────────────

def test_jf_owner_did_starts_with_did():
    assert JF._OWNER_DID.startswith("did:")


def test_jf_owner_did_contains_jp_fiscal():
    assert "jp-fiscal" in JF._OWNER_DID


def test_jf_ministry_urls_is_dict():
    assert isinstance(JF._MINISTRY_URLS, dict)


def test_jf_ministry_urls_not_empty():
    assert len(JF._MINISTRY_URLS) > 0


def test_jf_ministry_urls_contains_mof():
    assert "mof" in JF._MINISTRY_URLS


def test_jf_ministry_urls_values_are_strings():
    for v in JF._MINISTRY_URLS.values():
        assert isinstance(v, str)
        assert v.startswith("https://")


def test_jf_default_ministries_is_list():
    assert isinstance(JF._DEFAULT_MINISTRIES, list)


def test_jf_default_ministries_not_empty():
    assert len(JF._DEFAULT_MINISTRIES) > 0


def test_jf_default_ministries_matches_keys():
    assert set(JF._DEFAULT_MINISTRIES) == set(JF._MINISTRY_URLS.keys())


# ─── handotai — _utc_now ─────────────────────────────────────────────────────

def test_ht_utc_now_returns_string():
    assert isinstance(HT._utc_now(), str)


def test_ht_utc_now_ends_with_z():
    assert HT._utc_now().endswith("Z")


def test_ht_utc_now_contains_t():
    assert "T" in HT._utc_now()


# ─── handotai — vid helpers ───────────────────────────────────────────────────

def test_ht_src_vid_starts_with_at():
    result = HT._src_vid("src-pcw")
    assert result.startswith("at://")


def test_ht_src_vid_contains_source_id():
    result = HT._src_vid("src-eet")
    assert "src-eet" in result


def test_ht_art_vid_starts_with_at():
    result = HT._art_vid("art-abc123")
    assert result.startswith("at://")


def test_ht_art_vid_contains_article_id():
    result = HT._art_vid("art-xyz")
    assert "art-xyz" in result


def test_ht_dig_vid_starts_with_at():
    result = HT._dig_vid("2026-04-29")
    assert result.startswith("at://")


def test_ht_dig_vid_contains_date():
    result = HT._dig_vid("2026-04-29")
    assert "2026-04-29" in result


# ─── handotai — _article_id ──────────────────────────────────────────────────

def test_ht_article_id_starts_with_art():
    result = HT._article_id("https://example.com/article")
    assert result.startswith("art-")


def test_ht_article_id_deterministic():
    a = HT._article_id("https://example.com/article/1")
    b = HT._article_id("https://example.com/article/1")
    assert a == b


def test_ht_article_id_differs_by_url():
    a = HT._article_id("https://example.com/1")
    b = HT._article_id("https://example.com/2")
    assert a != b


def test_ht_article_id_has_fixed_length():
    result = HT._article_id("https://example.com/article")
    assert len(result) == 4 + 16  # "art-" + 16 hex chars


# ─── handotai — _guess_category ──────────────────────────────────────────────

def test_ht_guess_category_tsmc_is_fabrication():
    result = HT._guess_category("TSMC announces new 2nm process", "default")
    assert result == "fabrication"


def test_ht_guess_category_gpu_is_market():
    result = HT._guess_category("Nvidia GPU accelerator for AI training", "default")
    assert result == "market"


def test_ht_guess_category_asml_is_equipment():
    result = HT._guess_category("ASML ships new EUV scanner", "default")
    assert result == "equipment"


def test_ht_guess_category_no_match_returns_default():
    result = HT._guess_category("Unrelated topic about cooking", "other")
    assert result == "other"


def test_ht_guess_category_case_insensitive():
    result = HT._guess_category("DRAM prices are falling", "default")
    assert result == "materials"


def test_ht_guess_category_empty_text_returns_default():
    result = HT._guess_category("", "fallback")
    assert result == "fallback"


# ─── handotai — _strip_html ──────────────────────────────────────────────────

def test_ht_strip_html_removes_tags():
    result = HT._strip_html("<p>Hello <b>world</b></p>")
    assert result == "Hello world"


def test_ht_strip_html_empty_returns_empty():
    assert HT._strip_html("") == ""


def test_ht_strip_html_none_returns_empty():
    assert HT._strip_html(None) == ""  # type: ignore[arg-type]


def test_ht_strip_html_plain_text_unchanged():
    result = HT._strip_html("plain text")
    assert result == "plain text"


def test_ht_strip_html_truncates_at_1000():
    long_text = "x" * 2000
    result = HT._strip_html(long_text)
    assert len(result) <= 1000


# ─── handotai — constants ─────────────────────────────────────────────────────

def test_ht_owner_did_starts_with_did():
    assert HT._OWNER_DID.startswith("did:")


def test_ht_owner_did_contains_handotai():
    assert "handotai" in HT._OWNER_DID


def test_ht_writers_is_list():
    assert isinstance(HT._WRITERS, list)


def test_ht_writers_not_empty():
    assert len(HT._WRITERS) > 0


def test_ht_writers_have_source_id():
    for w in HT._WRITERS:
        assert "source_id" in w
        assert isinstance(w["source_id"], str)


def test_ht_writers_have_url():
    for w in HT._WRITERS:
        assert "url" in w
        assert w["url"].startswith("https://")


def test_ht_writers_have_language():
    for w in HT._WRITERS:
        assert "language" in w


def test_ht_cat_keywords_is_list():
    assert isinstance(HT._CAT_KEYWORDS, list)


def test_ht_cat_keywords_not_empty():
    assert len(HT._CAT_KEYWORDS) > 0


def test_ht_cat_keywords_are_tuples():
    for entry in HT._CAT_KEYWORDS:
        kws, cat = entry
        assert isinstance(kws, list)
        assert isinstance(cat, str)


# ─── onion_crawl — _utc_now ──────────────────────────────────────────────────

def test_oc_utc_now_returns_string():
    assert isinstance(OC._utc_now(), str)


def test_oc_utc_now_ends_with_z():
    assert OC._utc_now().endswith("Z")


def test_oc_utc_now_contains_t():
    assert "T" in OC._utc_now()


# ─── onion_crawl — _today ────────────────────────────────────────────────────

def test_oc_today_returns_string():
    assert isinstance(OC._today(), str)


def test_oc_today_is_date_format():
    result = OC._today()
    assert len(result) == 10
    assert result[4] == "-" and result[7] == "-"


# ─── onion_crawl — _sha ──────────────────────────────────────────────────────

def test_oc_sha_starts_with_prefix():
    result = OC._sha("p", "http://example.onion/page")
    assert result.startswith("p-")


def test_oc_sha_is_deterministic():
    a = OC._sha("h", "abc.onion")
    b = OC._sha("h", "abc.onion")
    assert a == b


def test_oc_sha_differs_by_parts():
    a = OC._sha("h", "abc.onion")
    b = OC._sha("h", "def.onion")
    assert a != b


def test_oc_sha_has_24_hex_chars():
    result = OC._sha("p", "url")
    hex_part = result[2:]  # strip "p-"
    assert len(hex_part) == 24


# ─── onion_crawl — _onion_host_from_url ──────────────────────────────────────

def test_oc_onion_host_from_url_extracts_host():
    result = OC._onion_host_from_url("http://abc123.onion/path")
    assert result == "abc123.onion"


def test_oc_onion_host_from_url_lowercases():
    result = OC._onion_host_from_url("http://ABC.ONION/")
    assert result == "abc.onion"


def test_oc_onion_host_from_url_empty_returns_empty():
    result = OC._onion_host_from_url("")
    assert result == ""


def test_oc_onion_host_from_url_no_host_returns_empty():
    result = OC._onion_host_from_url("not-a-url")
    assert result == ""


# ─── onion_crawl — _onion_slug ───────────────────────────────────────────────

def test_oc_onion_slug_strips_onion_suffix():
    result = OC._onion_slug("abcdefgh.onion")
    assert result == "abcdefgh"


def test_oc_onion_slug_no_suffix_returns_as_is():
    result = OC._onion_slug("myhost")
    assert result == "myhost"


def test_oc_onion_slug_empty_falls_back():
    result = OC._onion_slug("")
    assert len(result) > 0


# ─── onion_crawl — vid helpers ───────────────────────────────────────────────

def test_oc_site_vid_starts_with_at():
    result = OC._site_vid("abc.onion")
    assert result.startswith("at://")


def test_oc_site_vid_contains_slug():
    result = OC._site_vid("abc.onion")
    assert "abc" in result


def test_oc_page_vid_starts_with_at():
    result = OC._page_vid("http://abc.onion/page")
    assert result.startswith("at://")


def test_oc_crawl_vid_starts_with_at():
    result = OC._crawl_vid("abc.onion", "2026-04-29T12:00:00Z")
    assert result.startswith("at://")


def test_oc_site_did_starts_with_did():
    result = OC._site_did("abc.onion")
    assert result.startswith("did:")


def test_oc_site_did_contains_onion_etzhayyim():
    result = OC._site_did("abc.onion")
    assert "onion.etzhayyim.com" in result


# ─── onion_crawl — _clean_text ───────────────────────────────────────────────

def test_oc_clean_text_removes_tags():
    result = OC._clean_text("<p>Hello <b>world</b></p>", 1000)
    assert "Hello world" in result
    assert "<" not in result


def test_oc_clean_text_removes_script():
    result = OC._clean_text("<script>alert('x')</script>text", 1000)
    assert "alert" not in result
    assert "text" in result


def test_oc_clean_text_removes_style():
    result = OC._clean_text("<style>body{color:red}</style>text", 1000)
    assert "color" not in result
    assert "text" in result


def test_oc_clean_text_respects_limit():
    result = OC._clean_text("a" * 5000, 100)
    assert len(result) <= 100


def test_oc_clean_text_strips_whitespace():
    result = OC._clean_text("  hello  ", 1000)
    assert result == "hello"


# ─── onion_crawl — _extract_title ────────────────────────────────────────────

def test_oc_extract_title_from_title_tag():
    result = OC._extract_title("<html><title>My Page</title></html>")
    assert result == "My Page"


def test_oc_extract_title_from_h1():
    result = OC._extract_title("<html><h1>Main Heading</h1></html>")
    assert result == "Main Heading"


def test_oc_extract_title_empty_html():
    result = OC._extract_title("<html></html>")
    assert result == ""


def test_oc_extract_title_empty_string():
    result = OC._extract_title("")
    assert result == ""


# ─── onion_crawl — _extract_links ────────────────────────────────────────────

def test_oc_extract_links_returns_list():
    html = '<a href="http://abc.onion/page">link</a>'
    result = OC._extract_links(html, "http://abc.onion/")
    assert isinstance(result, list)


def test_oc_extract_links_same_host():
    html = '<a href="/page2">link</a>'
    result = OC._extract_links(html, "http://abc.onion/")
    assert all("abc.onion" in u for u in result)


def test_oc_extract_links_skips_hash_links():
    html = '<a href="#section">anchor</a>'
    result = OC._extract_links(html, "http://abc.onion/")
    assert result == []


def test_oc_extract_links_skips_javascript():
    html = "<a href=\"javascript:void(0)\">click</a>"
    result = OC._extract_links(html, "http://abc.onion/")
    assert result == []


def test_oc_extract_links_empty_html():
    result = OC._extract_links("", "http://abc.onion/")
    assert result == []


# ─── onion_crawl — _classify ─────────────────────────────────────────────────

def test_oc_classify_returns_dict():
    result = OC._classify("some text")
    assert isinstance(result, dict)


def test_oc_classify_has_required_keys():
    result = OC._classify("drugs for sale")
    for key in ("category", "threatIndicators", "riskScore"):
        assert key in result


def test_oc_classify_empty_is_unknown():
    result = OC._classify("")
    assert result["category"] == "unknown"
    assert result["riskScore"] == 0


def test_oc_classify_risk_score_is_int():
    result = OC._classify("weapons illegal firearms")
    assert isinstance(result["riskScore"], int)


def test_oc_classify_risk_score_bounded():
    result = OC._classify("drugs guns hacking fraud bitcoin money laundering ransom")
    assert 0 <= result["riskScore"] <= 100


def test_oc_classify_threat_indicators_is_list():
    result = OC._classify("buy drugs online")
    assert isinstance(result["threatIndicators"], list)


# ─── onion_crawl — constants ─────────────────────────────────────────────────

def test_oc_owner_did_starts_with_did():
    assert OC.OWNER_DID.startswith("did:")


def test_oc_owner_did_contains_onion():
    assert "onion" in OC.OWNER_DID


def test_oc_threat_keywords_is_dict():
    assert isinstance(OC.THREAT_KEYWORDS, dict)


def test_oc_threat_keywords_not_empty():
    assert len(OC.THREAT_KEYWORDS) > 0


def test_oc_threat_keywords_values_are_tuples():
    for v in OC.THREAT_KEYWORDS.values():
        assert isinstance(v, tuple)


def test_oc_max_internal_links_positive():
    assert OC.MAX_INTERNAL_LINKS > 0
