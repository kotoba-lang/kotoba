"""Pure helper tests for yoro_social, onion_crawl, and murakumo_fleet primitives.

Covers pure functions that have no DB/HTTP dependencies:
- yoro_social: utc_now_iso / _display_actor / build_social_post_record /
               build_repo_record
- onion_crawl: _utc_now / _today / _sha / _onion_host_from_url / _onion_slug /
               _site_vid / _page_vid / _crawl_vid / _site_did / _clean_text /
               _extract_title / _extract_links / _classify
- murakumo_fleet: _utc_now_iso / _extract_node_name / constants
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import yoro_social as YS
from kotodama.primitives import onion_crawl as OC
from kotodama.primitives import murakumo_fleet as MF


# ─── yoro_social — utc_now_iso ────────────────────────────────────────────────

def test_ys_utc_now_iso_returns_string():
    assert isinstance(YS.utc_now_iso(), str)


def test_ys_utc_now_iso_ends_with_z():
    assert YS.utc_now_iso().endswith("Z")


def test_ys_utc_now_iso_contains_t():
    assert "T" in YS.utc_now_iso()


# ─── yoro_social — _display_actor ────────────────────────────────────────────

def test_ys_display_actor_strips_did_web():
    result = YS._display_actor("did:web:shinshi.etzhayyim.com")
    assert result == "shinshi.etzhayyim.com"


def test_ys_display_actor_uses_handle_if_present():
    result = YS._display_actor("did:web:foo.etzhayyim.com", handle="@alice")
    assert result == "@alice"


def test_ys_display_actor_empty_falls_back_to_friend():
    result = YS._display_actor("", handle="")
    assert result == "friend"


def test_ys_display_actor_did_plc_returns_as_is():
    result = YS._display_actor("did:plc:abc123")
    assert result == "did:plc:abc123"


def test_ys_display_actor_returns_string():
    assert isinstance(YS._display_actor("did:web:test.etzhayyim.com"), str)


# ─── yoro_social — build_social_post_record ──────────────────────────────────

def test_ys_build_social_post_record_returns_dict():
    result = YS.build_social_post_record(text="hello")
    assert isinstance(result, dict)


def test_ys_build_social_post_record_has_uri():
    result = YS.build_social_post_record(text="test")
    assert "uri" in result
    assert result["uri"].startswith("at://")


def test_ys_build_social_post_record_has_collection():
    result = YS.build_social_post_record(text="test")
    assert "collection" in result


def test_ys_build_social_post_record_text_in_value_json():
    result = YS.build_social_post_record(text="hello world")
    assert "hello world" in result["value_json"]


def test_ys_build_social_post_record_custom_repo():
    result = YS.build_social_post_record(repo="did:web:custom.etzhayyim.com", text="x")
    assert "did:web:custom.etzhayyim.com" in result["uri"]


def test_ys_build_social_post_record_has_created_at():
    result = YS.build_social_post_record(text="test")
    assert "created_at" in result


def test_ys_build_social_post_record_explicit_rkey():
    result = YS.build_social_post_record(text="test", rkey="my-rkey-123")
    assert "my-rkey-123" in result["uri"]


# ─── yoro_social — build_repo_record ─────────────────────────────────────────

def test_ys_build_repo_record_returns_dict():
    result = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.feed.post",
        record={"$type": "app.bsky.feed.post", "text": "hello"},
    )
    assert isinstance(result, dict)


def test_ys_build_repo_record_uri_format():
    result = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.feed.post",
        record={"text": "hi"},
    )
    assert result["uri"].startswith("at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/")


def test_ys_build_repo_record_value_json_serialized():
    record = {"$type": "app.bsky.feed.post", "text": "test content"}
    result = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.feed.post",
        record=record,
    )
    assert "test content" in result["value_json"]


def test_ys_build_repo_record_explicit_rkey():
    result = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.feed.post",
        record={"text": "x"},
        rkey="explicit-rkey",
    )
    assert result["rkey"] == "explicit-rkey"


# ─── onion_crawl — _utc_now / _today ─────────────────────────────────────────

def test_oc_utc_now_returns_string():
    assert isinstance(OC._utc_now(), str)


def test_oc_utc_now_ends_with_z():
    assert OC._utc_now().endswith("Z")


def test_oc_today_returns_date_string():
    result = OC._today()
    assert len(result) == 10
    assert result[4] == "-" and result[7] == "-"


# ─── onion_crawl — _sha ──────────────────────────────────────────────────────

def test_oc_sha_starts_with_prefix():
    result = OC._sha("myprefix", "value1")
    assert result.startswith("myprefix-")


def test_oc_sha_is_deterministic():
    a = OC._sha("p", "url1", "url2")
    b = OC._sha("p", "url1", "url2")
    assert a == b


def test_oc_sha_differs_by_parts():
    a = OC._sha("p", "val1")
    b = OC._sha("p", "val2")
    assert a != b


def test_oc_sha_24_hex_chars_after_prefix():
    result = OC._sha("h", "test")
    hex_part = result[len("h-"):]
    assert len(hex_part) == 24
    int(hex_part, 16)  # raises ValueError if not hex


# ─── onion_crawl — _onion_host_from_url ──────────────────────────────────────

def test_oc_onion_host_from_url_returns_host():
    result = OC._onion_host_from_url("http://abc123xyz.onion/path")
    assert result == "abc123xyz.onion"


def test_oc_onion_host_from_url_lowercases():
    result = OC._onion_host_from_url("http://ABC123.ONION/")
    assert result == "abc123.onion"


def test_oc_onion_host_from_url_empty_on_invalid():
    result = OC._onion_host_from_url("")
    assert result == ""


# ─── onion_crawl — _onion_slug ───────────────────────────────────────────────

def test_oc_onion_slug_strips_dot_onion():
    result = OC._onion_slug("abc123xyz.onion")
    assert result == "abc123xyz"


def test_oc_onion_slug_no_onion_suffix():
    result = OC._onion_slug("plainhost")
    assert result == "plainhost"


def test_oc_onion_slug_returns_string():
    assert isinstance(OC._onion_slug("abc.onion"), str)


# ─── onion_crawl — _site_vid / _page_vid / _crawl_vid / _site_did ────────────

def test_oc_site_vid_starts_with_at():
    result = OC._site_vid("abc123.onion")
    assert result.startswith("at://")


def test_oc_site_vid_contains_onion():
    result = OC._site_vid("abc123.onion")
    assert "onion" in result


def test_oc_page_vid_starts_with_at():
    result = OC._page_vid("http://abc123.onion/page")
    assert result.startswith("at://")


def test_oc_crawl_vid_starts_with_at():
    result = OC._crawl_vid("abc.onion", "2026-01-01T00:00:00Z")
    assert result.startswith("at://")


def test_oc_site_did_starts_with_did():
    result = OC._site_did("abc123.onion")
    assert result.startswith("did:")


def test_oc_site_did_contains_onion_etzhayyim_ai():
    result = OC._site_did("abc123.onion")
    assert "onion.etzhayyim.com" in result


# ─── onion_crawl — _clean_text ───────────────────────────────────────────────

def test_oc_clean_text_strips_html_tags():
    result = OC._clean_text("<p>Hello <b>world</b></p>", 1000)
    assert "<" not in result
    assert "Hello" in result


def test_oc_clean_text_strips_script():
    result = OC._clean_text("<script>alert('x')</script>content", 1000)
    assert "alert" not in result
    assert "content" in result


def test_oc_clean_text_respects_limit():
    result = OC._clean_text("a" * 200, 50)
    assert len(result) <= 50


def test_oc_clean_text_empty_returns_empty():
    assert OC._clean_text("", 100) == ""


def test_oc_clean_text_unescapes_html_entities():
    result = OC._clean_text("&amp;", 100)
    assert "&" in result


# ─── onion_crawl — _extract_title ────────────────────────────────────────────

def test_oc_extract_title_from_title_tag():
    html = "<html><head><title>My Page Title</title></head></html>"
    result = OC._extract_title(html)
    assert result == "My Page Title"


def test_oc_extract_title_falls_back_to_h1():
    html = "<html><body><h1>Heading One</h1></body></html>"
    result = OC._extract_title(html)
    assert result == "Heading One"


def test_oc_extract_title_empty_on_no_title():
    html = "<html><body><p>No title here</p></body></html>"
    result = OC._extract_title(html)
    assert result == ""


def test_oc_extract_title_returns_string():
    assert isinstance(OC._extract_title("<title>x</title>"), str)


# ─── onion_crawl — _extract_links ────────────────────────────────────────────

def test_oc_extract_links_same_onion_domain():
    html = '<a href="/page2">link</a><a href="http://abc.onion/page3">link3</a>'
    base = "http://abc.onion/"
    links = OC._extract_links(html, base)
    assert "http://abc.onion/page2" in links
    assert "http://abc.onion/page3" in links


def test_oc_extract_links_excludes_external():
    html = '<a href="http://other.onion/page">ext</a>'
    base = "http://mine.onion/"
    links = OC._extract_links(html, base)
    assert len(links) == 0


def test_oc_extract_links_excludes_anchors():
    html = '<a href="#section">anchor</a>'
    base = "http://abc.onion/"
    links = OC._extract_links(html, base)
    assert len(links) == 0


def test_oc_extract_links_deduplicates():
    html = '<a href="/p">x</a><a href="/p">y</a>'
    base = "http://abc.onion/"
    links = OC._extract_links(html, base)
    assert links.count("http://abc.onion/p") == 1


def test_oc_extract_links_returns_list():
    result = OC._extract_links("", "http://abc.onion/")
    assert isinstance(result, list)


# ─── onion_crawl — _classify ─────────────────────────────────────────────────

def test_oc_classify_returns_dict():
    result = OC._classify("some text")
    assert isinstance(result, dict)


def test_oc_classify_has_required_keys():
    result = OC._classify("random text")
    assert "category" in result
    assert "threatIndicators" in result
    assert "riskScore" in result


def test_oc_classify_unknown_for_benign():
    result = OC._classify("hello world I am a website")
    assert result["category"] == "unknown" or result["riskScore"] == 0


def test_oc_classify_risk_score_bounded():
    result = OC._classify("drugs buy sell heroin cocaine marketplace darknet")
    assert 0 <= result["riskScore"] <= 100


def test_oc_classify_threat_indicators_is_list():
    result = OC._classify("some content")
    assert isinstance(result["threatIndicators"], list)


# ─── murakumo_fleet — _utc_now_iso ───────────────────────────────────────────

def test_mf_utc_now_iso_returns_string():
    assert isinstance(MF._utc_now_iso(), str)


def test_mf_utc_now_iso_ends_with_z():
    assert MF._utc_now_iso().endswith("Z")


# ─── murakumo_fleet — _extract_node_name ─────────────────────────────────────

def test_mf_extract_node_name_unknown_ip():
    result = MF._extract_node_name("http://999.999.999.999:4000")
    assert result == "unknown"


def test_mf_extract_node_name_returns_string():
    result = MF._extract_node_name("http://any-url:4000")
    assert isinstance(result, str)


def test_mf_extract_node_name_known_ip_returns_name():
    # pick first known IP from the NODE_IP_MAP
    if MF.NODE_IP_MAP:
        ip = next(iter(MF.NODE_IP_MAP))
        name = MF.NODE_IP_MAP[ip]
        result = MF._extract_node_name(f"http://{ip}:4000")
        assert result == name


# ─── murakumo_fleet — constants ──────────────────────────────────────────────

def test_mf_murakumo_did_starts_with_did():
    assert MF.MURAKUMO_DID.startswith("did:")


def test_mf_fleet_collection_is_string():
    assert isinstance(MF.FLEET_COLLECTION, str)


def test_mf_fleet_nodes_is_list():
    assert isinstance(MF.FLEET_NODES, list)


def test_mf_node_ip_map_is_dict():
    assert isinstance(MF.NODE_IP_MAP, dict)


def test_mf_health_timeout_sec_positive():
    assert MF.HEALTH_TIMEOUT_SEC > 0
