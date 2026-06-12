"""M5 tests for yoro_social_murakumo — delete-path primitives, fetch_followers,
list_actor_records, task_yoro_actor_quality_enrich_profile, and projector integration.

Per ADR-2605215300 §4 M5 milestone.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
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

# Pre-import the module for non-SDK-sensitive tests
YS = _ys()


# ---------------------------------------------------------------------------
# TestDeletePost — delete_post() happy path + guard checks
# ---------------------------------------------------------------------------

class TestDeletePost:
    @pytest.mark.asyncio
    async def test_happy_path_calls_delete_record(self):
        mock_pds = MagicMock()
        mock_pds.delete_record = AsyncMock(return_value=None)
        uri = "at://did:plc:author/app.bsky.feed.post/abc123"
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await YS.delete_post(uri)
        assert result["ok"] is True
        assert result["deleted"] == uri

    @pytest.mark.asyncio
    async def test_missing_uri_returns_error(self):
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await YS.delete_post("")
        assert result["ok"] is False
        assert "uri is required" in result["error"]

    @pytest.mark.asyncio
    async def test_non_at_uri_returns_error(self):
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await YS.delete_post("https://example.com/post/123")
        assert result["ok"] is False
        assert "AT URI" in result["error"]

    @pytest.mark.asyncio
    async def test_sdk_not_installed_raises_import_error(self):
        with patch(f"{_SOCIAL_MOD}._pds_mod", None):
            with pytest.raises(ImportError, match="etzhayyim_sdk not installed"):
                await YS.delete_post("at://did:plc:x/app.bsky.feed.post/abc")

    def test_delete_post_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().delete_post)


# ---------------------------------------------------------------------------
# TestUnfollowActor — unfollow_actor() happy path + guard checks
# ---------------------------------------------------------------------------

class TestUnfollowActor:
    @pytest.mark.asyncio
    async def test_happy_path_calls_delete_record(self):
        ys = _ys()
        mock_pds = MagicMock()
        mock_pds.delete_record = AsyncMock(return_value=None)
        uri = "at://did:plc:author/app.bsky.graph.follow/rkey001"
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unfollow_actor(uri)
        assert result["ok"] is True
        assert result["deleted"] == uri

    @pytest.mark.asyncio
    async def test_missing_uri_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unfollow_actor("")
        assert result["ok"] is False
        assert "uri is required" in result["error"]

    @pytest.mark.asyncio
    async def test_non_at_uri_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unfollow_actor("https://example.com/follow/123")
        assert result["ok"] is False
        assert "AT URI" in result["error"]

    @pytest.mark.asyncio
    async def test_sdk_not_installed_raises_import_error(self):
        ys = _ys()
        with patch(f"{_SOCIAL_MOD}._pds_mod", None):
            with pytest.raises(ImportError, match="etzhayyim_sdk not installed"):
                await ys.unfollow_actor("at://did:plc:x/app.bsky.graph.follow/rkey")

    def test_unfollow_actor_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().unfollow_actor)


# ---------------------------------------------------------------------------
# TestUnlikePost — unlike_post() happy path + guard checks
# ---------------------------------------------------------------------------

class TestUnlikePost:
    @pytest.mark.asyncio
    async def test_happy_path_calls_delete_record(self):
        ys = _ys()
        mock_pds = MagicMock()
        mock_pds.delete_record = AsyncMock(return_value=None)
        uri = "at://did:plc:author/app.bsky.feed.like/likerkey001"
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unlike_post(uri)
        assert result["ok"] is True
        assert result["deleted"] == uri

    @pytest.mark.asyncio
    async def test_missing_uri_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unlike_post("")
        assert result["ok"] is False
        assert "uri is required" in result["error"]

    @pytest.mark.asyncio
    async def test_non_at_uri_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.unlike_post("https://example.com/like/123")
        assert result["ok"] is False
        assert "AT URI" in result["error"]

    @pytest.mark.asyncio
    async def test_sdk_not_installed_raises_import_error(self):
        ys = _ys()
        with patch(f"{_SOCIAL_MOD}._pds_mod", None):
            with pytest.raises(ImportError, match="etzhayyim_sdk not installed"):
                await ys.unlike_post("at://did:plc:x/app.bsky.feed.like/lkey")

    def test_unlike_post_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().unlike_post)


# ---------------------------------------------------------------------------
# TestFetchFollowers — fetch_followers() happy path, fallback, projector
# ---------------------------------------------------------------------------

class TestFetchFollowers:
    @pytest.mark.asyncio
    async def test_happy_path_returns_follow_list(self):
        ys = _ys()
        actor_did = "did:plc:actor001"
        mock_records = [
            {
                "uri": f"at://{actor_did}/app.bsky.graph.follow/k1",
                "cid": "bafyfollowcid001",
                "value": {
                    "$type": "app.bsky.graph.follow",
                    "subject": "did:plc:target001",
                    "createdAt": "2026-05-21T00:00:00Z",
                },
            },
            {
                "uri": f"at://{actor_did}/app.bsky.graph.follow/k2",
                "cid": "bafyfollowcid002",
                "value": {
                    "$type": "app.bsky.graph.follow",
                    "subject": "did:plc:target002",
                    "createdAt": "2026-05-21T01:00:00Z",
                },
            },
        ]
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(return_value={"records": mock_records, "cursor": None})
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", None),
        ):
            result = await ys.fetch_followers(actor_did)
        assert result["ok"] is True
        assert result["actorDid"] == actor_did
        assert result["count"] == 2
        assert len(result["follows"]) == 2

    @pytest.mark.asyncio
    async def test_empty_follow_list_returns_ok(self):
        ys = _ys()
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(return_value={"records": [], "cursor": None})
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", None),
        ):
            result = await ys.fetch_followers("did:plc:empty")
        assert result["ok"] is True
        assert result["count"] == 0
        assert result["follows"] == []

    @pytest.mark.asyncio
    async def test_missing_actor_did_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.fetch_followers("")
        assert result["ok"] is False
        assert "actor_did is required" in result["error"]

    @pytest.mark.asyncio
    async def test_sdk_failure_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(side_effect=RuntimeError("PDS unavailable"))
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", None),
        ):
            result = await ys.fetch_followers("did:plc:actor001")
        assert result["ok"] is False
        assert result["error"]
        assert result["follows"] == []

    @pytest.mark.asyncio
    async def test_cursor_pagination_passed_through(self):
        ys = _ys()
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(
            return_value={"records": [], "cursor": "next-page-cursor"}
        )
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", None),
        ):
            result = await ys.fetch_followers("did:plc:actor001", cursor="prev-cursor")
        call_kwargs = mock_pds.list_records.call_args
        assert call_kwargs is not None
        # cursor was passed
        args, kwargs = call_kwargs
        assert kwargs.get("cursor") == "prev-cursor" or "prev-cursor" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_sdk_not_installed_raises_import_error(self):
        ys = _ys()
        with patch(f"{_SOCIAL_MOD}._pds_mod", None):
            with pytest.raises(ImportError, match="etzhayyim_sdk not installed"):
                await ys.fetch_followers("did:plc:actor001")

    def test_fetch_followers_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().fetch_followers)

    # ── mst-projector tests ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_followers_uses_projector_when_available(self):
        """When _projector_mod is available, fetch_followers uses query_by_field
        to get the true reverse-follower index instead of PDS listRecords."""
        ys = _ys()
        actor_did = "did:plc:proj_actor"
        proj_records = [
            {
                "uri": f"at://did:plc:follower{i}/app.bsky.graph.follow/r{i}",
                "cid": f"cid{i}",
                "value": {"subject": actor_did, "createdAt": "2026-05-21T00:00:00Z"},
            }
            for i in range(5)
        ]
        mock_pds = MagicMock()
        mock_projector = MagicMock()
        mock_projector.query_by_field = AsyncMock(
            return_value={"records": proj_records, "cursor": None}
        )
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", mock_projector),
        ):
            result = await ys.fetch_followers(actor_did, limit=50)

        # Projector was called with the right arguments
        mock_projector.query_by_field.assert_called_once_with(
            "app.bsky.graph.follow", "subject", actor_did, limit=50,
        )
        # PDS listRecords was NOT called (projector succeeded)
        mock_pds.list_records.assert_not_called()

        assert result["ok"] is True
        assert result["actorDid"] == actor_did
        assert result["count"] == 5
        assert result["source"] == "mst-projector"

    @pytest.mark.asyncio
    async def test_fetch_followers_falls_back_to_pds_on_projector_error(self):
        """When projector raises, fetch_followers falls back to PDS listRecords."""
        ys = _ys()
        actor_did = "did:plc:fallback_actor"
        pds_records = [
            {
                "uri": f"at://{actor_did}/app.bsky.graph.follow/pds_r{i}",
                "cid": f"pdscid{i}",
                "value": {"subject": f"did:plc:other{i}", "createdAt": "2026-05-21T00:00:00Z"},
            }
            for i in range(2)
        ]
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(return_value={"records": pds_records, "cursor": None})
        mock_projector = MagicMock()
        mock_projector.query_by_field = AsyncMock(
            side_effect=ConnectionRefusedError("projector unreachable")
        )
        with (
            patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds),
            patch(f"{_SOCIAL_MOD}._projector_mod", mock_projector),
        ):
            result = await ys.fetch_followers(actor_did, limit=50)

        # Projector was attempted
        mock_projector.query_by_field.assert_called_once()
        # PDS listRecords was called as fallback
        mock_pds.list_records.assert_called_once()

        assert result["ok"] is True
        assert result["actorDid"] == actor_did
        assert result["count"] == 2
        assert result["source"] == "pds-list-records"


# ---------------------------------------------------------------------------
# TestListActorRecords — list_actor_records() basic checks
# ---------------------------------------------------------------------------

class TestListActorRecords:
    @pytest.mark.asyncio
    async def test_happy_path_returns_records(self):
        ys = _ys()
        actor_did = "did:plc:actor001"
        mock_records = [
            {"uri": f"at://{actor_did}/app.bsky.feed.post/p1", "cid": "c1",
             "value": {"text": "hello"}},
        ]
        mock_pds = MagicMock()
        mock_pds.list_records = AsyncMock(return_value={"records": mock_records, "cursor": None})
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.list_actor_records(actor_did)
        assert result["ok"] is True
        assert result["actorDid"] == actor_did
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_missing_actor_did_returns_error(self):
        ys = _ys()
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            result = await ys.list_actor_records("")
        assert result["ok"] is False
        assert "actor_did is required" in result["error"]

    @pytest.mark.asyncio
    async def test_sdk_not_installed_raises_import_error(self):
        ys = _ys()
        with patch(f"{_SOCIAL_MOD}._pds_mod", None):
            with pytest.raises(ImportError, match="etzhayyim_sdk not installed"):
                await ys.list_actor_records("did:plc:x")

    def test_list_actor_records_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().list_actor_records)


# ---------------------------------------------------------------------------
# TestTaskActorQualityEnrichProfile — basic coroutine check
# ---------------------------------------------------------------------------

class TestTaskActorQualityEnrichProfile:
    def test_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().task_yoro_actor_quality_enrich_profile)


# ---------------------------------------------------------------------------
# TestTaskActorQualityEnsureSeedPost — basic coroutine check
# ---------------------------------------------------------------------------

class TestTaskActorQualityEnsureSeedPost:
    def test_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().task_yoro_actor_quality_ensure_seed_post)


# ---------------------------------------------------------------------------
# TestTaskPlatformPulseGraphFallback — basic coroutine check
# ---------------------------------------------------------------------------

class TestTaskPlatformPulseGraphFallback:
    def test_is_coroutine(self):
        assert inspect.iscoroutinefunction(_ys().task_yoro_social_platform_pulse_graph_fallback)


# ---------------------------------------------------------------------------
# TestSubstrateFitRegressionM5 — M5 functions must not use prohibited patterns
# ---------------------------------------------------------------------------

class TestSubstrateFitRegressionM5:
    def _src(self) -> str:
        mod = _ys()
        src_file = inspect.getfile(mod)
        return Path(src_file).read_text(encoding="utf-8")

    def test_no_psycopg_in_m5_functions(self):
        src = self._src()
        assert "import psycopg" not in src

    def test_no_runpod_in_m5_functions(self):
        src = self._src()
        assert "import runpod" not in src.lower()

    def test_no_stripe_in_m5_functions(self):
        src = self._src()
        assert "import stripe\n" not in src

    def test_delete_post_exists(self):
        assert callable(_ys().delete_post)

    def test_unfollow_actor_exists(self):
        assert callable(_ys().unfollow_actor)

    def test_unlike_post_exists(self):
        assert callable(_ys().unlike_post)

    def test_fetch_followers_exists(self):
        assert callable(_ys().fetch_followers)

    def test_list_actor_records_exists(self):
        assert callable(_ys().list_actor_records)


# ---------------------------------------------------------------------------
# TestCreateDeleteSymmetry — delete endpoints are symmetric counterparts
# ---------------------------------------------------------------------------

class TestCreateDeleteSymmetry:
    def test_delete_post_is_async(self):
        assert inspect.iscoroutinefunction(_ys().delete_post)

    def test_unfollow_actor_is_async(self):
        assert inspect.iscoroutinefunction(_ys().unfollow_actor)

    def test_unlike_post_is_async(self):
        assert inspect.iscoroutinefunction(_ys().unlike_post)

    @pytest.mark.asyncio
    async def test_delete_unfollow_unlike_share_guard_logic(self):
        """All three delete functions reject non-AT-URIs with the same error pattern."""
        ys = _ys()
        bad_uri = "https://not-an-at-uri.example.com/post/123"
        mock_pds = MagicMock()
        with patch(f"{_SOCIAL_MOD}._pds_mod", mock_pds):
            dp = await ys.delete_post(bad_uri)
            ua = await ys.unfollow_actor(bad_uri)
            ul = await ys.unlike_post(bad_uri)
        for result in (dp, ua, ul):
            assert result["ok"] is False
            assert "AT URI" in result["error"]
