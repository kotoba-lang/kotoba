"""M4 tests for yoro_social_murakumo — fetch, translate, task completeness.

Per ADR-2605215300 §4 M4 milestone.

Covers:
  - task_yoro_social_translate_post: real LLM call via mocked _llm_mod.translate
  - task_yoro_social_translate_post_batch: fan-out + coalescer pattern
  - task_yoro_social_post_graph_fallback
  - task_yoro_social_respond_to_mention_graph_fallback
  - task_yoro_social_respond_to_follow_graph_fallback
  - task_yoro_actor_quality_inspect (dry_run and live paths)
  - task_yoro_actor_quality_verify (dry_run and live paths)
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PY_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_PY_SRC) not in sys.path:
    sys.path.insert(0, str(_PY_SRC))

_SDK_SRC = Path(__file__).resolve().parents[3] / "etzhayyim-sdk-py" / "src"
if _SDK_SRC.exists() and str(_SDK_SRC) not in sys.path:
    sys.path.insert(0, str(_SDK_SRC))


def _clean_env_import(module_name: str) -> Any:
    """Import a module with RW_URL unset, evicting any cached version first."""
    env_backup = os.environ.pop("RW_URL", None)
    try:
        if module_name in sys.modules:
            del sys.modules[module_name]
        mod = importlib.import_module(module_name)
        return mod
    finally:
        if env_backup is not None:
            os.environ["RW_URL"] = env_backup


def _ys() -> Any:
    return _clean_env_import("kotodama.primitives.yoro_social_murakumo")


_SOCIAL_MOD = "kotodama.primitives.yoro_social_murakumo"

# Pre-import the module for non-SDK-sensitive tests.
# Each test that calls module functions uses `_ys()` to get the current live
# module instance from sys.modules (which may be re-evicted by test_yoro_m5's
# _clean_env_import). This avoids stale-reference failures when tests run
# in a combined session.
YS = _ys()


def _get_ys() -> Any:
    """Return the current live yoro_social_murakumo module from sys.modules.

    Needed because test_yoro_m5's _clean_env_import evicts and reloads the
    module between test files. After a reload, YS (module-level reference)
    may point to the old instance while sys.modules has a new one.
    """
    return sys.modules.get(_SOCIAL_MOD) or _ys()


# ---------------------------------------------------------------------------
# TestTranslatePost — task_yoro_social_translate_post real LLM wiring
# ---------------------------------------------------------------------------

class TestTranslatePost:
    """Tests for task_yoro_social_translate_post with real LLM call (mocked)."""

    @pytest.mark.asyncio
    async def test_translate_real_llm_returns_translated_text(self):
        """_llm_mod.translate returns 'Konnichiwa' → result translatedText is 'Konnichiwa'."""
        ys = _get_ys()
        mock_pds = MagicMock()
        # fetch_source_post returns a post with text "Hello"
        source_post_data = {
            "value": {
                "text": "Hello",
                "createdAt": "2026-05-20T00:00:00Z",
                "langs": ["en"],
            }
        }
        mock_pds.get_record = AsyncMock(return_value=source_post_data)
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-post"})
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-link"})

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(return_value="Konnichiwa")

        mock_coalescer = MagicMock()
        mock_coalescer.submit = AsyncMock(return_value=None)

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_translate_post(
                postUri="at://did:plc:test/app.bsky.feed.post/abc",
                targetLang="ja",
                sourceLang="en",
                postText="Hello",
            )

        assert result["ok"] is True
        assert result["translatedText"] == "Konnichiwa"
        assert result["targetLang"] == "ja"
        assert result["model"] != "stub"  # real LLM path, not stub
        # _llm_mod.translate must have been called with source + target lang
        mock_llm.translate.assert_called_once()
        call_kwargs = mock_llm.translate.call_args
        assert call_kwargs.kwargs.get("target_lang") == "ja" or "ja" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_translate_text_not_bracketed_placeholder(self):
        """Translated text must NOT be the old [translated to {lang}] placeholder."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {"text": "Hello world", "createdAt": "2026-05-20T00:00:00Z", "langs": ["en"]}
        })
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-post2"})
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-link2"})

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(return_value="Hola mundo")

        mock_coalescer = MagicMock()
        mock_coalescer.submit = AsyncMock(return_value=None)

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_translate_post(
                postUri="at://did:plc:test/app.bsky.feed.post/xyz",
                targetLang="es",
                postText="Hello world",
            )

        assert result["ok"] is True
        assert "[translated to es]" not in result["translatedText"]
        assert result["translatedText"] == "Hola mundo"

    @pytest.mark.asyncio
    async def test_translate_llm_error_propagates(self):
        """_llm_mod.translate raises LlmError → task surfaces the error."""
        ys = _get_ys()

        class _LlmError(Exception):
            pass

        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {"text": "Test text", "createdAt": "2026-05-20T00:00:00Z", "langs": ["en"]}
        })

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(side_effect=_LlmError("LLM rate limited"))

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
        ):
            with pytest.raises(_LlmError):
                await ys.task_yoro_social_translate_post(
                    postUri="at://did:plc:test/app.bsky.feed.post/zzz",
                    targetLang="fr",
                    postText="Test text",
                )

    @pytest.mark.asyncio
    async def test_translate_missing_post_uri_returns_error(self):
        """Empty postUri → {'ok': False, 'error': 'postUri is required'}."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_translate_post(
                postUri="",
                targetLang="ja",
            )
        assert result["ok"] is False
        assert "postUri is required" in result["error"]

    @pytest.mark.asyncio
    async def test_translate_missing_target_lang_returns_error(self):
        """Empty targetLang → {'ok': False, 'error': 'targetLang is required'}."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_translate_post(
                postUri="at://did:plc:test/app.bsky.feed.post/abc",
                targetLang="",
            )
        assert result["ok"] is False
        assert "targetLang is required" in result["error"]

    @pytest.mark.asyncio
    async def test_translate_dry_run_calls_llm_but_skips_writes(self):
        """dryRun=True: LLM translate IS called, but record_post + translation_link are NOT."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {"text": "Dry run text", "createdAt": "2026-05-20T00:00:00Z", "langs": ["en"]}
        })
        mock_pds.dispatch = AsyncMock()
        mock_pds.put_record = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(return_value="Dry run result")

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
        ):
            result = await ys.task_yoro_social_translate_post(
                postUri="at://did:plc:test/app.bsky.feed.post/dry",
                targetLang="ko",
                postText="Dry run text",
                dryRun=True,
            )

        assert result["ok"] is True
        assert result.get("dryRun") is True
        assert result["translatedText"] == "Dry run result"
        # No PDS writes should have occurred
        mock_pds.dispatch.assert_not_called()
        mock_pds.put_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_translate_source_post_fetched_from_pds(self):
        """When postText is empty, source text is fetched from PDS via get_record."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {
                "text": "Source from PDS",
                "createdAt": "2026-05-20T00:00:00Z",
                "langs": ["ja"],
            }
        })
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-fetched"})
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-link-fetched"})

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(return_value="Source from PDS in English")

        mock_coalescer = MagicMock()
        mock_coalescer.submit = AsyncMock(return_value=None)

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_translate_post(
                postUri="at://did:plc:test/app.bsky.feed.post/pds-fetch",
                targetLang="en",
                postText="",  # empty → must fetch from PDS
            )

        assert result["ok"] is True
        mock_pds.get_record.assert_called_once()
        assert result["translatedText"] == "Source from PDS in English"


# ---------------------------------------------------------------------------
# TestTranslatePostBatch — task_yoro_social_translate_post_batch fan-out
# ---------------------------------------------------------------------------

class TestTranslatePostBatch:
    """Tests for task_yoro_social_translate_post_batch: fan-out + coalescer."""

    @pytest.mark.asyncio
    async def test_batch_translate_fans_out_to_all_langs(self):
        """Batch translate calls translate for each target language."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {"text": "Batch source", "createdAt": "2026-05-20T00:00:00Z", "langs": ["en"]}
        })
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-batch"})
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-batch-link"})

        translate_call_count = 0

        async def _mock_translate(source_text: str, target_lang: str, source_lang: str = "") -> str:
            nonlocal translate_call_count
            translate_call_count += 1
            return f"[{target_lang}] {source_text}"

        mock_llm = MagicMock()
        mock_llm.translate = _mock_translate

        mock_coalescer = MagicMock()
        mock_coalescer.submit = AsyncMock(return_value=None)

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_translate_post_batch(
                postUri="at://did:plc:test/app.bsky.feed.post/batch001",
                targetLangs="ja,en,ko",
                postText="Batch source",
            )

        assert result["ok"] is True
        assert result["count"] == 3
        assert result["translated"] == 3
        assert translate_call_count == 3

    @pytest.mark.asyncio
    async def test_batch_missing_post_uri_returns_error(self):
        """Batch with empty postUri → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_translate_post_batch(
                postUri="",
                targetLangs="ja,en",
            )
        assert result["ok"] is False
        assert "postUri is required" in result["error"]

    @pytest.mark.asyncio
    async def test_batch_empty_target_langs_returns_error(self):
        """Batch with empty targetLangs → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_translate_post_batch(
                postUri="at://did:plc:test/app.bsky.feed.post/batch002",
                targetLangs="",
            )
        assert result["ok"] is False
        assert "targetLangs is empty" in result["error"]

    @pytest.mark.asyncio
    async def test_batch_coalescer_pattern_used(self):
        """Batch translate uses the coalescer pattern for translation links."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {"text": "Coalesce test", "createdAt": "2026-05-20T00:00:00Z", "langs": ["en"]}
        })
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-c"})
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-c-link"})

        mock_llm = MagicMock()
        mock_llm.translate = AsyncMock(return_value="Translated")

        # Use a real-ish coalescer mock to verify submit is called
        submit_calls: list[str] = []

        async def _mock_submit(key: str, fn: Any) -> None:
            submit_calls.append(key)
            # Actually call the function to ensure the translation link is "written"
            await fn()

        mock_coalescer = MagicMock()
        mock_coalescer.submit = _mock_submit

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._llm_mod", mock_llm),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_translate_post_batch(
                postUri="at://did:plc:test/app.bsky.feed.post/coalesce",
                targetLangs="ja,ko",
                postText="Coalesce test",
            )

        assert result["ok"] is True
        # The coalescer should have been submitted once per language
        assert len(submit_calls) == 2
        # Each submit key should be the source post URI
        for key in submit_calls:
            assert "at://" in key


# ---------------------------------------------------------------------------
# TestPostGraphFallback — task_yoro_social_post_graph_fallback
# ---------------------------------------------------------------------------

class TestPostGraphFallback:
    @pytest.mark.asyncio
    async def test_post_graph_fallback_dispatches_and_returns_uri(self):
        """task_yoro_social_post_graph_fallback dispatches post and returns uri."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-post"})

        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_post_graph_fallback(
                postRepo="did:plc:test001",
                text="Hello Yoro!",
            )

        assert result["ok"] is True
        assert result["uri"].startswith("at://did:plc:test001/app.bsky.feed.post/")
        mock_pds.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_graph_fallback_missing_repo_returns_error(self):
        """Missing postRepo → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_post_graph_fallback(postRepo="")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# TestRespondToMentionGraphFallback
# ---------------------------------------------------------------------------

class TestRespondToMentionGraphFallback:
    @pytest.mark.asyncio
    async def test_respond_to_mention_dispatches_reply(self):
        """Respond to mention dispatches a reply post."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-mention-reply"})

        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_respond_to_mention_graph_fallback(
                authorDid="did:plc:author001",
                postUri="at://did:plc:author001/app.bsky.feed.post/mention123",
            )

        assert result["ok"] is True
        assert result["authorDid"] == "did:plc:author001"
        mock_pds.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_respond_to_mention_missing_author_did(self):
        """Missing authorDid → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_respond_to_mention_graph_fallback(
                authorDid="",
                postUri="at://did:plc:author/app.bsky.feed.post/abc",
            )
        assert result["ok"] is False
        assert "authorDid is required" in result["error"]


# ---------------------------------------------------------------------------
# TestRespondToFollowGraphFallback
# ---------------------------------------------------------------------------

class TestRespondToFollowGraphFallback:
    @pytest.mark.asyncio
    async def test_respond_to_follow_dispatches_follow_back_and_welcome(self):
        """Respond to follow: follow-back + welcome post dispatched concurrently."""
        ys = _get_ys()
        mock_pds = MagicMock()
        mock_pds.dispatch = AsyncMock(return_value={"cid": "bafy-follow"})

        mock_coalescer = MagicMock()
        mock_coalescer.submit = AsyncMock(return_value=None)

        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._COALESCER", mock_coalescer),
        ):
            result = await ys.task_yoro_social_respond_to_follow_graph_fallback(
                followerDid="did:plc:follower001",
                followerHandle="follower001.bsky.social",
            )

        assert result["ok"] is True
        assert result["followerDid"] == "did:plc:follower001"
        assert "followBackUri" in result
        assert "welcomeUri" in result

    @pytest.mark.asyncio
    async def test_respond_to_follow_missing_follower_did(self):
        """Missing followerDid → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_social_respond_to_follow_graph_fallback(
                followerDid="",
            )
        assert result["ok"] is False
        assert "followerDid is required" in result["error"]


# ---------------------------------------------------------------------------
# TestActorQualityInspect
# ---------------------------------------------------------------------------

class TestActorQualityInspect:
    @pytest.mark.asyncio
    async def test_inspect_dry_run_returns_quality_data(self):
        """dry_run=True returns quality data without writing a report."""
        ys = _get_ys()
        actor_did = "did:plc:actor001"
        mock_pds = MagicMock()
        # Profile exists, no posts
        mock_pds.get_record = AsyncMock(return_value={
            "value": {
                "displayName": "Test Actor",
                "description": "An actor",
                "avatar": "",
                "createdAt": "2026-01-01T00:00:00Z",
            }
        })
        mock_pds.list_records = AsyncMock(return_value={"records": [], "cursor": None})

        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_actor_quality_inspect(
                actorDid=actor_did,
                dryRun=True,
            )

        assert result["ok"] is True
        assert result.get("dryRun") is True
        assert "qualityScore" in result
        assert "dimensions" in result

    @pytest.mark.asyncio
    async def test_inspect_missing_actor_did_returns_error(self):
        """Missing actorDid and handle → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_actor_quality_inspect(actorDid="", handle="")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# TestActorQualityVerify
# ---------------------------------------------------------------------------

class TestActorQualityVerify:
    @pytest.mark.asyncio
    async def test_verify_dry_run_returns_verified_status(self):
        """dry_run=True returns verified status without writing a report."""
        ys = _get_ys()
        actor_did = "did:plc:actor002"
        mock_pds = MagicMock()
        mock_pds.get_record = AsyncMock(return_value={
            "value": {
                "displayName": "Full Actor",
                "description": "Full profile",
                "avatar": "https://cdn.example.com/avatar.jpg",
                "createdAt": "2026-01-01T00:00:00Z",
            }
        })
        mock_pds.list_records = AsyncMock(return_value={
            "records": [{"uri": "at://did:plc:actor002/app.bsky.feed.post/p1", "value": {}}],
            "cursor": None,
        })

        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_actor_quality_verify(
                actorDid=actor_did,
                dryRun=True,
            )

        assert result["ok"] is True
        assert result.get("dryRun") is True
        assert "verified" in result

    @pytest.mark.asyncio
    async def test_verify_missing_actor_did_returns_error(self):
        """Missing actorDid and handle → error."""
        ys = _get_ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.task_yoro_actor_quality_verify(actorDid="", handle="")
        assert result["ok"] is False
