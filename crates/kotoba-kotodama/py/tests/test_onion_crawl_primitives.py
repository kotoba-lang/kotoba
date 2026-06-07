"""Tests for onion_crawl primitives (pure helpers + queue logic)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import onion_crawl as OC  # noqa: E402


# ─── pure helper tests ────────────────────────────────────────────────────

def test_sha_is_deterministic():
    a = OC._sha("p", "http://example.onion/")
    b = OC._sha("p", "http://example.onion/")
    assert a == b
    assert a.startswith("p-")
    assert len(a) == 2 + 24  # "p-" + 24 hex chars


def test_sha_differs_for_different_inputs():
    a = OC._sha("p", "http://abc.onion/")
    b = OC._sha("p", "http://xyz.onion/")
    assert a != b


def test_onion_host_from_url_extracts_hostname():
    assert OC._onion_host_from_url("http://abcdef1234567890.onion/path") == "abcdef1234567890.onion"


def test_onion_host_from_url_lowercases():
    assert OC._onion_host_from_url("HTTP://ABC.ONION/") == "abc.onion"


def test_onion_host_from_url_returns_empty_on_invalid():
    assert OC._onion_host_from_url("not-a-url") == ""


def test_onion_slug_strips_onion_suffix():
    assert OC._onion_slug("abcdef1234567890.onion") == "abcdef1234567890"


def test_onion_slug_non_onion_host():
    slug = OC._onion_slug("example.com")
    assert slug  # something non-empty


def test_site_vid_format():
    vid = OC._site_vid("abc12345.onion")
    assert vid.startswith("at://did:web:onion.etzhayyim.com/")
    assert "abc12345" in vid


def test_page_vid_format():
    vid = OC._page_vid("http://abc12345.onion/page1")
    assert vid.startswith("at://did:web:onion.etzhayyim.com/")


def test_crawl_vid_format():
    vid = OC._crawl_vid("abc12345.onion", "2026-04-29T10:00:00Z")
    assert "abc12345" in vid
    assert vid.startswith("at://")


def test_site_did_format():
    did = OC._site_did("abc12345.onion")
    assert did == "did:web:onion.etzhayyim.com:abc12345"


def test_clean_text_strips_html_tags():
    raw = "<p>Hello <b>World</b></p>"
    result = OC._clean_text(raw, 500)
    assert "<" not in result
    assert "Hello" in result
    assert "World" in result


def test_clean_text_removes_scripts():
    raw = "<script>alert('xss')</script>clean text"
    result = OC._clean_text(raw, 500)
    assert "alert" not in result
    assert "clean text" in result


def test_clean_text_respects_limit():
    raw = "A" * 1000
    result = OC._clean_text(raw, 100)
    assert len(result) <= 100


def test_extract_title_from_title_tag():
    html = "<html><head><title>Dark Market</title></head><body>...</body></html>"
    assert OC._extract_title(html) == "Dark Market"


def test_extract_title_falls_back_to_h1():
    html = "<html><body><h1>Main heading</h1></body></html>"
    assert OC._extract_title(html) == "Main heading"


def test_extract_title_empty_when_no_tags():
    assert OC._extract_title("<p>no heading</p>") == ""


def test_extract_links_returns_internal_onion_links():
    html = """
    <a href="http://abc.onion/page1">p1</a>
    <a href="http://abc.onion/page2">p2</a>
    <a href="http://other.onion/page">external</a>
    <a href="https://clearnet.com/">clearnet</a>
    """
    links = OC._extract_links(html, "http://abc.onion/")
    assert "http://abc.onion/page1" in links
    assert "http://abc.onion/page2" in links
    assert all("other.onion" not in l for l in links)
    assert all("clearnet" not in l for l in links)


def test_extract_links_caps_at_max():
    hrefs = "".join(f'<a href="http://abc.onion/p{i}">x</a>' for i in range(20))
    html = f"<body>{hrefs}</body>"
    links = OC._extract_links(html, "http://abc.onion/")
    assert len(links) <= OC.MAX_INTERNAL_LINKS


def test_extract_links_deduplicates():
    html = '<a href="http://abc.onion/p1">a</a><a href="http://abc.onion/p1">b</a>'
    links = OC._extract_links(html, "http://abc.onion/")
    assert links.count("http://abc.onion/p1") == 1


def test_extract_links_skips_anchors():
    html = '<a href="#section">anchor</a>'
    links = OC._extract_links(html, "http://abc.onion/")
    assert links == []


def test_classify_clean_text_returns_unknown():
    result = OC._classify("Welcome to our community forum")
    assert result["category"] == "unknown"
    assert result["riskScore"] == 0
    assert result["threatIndicators"] == []


def test_classify_marketplace_keywords():
    result = OC._classify("buy drugs with bitcoin escrow vendor market")
    # should detect both drugs and marketplace
    assert result["riskScore"] > 0
    assert result["category"] in OC.THREAT_KEYWORDS


def test_classify_ransomware_keywords():
    result = OC._classify("ransomware leak site victim files decryptor payment")
    assert "ransomware" in result["category"]
    assert result["riskScore"] > 0


def test_classify_risk_score_capped_at_100():
    text = " ".join(kw for kws in OC.THREAT_KEYWORDS.values() for kw in kws) * 10
    result = OC._classify(text)
    assert result["riskScore"] <= 100


# ─── _normalize_explicit_seeds tests ─────────────────────────────────────

def test_normalize_explicit_seeds_accepts_strings():
    seeds, skipped = OC._normalize_explicit_seeds(
        ["http://abc123.onion/", "http://xyz456.onion/"],
        "drugs",
    )
    assert len(seeds) == 2
    assert skipped == 0
    assert seeds[0]["category"] == "drugs"


def test_normalize_explicit_seeds_accepts_dicts():
    seeds, skipped = OC._normalize_explicit_seeds(
        [{"url": "http://abc123.onion/", "category": "fraud"}],
        None,
    )
    assert len(seeds) == 1
    assert seeds[0]["category"] == "fraud"


def test_normalize_explicit_seeds_skips_non_onion():
    seeds, skipped = OC._normalize_explicit_seeds(
        ["http://clearnet.com/", "http://abc.onion/"],
        None,
    )
    assert len(seeds) == 1
    assert skipped == 1


def test_normalize_explicit_seeds_deduplicates():
    seeds, skipped = OC._normalize_explicit_seeds(
        ["http://abc.onion/", "http://abc.onion/"],
        None,
    )
    assert len(seeds) == 1
    assert skipped == 1


def test_normalize_explicit_seeds_skips_invalid_types():
    seeds, skipped = OC._normalize_explicit_seeds([42, None, "http://abc.onion/"], None)
    assert len(seeds) == 1
    assert skipped == 2


# ─── queue_seeds integration (mocked DB) ────────────────────────────────

def test_queue_seeds_with_explicit_onion_urls(monkeypatch):
    monkeypatch.setattr(OC, "_claim_stale_seeds", lambda limit: [])
    result = OC.queue_seeds(
        seeds=["http://abc123.onion/", "http://xyz456.onion/"],
        category="hacking",
        limit=5,
    )
    assert result["queued"] == 2
    assert result["skipped"] == 0


def test_queue_seeds_falls_back_to_stale(monkeypatch):
    stale = [{"url": "http://stale001.onion/", "host": "stale001.onion", "category": None}]
    monkeypatch.setattr(OC, "_claim_stale_seeds", lambda limit: stale)
    result = OC.queue_seeds(seeds=[], limit=3)
    assert result["queued"] == 1


def test_queue_seeds_caps_runs_at_limit(monkeypatch):
    monkeypatch.setattr(OC, "_claim_stale_seeds", lambda limit: [])
    urls = [f"http://site{i:03d}.onion/" for i in range(10)]
    result = OC.queue_seeds(seeds=urls, limit=3)
    assert len(result["runs"]) <= 3


def test_queue_seeds_skips_non_onion_in_explicit_list(monkeypatch):
    monkeypatch.setattr(OC, "_claim_stale_seeds", lambda limit: [])
    result = OC.queue_seeds(seeds=["http://clearnet.com/", "http://abc.onion/"])
    assert result["queued"] == 1
    assert result["skipped"] == 1


# ─── process_queue (fully mocked) ────────────────────────────────────────

def test_process_queue_empty_runs():
    result = OC.process_queue(runs=[])
    assert result["processed"] == 0
    assert result["completed"] == 0
    assert result["failed"] == 0


def test_process_queue_skips_non_dict():
    result = OC.process_queue(runs=["not-a-dict", 42])
    assert result["failed"] == 2


def test_process_queue_skips_non_onion_host():
    result = OC.process_queue(runs=[{"url": "http://clearnet.com/", "host": "clearnet.com"}])
    assert result["failed"] == 1


def test_process_queue_handles_proxy_failure(monkeypatch):
    monkeypatch.setattr(OC, "_ensure_site", lambda host, **kw: "vid_001")
    monkeypatch.setattr(OC, "_fetch_via_proxy", lambda url, timeout: {"ok": False, "html": "", "error": "timeout", "outboundLinks": [], "title": "", "statusCode": 0})
    monkeypatch.setattr(OC, "_update_site", lambda *a, **kw: None)
    monkeypatch.setattr(OC, "_write_crawl", lambda *a, **kw: "crawl_vid")
    result = OC.process_queue(runs=[{"url": "http://abc.onion/", "host": "abc.onion", "category": None}])
    assert result["failed"] == 1
    assert result["completed"] == 0


def test_process_queue_handles_successful_crawl(monkeypatch):
    monkeypatch.setattr(OC, "_ensure_site", lambda host, **kw: "vid_001")
    monkeypatch.setattr(OC, "_fetch_via_proxy", lambda url, timeout: {
        "ok": True, "html": "<title>Test</title>", "error": "",
        "outboundLinks": [], "title": "Test", "statusCode": 200,
    })
    monkeypatch.setattr(OC, "_update_site", lambda *a, **kw: None)
    monkeypatch.setattr(OC, "_write_crawl", lambda *a, **kw: "crawl_vid")
    monkeypatch.setattr(OC, "_write_page", lambda **kw: (True, {"category": "unknown", "riskScore": 0, "links": []}))
    result = OC.process_queue(runs=[{"url": "http://abc.onion/", "host": "abc.onion", "category": None}])
    assert result["completed"] == 1
    assert result["pagesWritten"] == 1


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_two_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    OC.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {"onion.crawl.queueSeeds", "onion.crawl.processQueue"}


def test_task_queue_seeds_wraps_queue_seeds(monkeypatch):
    monkeypatch.setattr(OC, "queue_seeds", lambda **kw: {"queued": 1, "skipped": 0, "runs": []})
    result = asyncio.run(OC.task_queue_seeds(seeds=[], limit=5))
    assert result["queued"] == 1


def test_task_process_queue_wraps_process_queue(monkeypatch):
    monkeypatch.setattr(OC, "process_queue", lambda **kw: {"processed": 0, "completed": 0, "failed": 0, "pagesWritten": 0})
    result = asyncio.run(OC.task_process_queue(runs=[], timeout_sec=30.0))
    assert result["processed"] == 0
