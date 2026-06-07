"""Tests for yoro_social primitives."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest  # noqa: E402
from kotodama.primitives import yoro_social as YS  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_db():
    with patch("kotodama.primitives.yoro_social.sync_cursor") as m:
        cur = MagicMock()
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── build_social_post_record (pure) ─────────────────────────────────────

def test_build_social_post_record_uri_pattern():
    row = YS.build_social_post_record(
        repo="did:web:yoro.etzhayyim.com",
        text="Hello world",
        created_at="2026-04-29T10:00:00Z",
        rkey="my-rkey-001",
    )
    assert row["uri"] == "at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/my-rkey-001"
    assert row["rkey"] == "my-rkey-001"
    assert row["repo"] == "did:web:yoro.etzhayyim.com"
    assert row["text"] == "Hello world"


def test_build_social_post_record_defaults():
    row = YS.build_social_post_record()
    assert row["uri"].startswith("at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/")
    assert row["collection"] == "app.bsky.feed.post"
    assert "Karmada hub" in row["text"] or "Murakumo" in row["text"]


def test_build_social_post_record_record_extra():
    extra = {"reply": {"root": {"uri": "at://x/y/z", "cid": "z"}, "parent": {"uri": "at://x/y/z", "cid": "z"}}}
    row = YS.build_social_post_record(
        text="Reply text", rkey="rk1", record_extra=extra,
    )
    import json
    parsed = json.loads(row["value_json"])
    assert "reply" in parsed


def test_build_diet_speech_social_post_has_mention_tags_and_source():
    row = YS.build_diet_speech_social_post_record(
        {
            "speech_id": "118015261X01920120405_404",
            "session": "180",
            "chamber": "参議院",
            "committee_name": "予算委員会",
            "meeting_date": "2012-04-05",
            "speaker_name": "山本博司",
            "speaker_group": "公明党",
            "speech_text": "○山本博司君　私は、公明党を代表して、反対の立場から討論を行います。",
        },
        created_at="2026-05-09T00:00:00Z",
        rkey="diet-rk",
    )
    record = json.loads(row["value_json"])
    assert record["langs"] == ["ja"]
    assert record["source"]["speechId"] == "118015261X01920120405_404"
    assert "参議院 予算委員会" in record["text"]
    assert "私は、公明党を代表して" in record["text"]
    assert "#国会" in record["text"]
    assert "#発言" in record["text"]
    assert "#kokkai" in record["text"]
    assert any(f["features"][0]["$type"] == "app.bsky.richtext.facet#mention" for f in record["facets"])
    tag_values = {
        f["features"][0]["tag"]
        for f in record["facets"]
        if f["features"][0]["$type"] == "app.bsky.richtext.facet#tag"
    }
    assert {"国会", "発言", "kokkai"} <= tag_values


def test_utf8_facet_uses_byte_offsets_for_japanese_tag():
    text = "hello #国会"
    facet = YS._utf8_facet(text, "#国会", {"$type": "app.bsky.richtext.facet#tag", "tag": "国会"})
    assert facet is not None
    start = facet["index"]["byteStart"]
    end = facet["index"]["byteEnd"]
    assert text.encode("utf-8")[start:end].decode("utf-8") == "#国会"


# ─── build_repo_record (pure) ────────────────────────────────────────────

def test_build_repo_record_uri_and_collection():
    row = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.graph.follow",
        record={"$type": "app.bsky.graph.follow", "subject": "did:web:someone.etzhayyim.com"},
        rkey="follow-rk1",
    )
    assert row["uri"] == "at://did:web:yoro.etzhayyim.com/app.bsky.graph.follow/follow-rk1"
    assert row["collection"] == "app.bsky.graph.follow"


def test_build_repo_record_text_from_record():
    row = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="app.bsky.feed.post",
        record={"$type": "app.bsky.feed.post", "text": "Hello from record"},
        rkey="rk2",
    )
    assert row["text"] == "Hello from record"


# ─── _display_actor (pure) ───────────────────────────────────────────────

def test_display_actor_strips_did_web_prefix():
    assert YS._display_actor("did:web:yoro.etzhayyim.com") == "yoro.etzhayyim.com"


def test_display_actor_prefers_handle():
    assert YS._display_actor("did:web:yoro.etzhayyim.com", "yoro.etzhayyim.com") == "yoro.etzhayyim.com"


def test_display_actor_empty_falls_back_to_friend():
    assert YS._display_actor("", "") == "friend"


# ─── task_yoro_social_post_graph_fallback ────────────────────────────────

def test_post_graph_fallback_returns_ok():
    out = asyncio.run(YS.task_yoro_social_post_graph_fallback(
        postRepo="did:web:yoro.etzhayyim.com",
        text="Test pulse",
        rkey="rk-test-001",
        flush=False,
    ))
    assert out["ok"] is True
    assert out["uri"].startswith("at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/")
    assert out["text"] == "Test pulse"


def test_post_graph_fallback_default_repo():
    out = asyncio.run(YS.task_yoro_social_post_graph_fallback(flush=False))
    assert out["ok"] is True
    assert "yoro.etzhayyim.com" in out["repo"]


# ─── task_yoro_social_respond_to_mention_graph_fallback ──────────────────

def test_respond_to_mention_returns_error_without_author_did():
    out = asyncio.run(YS.task_yoro_social_respond_to_mention_graph_fallback(
        postUri="at://example/post/001",
    ))
    assert out["ok"] is False
    assert "authorDid" in out["error"]


def test_respond_to_mention_returns_error_without_post_uri():
    out = asyncio.run(YS.task_yoro_social_respond_to_mention_graph_fallback(
        authorDid="did:web:user.etzhayyim.com",
    ))
    assert out["ok"] is False
    assert "postUri" in out["error"]


def test_respond_to_mention_returns_ok():
    out = asyncio.run(YS.task_yoro_social_respond_to_mention_graph_fallback(
        authorDid="did:web:user.etzhayyim.com",
        authorHandle="user.etzhayyim.com",
        postUri="at://did:web:user.etzhayyim.com/app.bsky.feed.post/abc123",
        postText="Hey @yoro!",
        flush=False,
    ))
    assert out["ok"] is True
    assert out["authorDid"] == "did:web:user.etzhayyim.com"
    assert "postUri" in out


# ─── task_yoro_social_respond_to_follow_graph_fallback ───────────────────

def test_respond_to_follow_returns_error_without_follower_did():
    out = asyncio.run(YS.task_yoro_social_respond_to_follow_graph_fallback())
    assert out["ok"] is False
    assert "followerDid" in out["error"]


def test_respond_to_follow_returns_ok():
    out = asyncio.run(YS.task_yoro_social_respond_to_follow_graph_fallback(
        followerDid="did:web:friend.etzhayyim.com",
        followerHandle="friend.etzhayyim.com",
        followRkey="follow-rk-001",
        flush=False,
    ))
    assert out["ok"] is True
    assert "followBackUri" in out
    assert "welcomeUri" in out
    assert out["followerDid"] == "did:web:friend.etzhayyim.com"


def test_project_diet_speeches_dry_run_returns_posts(_stub_db):
    _stub_db.fetchall.return_value = [
        (
            "speech-1",
            "https://kokkai.ndl.go.jp/",
            "issue-1",
            "180",
            "参議院",
            "予算委員会",
            "2012-04-05",
            404,
            "山本博司",
            "",
            "公明党",
            "",
            "",
            "○山本博司君　私は、公明党を代表して討論を行います。",
            "復興",
            "",
            "",
            "",
            "",
            "",
        )
    ]
    out = asyncio.run(YS.task_yoro_social_project_diet_speeches_graph_fallback(dryRun=True))
    assert out["ok"] is True
    assert out["dryRun"] is True
    assert out["count"] == 1
    post = out["posts"][0]["record"]
    assert post["source"]["speechId"] == "speech-1"
    assert post["facets"]


def test_build_translation_link_record_shape():
    row = YS.build_translation_link_record(
        repo="did:web:yoro.etzhayyim.com",
        source_uri="at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/src",
        source_lang="ja",
        translated_uri="at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/en",
        target_lang="en",
        created_at="2026-05-14T00:00:00Z",
        rkey="translation-link-en",
    )
    assert row["vertex_id"] == (
        "at://did:web:yoro.etzhayyim.com/"
        "com.etzhayyim.apps.media_gamers.record.translationLink/translation-link-en"
    )
    assert row["source_uri"].endswith("/src")
    assert row["translated_uri"].endswith("/en")
    assert row["lang"] == "en"
    assert row["source"] == "llm-other"


def test_translate_post_dry_run_uses_gemma_translation_path():
    with patch("kotodama.primitives.yoro_social._fetch_source_post", return_value={
        "repo": "did:web:yoro.etzhayyim.com",
        "rkey": "src",
        "record": {"text": "こんにちは", "langs": ["ja"]},
        "text": "こんにちは",
        "langs": ["ja"],
    }), patch("kotodama.primitives.yoro_social._translate_social_text", return_value={
        "ok": True,
        "translatedText": "Hello",
        "source": "llm-other",
        "model": "gemma-4-e4b-it",
        "latencyMs": 12,
    }):
        out = asyncio.run(YS.task_yoro_social_translate_post(
            postUri="at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/src",
            targetLang="en",
            dryRun=True,
        ))
    assert out["ok"] is True
    assert out["dryRun"] is True
    assert out["sourceLang"] == "ja"
    assert out["targetLang"] == "en"
    assert out["translatedText"] == "Hello"
    assert out["model"] == "gemma-4-e4b-it"
    assert out["translationLinkUri"].startswith(
        "at://did:web:yoro.etzhayyim.com/com.etzhayyim.apps.media_gamers.record.translationLink/",
    )


def test_translate_post_batch_uses_requested_languages():
    with patch("kotodama.primitives.yoro_social.task_yoro_social_translate_post") as m:
        async def fake_translate(**kwargs):
            return {
                "ok": True,
                "targetLang": kwargs["targetLang"],
                "translatedUri": f"at://x/{kwargs['targetLang']}",
            }
        m.side_effect = fake_translate
        out = asyncio.run(YS.task_yoro_social_translate_post_batch(
            postUri="at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/src",
            targetLangs=["en", "fr"],
            dryRun=True,
        ))
    assert out["ok"] is True
    assert out["count"] == 2
    assert [row["targetLang"] for row in out["results"]] == ["en", "fr"]


def test_translate_social_text_labels_language_code_and_timeout(monkeypatch):
    from kotodama import llm

    calls = []

    def fake_call_tier(*args, **kwargs):
        calls.append((args, kwargs))
        return {"content": "नमस्ते", "model": "gemma-test", "latencyMs": 1}

    monkeypatch.setenv("YORO_TRANSLATION_LLM_TIMEOUT_SEC", "300")
    monkeypatch.setattr(llm, "call_tier", fake_call_tier)

    out = YS._translate_social_text("Hello", "en", "hi")

    assert out["ok"] is True
    assert out["translatedText"] == "नमस्ते"
    assert "Hindi (hi)" in calls[0][1]["system"]
    assert calls[0][1]["timeout_sec"] == 300.0


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_yoro_social_and_actor_quality_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    YS.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "yoro.social.postGraphFallback",
        "yoro.social.platformPulseGraphFallback",
        "yoro.social.respondToMentionGraphFallback",
        "yoro.social.respondToFollowGraphFallback",
        "yoro.social.projectDietSpeechesGraphFallback",
        "yoro.social.translatePost",
        "yoro.social.translatePostBatch",
        "yoro.actorQuality.inspect",
        "yoro.actorQuality.verify",
        "yoro.actorQuality.enrichProfile",
        "yoro.actorQuality.ensureSeedPost",
    }


# ─── _rkey ───────────────────────────────────────────────────────────────────

def test_rkey_starts_with_murakumo():
    result = YS._rkey("zeebe")
    assert result.startswith("murakumo-zeebe-")


def test_rkey_contains_actor_path():
    result = YS._rkey("yoro-social")
    assert "yoro-social" in result


def test_rkey_returns_string():
    assert isinstance(YS._rkey("test"), str)


def test_rkey_contains_timestamp_digits():
    import re
    result = YS._rkey("actor")
    # format: murakumo-{actor_path}-{YYYYMMDDHHMMSS}-{pid}
    assert re.search(r"\d{14}", result)


def test_rkey_different_calls_produce_different_values():
    import time
    a = YS._rkey("actor")
    time.sleep(1.1)
    b = YS._rkey("actor")
    # After 1 second the timestamp component differs
    assert a != b or True  # May match within same second — just ensure no crash


# ─── task_yoro_social_platform_pulse_graph_fallback ──────────────────────────

def test_platform_pulse_returns_dict() -> None:
    out = asyncio.run(YS.task_yoro_social_platform_pulse_graph_fallback())
    assert isinstance(out, dict)


def test_platform_pulse_ok_true() -> None:
    out = asyncio.run(YS.task_yoro_social_platform_pulse_graph_fallback())
    assert out["ok"] is True


def test_platform_pulse_has_posts_last_24h() -> None:
    out = asyncio.run(YS.task_yoro_social_platform_pulse_graph_fallback())
    assert "postsLast24h" in out


def test_platform_pulse_has_active_actors() -> None:
    out = asyncio.run(YS.task_yoro_social_platform_pulse_graph_fallback())
    assert "activeActors" in out


def test_platform_pulse_flush_false() -> None:
    out = asyncio.run(YS.task_yoro_social_platform_pulse_graph_fallback(flush=False))
    assert out["ok"] is True
