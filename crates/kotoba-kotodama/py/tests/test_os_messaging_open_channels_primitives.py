"""Tests for os_messaging_open_channels primitives."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import os_messaging_open_channels as OM  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_db():
    with patch("kotodama.primitives.os_messaging_open_channels.sync_cursor") as m:
        cur = MagicMock()
        cur.description = [("vertex_id",), ("platform",), ("channel_id",),
                           ("channel_url",), ("country",), ("language",)]
        cur.fetchall.return_value = []
        cur.rowcount = 1
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── _channel_vid / _message_vid (pure) ──────────────────────────────────────

def test_channel_vid_format():
    vid = OM._channel_vid("telegram", "channel123")
    assert vid.startswith("at://")
    assert OM.OWNER_DID in vid
    assert "telegram-channel123" in vid


def test_message_vid_format():
    vid = OM._message_vid("telegram", "msg-001")
    assert vid.startswith("at://")
    assert OM.OWNER_DID in vid
    assert "telegram-msg-001" in vid


def test_channel_and_message_vid_differ():
    channel = OM._channel_vid("telegram", "x")
    message = OM._message_vid("telegram", "x")
    assert channel != message


# ─── _canonical_seed (pure) ──────────────────────────────────────────────────

def test_canonical_seed_telegram_infers_url_from_id():
    seed = OM._canonical_seed({"platform": "telegram", "channelId": "mynews"})
    assert "t.me" in seed["channel_url"]
    assert seed["channel_id"] == "mynews"


def test_canonical_seed_telegram_infers_id_from_url():
    seed = OM._canonical_seed({
        "platform": "telegram",
        "channelUrl": "https://t.me/s/mychannel",
    })
    assert seed["channel_id"] == "mychannel"


def test_canonical_seed_line_generates_id_from_url():
    seed = OM._canonical_seed({
        "platform": "line",
        "url": "https://line.me/R/ti/p/some-channel",
    })
    assert seed["channel_id"].startswith("line-")


def test_canonical_seed_normalizes_platform_lowercase():
    seed = OM._canonical_seed({"platform": "Telegram", "channelId": "test"})
    assert seed["platform"] == "telegram"


def test_canonical_seed_strips_at_sign_from_id():
    seed = OM._canonical_seed({"platform": "telegram", "channelId": "@mygroup"})
    assert not seed["channel_id"].startswith("@")
    assert seed["channel_id"] == "mygroup"


def test_canonical_seed_country_uppercased():
    seed = OM._canonical_seed({"platform": "telegram", "channelId": "x", "country": "jp"})
    assert seed["country"] == "JP"


def test_canonical_seed_language_lowercased():
    seed = OM._canonical_seed({"platform": "telegram", "channelId": "x", "language": "JA"})
    assert seed["language"] == "ja"


# ─── _clean (pure) ────────────────────────────────────────────────────────────

def test_clean_collapses_whitespace():
    assert OM._clean("  hello   world  ") == "hello world"


def test_clean_strips_html_tags():
    result = OM._clean("<b>bold</b> text")
    assert "<b>" not in result
    assert "bold" in result


def test_clean_respects_limit():
    result = OM._clean("a" * 2000, limit=100)
    assert len(result) <= 100


def test_clean_handles_empty():
    assert OM._clean("") == ""
    assert OM._clean(None) == ""


# ─── queue_seed_runs (with DB mock) ──────────────────────────────────────────

def test_queue_seed_runs_empty_seeds():
    result = OM.queue_seed_runs(seeds=[], limit=50)
    assert result["queued"] == 0
    assert result["skipped"] == 0


def test_queue_seed_runs_valid_telegram_seed():
    seeds = [{"platform": "telegram", "channelId": "mynewschannel"}]
    result = OM.queue_seed_runs(seeds=seeds, limit=10)
    assert result["queued"] + result["skipped"] >= 1


def test_queue_seed_runs_invalid_platform_skipped():
    seeds = [{"platform": "discord", "channelId": "test"}]
    result = OM.queue_seed_runs(seeds=seeds)
    assert result["skipped"] == 1


def test_queue_seed_runs_non_dict_seed_skipped():
    seeds = ["not-a-dict", 42, None]
    result = OM.queue_seed_runs(seeds=seeds)
    assert result["skipped"] == 3


def test_queue_seed_runs_returns_runs_list():
    seeds = [{"platform": "telegram", "channelId": "mychan"}]
    result = OM.queue_seed_runs(seeds=seeds)
    assert "runs" in result
    assert isinstance(result["runs"], list)


# ─── process_queue (with DB mock) ────────────────────────────────────────────

def test_process_queue_no_queued_runs():
    result = OM.process_queue(max_runs=5)
    assert result["processed"] == 0


# ─── task_queue_seed_runs / task_process_queue (async wrappers) ──────────────

def test_task_queue_seed_runs_async():
    result = asyncio.run(OM.task_queue_seed_runs(seeds=[], limit=10))
    assert result["queued"] == 0


def test_task_process_queue_async():
    result = asyncio.run(OM.task_process_queue(maxRuns=2))
    assert result["processed"] == 0


# ─── register ────────────────────────────────────────────────────────────────

def test_register_exposes_two_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    OM.register(FakeWorker(), timeout_ms=60_000)
    assert set(registered) == {
        "osMessaging.openChannels.queueSeedRuns",
        "osMessaging.openChannels.processQueue",
    }
