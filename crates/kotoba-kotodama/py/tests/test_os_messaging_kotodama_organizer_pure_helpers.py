"""Pure helper tests for os_messaging_open_channels and kotoba-kotodama_organizer primitives.

Covers pure functions with no DB/HTTP dependencies:
- os_messaging_open_channels: _utc_now / _today / _sha / _clean / _meta /
                               _title / _channel_vid / _message_vid / _run_vid /
                               _canonical_seed / _parse_messages /
                               OWNER_DID / KNOWN_PLATFORMS constants
- kotoba-kotodama_organizer: _utc_now_iso / KOTODAMA_DID / ORGANIZER_RUN_COLLECTION constants
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import os_messaging_open_channels as OC
from kotodama.primitives import kotoba-kotodama_organizer as MO


# ─── os_messaging — _utc_now / _today ────────────────────────────────────────

def test_oc_utc_now_returns_string():
    assert isinstance(OC._utc_now(), str)


def test_oc_utc_now_ends_with_z():
    assert OC._utc_now().endswith("Z")


def test_oc_today_is_date_format():
    result = OC._today()
    assert len(result) == 10
    assert result[4] == "-" and result[7] == "-"


# ─── os_messaging — _sha ─────────────────────────────────────────────────────

def test_oc_sha_starts_with_prefix():
    result = OC._sha("chan", "telegram", "channel1")
    assert result.startswith("chan-")


def test_oc_sha_is_deterministic():
    a = OC._sha("p", "val1", "val2")
    b = OC._sha("p", "val1", "val2")
    assert a == b


def test_oc_sha_differs_by_parts():
    a = OC._sha("p", "val1")
    b = OC._sha("p", "val2")
    assert a != b


def test_oc_sha_24_hex_chars_after_prefix():
    result = OC._sha("x", "test")
    hex_part = result[len("x-"):]
    assert len(hex_part) == 24


# ─── os_messaging — _clean ───────────────────────────────────────────────────

def test_oc_clean_strips_html_tags():
    result = OC._clean("<p>Hello <b>world</b></p>")
    assert "<" not in result
    assert "Hello" in result


def test_oc_clean_strips_script():
    result = OC._clean("<script>bad()</script>content")
    assert "bad" not in result
    assert "content" in result


def test_oc_clean_respects_limit():
    result = OC._clean("x" * 200, 50)
    assert len(result) <= 50


def test_oc_clean_empty_returns_empty():
    assert OC._clean("", 100) == ""


def test_oc_clean_unescapes_entities():
    result = OC._clean("&amp; &lt;", 100)
    assert "&" in result


# ─── os_messaging — _meta ────────────────────────────────────────────────────

def test_oc_meta_extracts_og_title():
    html = '<meta property="og:title" content="Test Page Title">'
    result = OC._meta(html, "og:title")
    assert result == "Test Page Title"


def test_oc_meta_returns_empty_when_missing():
    result = OC._meta("<html></html>", "og:title")
    assert result == ""


def test_oc_meta_name_attribute():
    html = '<meta name="description" content="Page description">'
    result = OC._meta(html, "description")
    assert result == "Page description"


# ─── os_messaging — _title ───────────────────────────────────────────────────

def test_oc_title_from_og_title():
    html = '<meta property="og:title" content="OG Title">'
    result = OC._title(html)
    assert result == "OG Title"


def test_oc_title_from_title_tag():
    html = "<html><title>Page Title</title></html>"
    result = OC._title(html)
    assert "Page Title" in result


def test_oc_title_empty_when_none():
    result = OC._title("<html></html>")
    assert result == ""


# ─── os_messaging — vid helpers ──────────────────────────────────────────────

def test_oc_channel_vid_starts_with_at():
    result = OC._channel_vid("telegram", "channel1")
    assert result.startswith("at://")


def test_oc_channel_vid_contains_platform():
    result = OC._channel_vid("telegram", "channel1")
    assert "telegram" in result


def test_oc_channel_vid_contains_channel_id():
    result = OC._channel_vid("telegram", "channel1")
    assert "channel1" in result


def test_oc_message_vid_starts_with_at():
    result = OC._message_vid("telegram", "msg-001")
    assert result.startswith("at://")


def test_oc_message_vid_contains_message_id():
    result = OC._message_vid("telegram", "msg-001")
    assert "msg-001" in result


def test_oc_run_vid_starts_with_at():
    result = OC._run_vid("run-abc")
    assert result.startswith("at://")


def test_oc_run_vid_contains_run_id():
    result = OC._run_vid("run-xyz")
    assert "run-xyz" in result


# ─── os_messaging — _canonical_seed ──────────────────────────────────────────

def test_oc_canonical_seed_platform_lowercased():
    result = OC._canonical_seed({"platform": "Telegram", "channelUrl": "https://t.me/s/test"})
    assert result["platform"] == "telegram"


def test_oc_canonical_seed_telegram_derives_channel_url():
    result = OC._canonical_seed({"platform": "telegram", "channelId": "testchannel"})
    assert "t.me" in result["channel_url"]
    assert "testchannel" in result["channel_url"]


def test_oc_canonical_seed_telegram_derives_channel_id_from_url():
    result = OC._canonical_seed({"platform": "telegram", "channelUrl": "https://t.me/s/mychannel"})
    assert result["channel_id"] == "mychannel"


def test_oc_canonical_seed_country_uppercased():
    result = OC._canonical_seed({"platform": "telegram", "country": "jp"})
    assert result["country"] == "JP"


def test_oc_canonical_seed_language_lowercased():
    result = OC._canonical_seed({"platform": "telegram", "language": "JA"})
    assert result["language"] == "ja"


def test_oc_canonical_seed_returns_dict():
    result = OC._canonical_seed({"platform": "telegram"})
    assert isinstance(result, dict)
    for key in ("platform", "channel_id", "channel_url", "country", "language"):
        assert key in result


# ─── os_messaging — _parse_messages ──────────────────────────────────────────

def test_oc_parse_messages_non_telegram_returns_empty():
    result = OC._parse_messages("line", "https://line.me/test", "<html>any html</html>")
    assert result == []


def test_oc_parse_messages_empty_html_returns_empty():
    result = OC._parse_messages("telegram", "https://t.me/s/test", "")
    assert result == []


def test_oc_parse_messages_returns_list():
    result = OC._parse_messages("telegram", "https://t.me/s/test", "<html></html>")
    assert isinstance(result, list)


# ─── os_messaging — constants ─────────────────────────────────────────────────

def test_oc_owner_did_starts_with_did():
    assert OC.OWNER_DID.startswith("did:")


def test_oc_known_platforms_is_set():
    assert isinstance(OC.KNOWN_PLATFORMS, set)


def test_oc_known_platforms_contains_telegram():
    assert "telegram" in OC.KNOWN_PLATFORMS


def test_oc_known_platforms_contains_line():
    assert "line" in OC.KNOWN_PLATFORMS


# ─── kotoba-kotodama_organizer — _utc_now_iso / constants ──────────────────────────

def test_mo_utc_now_iso_returns_string():
    assert isinstance(MO._utc_now_iso(), str)


def test_mo_utc_now_iso_ends_with_z():
    assert MO._utc_now_iso().endswith("Z")


def test_mo_utc_now_iso_contains_t():
    assert "T" in MO._utc_now_iso()


def test_mo_kotoba-kotodama_did_starts_with_did():
    assert MO.KOTODAMA_DID.startswith("did:")


def test_mo_kotoba-kotodama_did_contains_kotoba-kotodama():
    assert "kotoba-kotodama" in MO.KOTODAMA_DID


def test_mo_organizer_run_collection_is_string():
    assert isinstance(MO.ORGANIZER_RUN_COLLECTION, str)


def test_mo_organizer_run_collection_starts_with_ai_etzhayyim():
    assert MO.ORGANIZER_RUN_COLLECTION.startswith("com.etzhayyim.apps.")
