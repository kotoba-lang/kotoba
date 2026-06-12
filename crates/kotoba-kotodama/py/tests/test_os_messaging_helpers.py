"""Tests for pure helper functions in os_messaging_open_channels.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import os_messaging_open_channels as OSM


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_osm_clean_strips_html_tags() -> None:
    result = OSM._clean("<b>Hello</b> world")
    assert "<b>" not in result
    assert "Hello" in result and "world" in result


def test_osm_clean_removes_script() -> None:
    result = OSM._clean("<script>alert(1)</script>text")
    assert "alert" not in result
    assert "text" in result


def test_osm_clean_removes_style() -> None:
    result = OSM._clean("<style>body{color:red}</style>visible")
    assert "color" not in result
    assert "visible" in result


def test_osm_clean_collapses_whitespace() -> None:
    result = OSM._clean("a   b\tc")
    assert "   " not in result


def test_osm_clean_none_returns_empty() -> None:
    assert OSM._clean(None) == ""


def test_osm_clean_truncates_at_limit() -> None:
    result = OSM._clean("a" * 2000, limit=100)
    assert len(result) <= 100


# ─── _title ──────────────────────────────────────────────────────────────────

def test_osm_title_from_title_tag() -> None:
    html = "<html><head><title>My Channel</title></head></html>"
    assert OSM._title(html) == "My Channel"


def test_osm_title_prefers_og_title() -> None:
    html = '<html><head><meta property="og:title" content="OG Title"><title>Regular</title></head></html>'
    assert OSM._title(html) == "OG Title"


def test_osm_title_empty_html_returns_empty() -> None:
    assert OSM._title("<html></html>") == ""


# ─── _channel_vid ────────────────────────────────────────────────────────────

def test_osm_channel_vid_format() -> None:
    vid = OSM._channel_vid("telegram", "ch-123")
    assert "at://" in vid
    assert "com.etzhayyim.apps.osMessaging.openChannel" in vid
    assert "telegram-ch-123" in vid


def test_osm_channel_vid_deterministic() -> None:
    a = OSM._channel_vid("telegram", "ch")
    b = OSM._channel_vid("telegram", "ch")
    assert a == b


# ─── _message_vid ────────────────────────────────────────────────────────────

def test_osm_message_vid_format() -> None:
    vid = OSM._message_vid("line", "msg-001")
    assert "com.etzhayyim.apps.osMessaging.openMessage" in vid
    assert "line-msg-001" in vid


# ─── _run_vid ────────────────────────────────────────────────────────────────

def test_osm_run_vid_format() -> None:
    vid = OSM._run_vid("run-abc")
    assert "com.etzhayyim.apps.osMessaging.openScraperRun" in vid
    assert "run-abc" in vid


# ─── _canonical_seed ─────────────────────────────────────────────────────────

def test_osm_canonical_seed_basic() -> None:
    raw = {"platform": "Telegram", "channelId": "myChannel"}
    result = OSM._canonical_seed(raw)
    assert result["platform"] == "telegram"
    assert result["channel_id"] == "myChannel"


def test_osm_canonical_seed_telegram_url_extracts_id() -> None:
    raw = {"platform": "telegram", "channelUrl": "https://t.me/s/test_channel"}
    result = OSM._canonical_seed(raw)
    assert result["channel_id"] == "test_channel"


def test_osm_canonical_seed_telegram_id_builds_url() -> None:
    raw = {"platform": "telegram", "channelId": "news_bot"}
    result = OSM._canonical_seed(raw)
    assert "t.me" in result.get("channel_url", "")


def test_osm_canonical_seed_returns_dict_with_platform() -> None:
    raw = {"platform": "line", "channelUrl": "https://line.me/ch/123"}
    result = OSM._canonical_seed(raw)
    assert "platform" in result
    assert "channel_id" in result
    assert "channel_url" in result
