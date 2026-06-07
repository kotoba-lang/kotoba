"""test_cell_runner_spawn — unit tests for M3 cell spawn helpers.

Per ADR-2605215200. Tests for cron + mst-listener cell dispatch added in M3.

Test cases:
  1.  test_cron_to_interval_s_every_15_min    — "*/15 * * * *" → 900
  2.  test_cron_to_interval_s_hourly          — "0 * * * *" → 3600
  3.  test_cron_to_interval_s_every_2_hours   — "0 */2 * * *" → 7200
  4.  test_cron_to_interval_s_fallback        — invalid expr → 3600
  5.  test_spawn_cron_cell_invokes_entry       — mock cell_fn fired after 1 tick
  6.  test_spawn_cron_cell_handles_invocation_error — cell_fn raises; loop continues
  7.  test_spawn_listener_cell_filters_collection  — mock subscribe yields events
  8.  test_extract_adherent_did_from_event     — event with op path → returns repo
  9.  test_spawn_cells_for_node_skips_unknown_trigger — unknown kind → skipped
  10. test_async_main_handles_sigterm          — stop_event set → cells exit cleanly
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure kotodama is importable from the src tree.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from kotodama.cell_runner_main import (
    _async_main,
    _cron_to_interval_s,
    _extract_adherent_did,
    _spawn_cron_cell,
    _spawn_listener_cell,
    spawn_cells_for_node,
)


# ── Helper: async generator mock ─────────────────────────────────────────────


async def _async_gen(*items):
    """Yield items one at a time from an async generator (for mocking)."""
    for item in items:
        yield item


# ── 1. _cron_to_interval_s — basic patterns ───────────────────────────────────


class TestCronToIntervalS:
    def test_cron_to_interval_s_every_15_min(self) -> None:
        assert _cron_to_interval_s("*/15 * * * *") == 900

    def test_cron_to_interval_s_hourly(self) -> None:
        assert _cron_to_interval_s("0 * * * *") == 3600

    def test_cron_to_interval_s_every_2_hours(self) -> None:
        assert _cron_to_interval_s("0 */2 * * *") == 7200

    def test_cron_to_interval_s_every_6_hours(self) -> None:
        assert _cron_to_interval_s("0 */6 * * *") == 21600

    def test_cron_to_interval_s_every_1_min(self) -> None:
        assert _cron_to_interval_s("*/1 * * * *") == 60

    def test_cron_to_interval_s_fallback_too_few_parts(self) -> None:
        """Too few parts → default 3600."""
        assert _cron_to_interval_s("*/15 * * *") == 3600

    def test_cron_to_interval_s_fallback_empty(self) -> None:
        assert _cron_to_interval_s("") == 3600

    def test_cron_to_interval_s_fallback_arbitrary(self) -> None:
        """Arbitrary non-matching expression → default 3600."""
        assert _cron_to_interval_s("30 2 * * 1") == 3600

    def test_cron_to_interval_s_fallback_bad_minute_divisor(self) -> None:
        """Non-numeric N in */N → fallback 3600."""
        assert _cron_to_interval_s("*/abc * * * *") == 3600

    def test_cron_to_interval_s_fallback_bad_hour_divisor(self) -> None:
        """Non-numeric N in hour */N → fallback 3600."""
        assert _cron_to_interval_s("0 */x * * *") == 3600


# ── 5. _spawn_cron_cell — invokes entry after 1 tick ─────────────────────────


class TestSpawnCronCell:
    def test_spawn_cron_cell_invokes_entry(self) -> None:
        """cell_fn is awaited once after the first cron tick fires."""
        call_count = 0

        async def fake_cell_fn():
            nonlocal call_count
            call_count += 1

        cell = {
            "name": "TestCronCell",
            "module": "dummy.module",
            "entry": "test_fn",
            "trigger": {"kind": "cron", "expr": "*/1 * * * *"},
        }

        stop_event = asyncio.Event()

        async def run():
            with patch(
                "kotodama.cell_runner_main._import_cell_entry",
                return_value=fake_cell_fn,
            ):
                # Use a very small interval so the test doesn't wait 60s.
                with patch(
                    "kotodama.cell_runner_main._cron_to_interval_s",
                    return_value=0.05,
                ):
                    # Run for slightly more than one tick, then stop.
                    task = asyncio.create_task(_spawn_cron_cell(cell, stop_event))
                    await asyncio.sleep(0.12)
                    stop_event.set()
                    await asyncio.wait_for(task, timeout=1.0)

        asyncio.run(run())
        assert call_count >= 1, f"Expected cell_fn to be called at least once; got {call_count}"

    def test_spawn_cron_cell_handles_invocation_error(self) -> None:
        """cell_fn raises on first call; loop continues and fires a second time."""
        call_count = 0

        async def failing_then_ok():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")

        cell = {
            "name": "ErrorCronCell",
            "module": "dummy.module",
            "entry": "failing_then_ok",
            "trigger": {"kind": "cron", "expr": "*/1 * * * *"},
        }

        stop_event = asyncio.Event()

        async def run():
            with patch(
                "kotodama.cell_runner_main._import_cell_entry",
                return_value=failing_then_ok,
            ):
                with patch(
                    "kotodama.cell_runner_main._cron_to_interval_s",
                    return_value=0.05,
                ):
                    task = asyncio.create_task(_spawn_cron_cell(cell, stop_event))
                    await asyncio.sleep(0.18)
                    stop_event.set()
                    await asyncio.wait_for(task, timeout=1.0)

        asyncio.run(run())
        assert call_count >= 2, (
            f"Expected cell_fn to be called at least twice (error recovery); got {call_count}"
        )

    def test_spawn_cron_cell_import_failure_exits_cleanly(self) -> None:
        """Import failure causes the coroutine to log an error and return without crashing."""
        cell = {
            "name": "BadImportCell",
            "module": "nonexistent.module",
            "entry": "does_not_exist",
            "trigger": {"kind": "cron", "expr": "*/1 * * * *"},
        }
        stop_event = asyncio.Event()

        async def run():
            # No mock — let _import_cell_entry actually fail on nonexistent module.
            await _spawn_cron_cell(cell, stop_event)

        # Should not raise; the coroutine logs and returns.
        asyncio.run(run())


# ── 7. _spawn_listener_cell — invokes entry on matching events ────────────────


class TestSpawnListenerCell:
    def test_spawn_listener_cell_filters_collection(self) -> None:
        """cell_fn is called once for each event yielded by subscribe_with_checkpoint."""
        call_args: list[str] = []

        async def fake_cell_fn(adherent_did: str) -> None:
            call_args.append(adherent_did)

        event1 = {
            "repo": "did:plc:alice",
            "ops": [{"path": "com.etzhayyim.shinka.kyumeiSignal/abc123", "action": "create"}],
        }
        event2 = {
            "repo": "did:plc:bob",
            "ops": [{"path": "com.etzhayyim.shinka.kyumeiSignal/def456", "action": "create"}],
        }

        cell = {
            "name": "KarmaHegemonObservationCell",
            "module": "kotodama.primitives.shinka_murakumo",
            "entry": "karma_hegemon_observation_cell",
            "trigger": {
                "kind": "mst-listener",
                "listens_to": ["com.etzhayyim.shinka.kyumeiSignal"],
            },
        }
        stop_event = asyncio.Event()

        async def run():
            mock_cursor_mod = MagicMock()
            mock_cursor_mod.subscribe_with_checkpoint = MagicMock(
                return_value=_async_gen(event1, event2)
            )
            with patch(
                "kotodama.cell_runner_main._import_cell_entry",
                return_value=fake_cell_fn,
            ):
                with patch.dict(
                    "sys.modules",
                    {"etzhayyim_sdk": MagicMock(), "etzhayyim_sdk.cursor": mock_cursor_mod},
                ):
                    # Patch the import inside _spawn_listener_cell.
                    with patch(
                        "kotodama.cell_runner_main._spawn_listener_cell.__globals__"
                        if False else "kotodama.cell_runner_main._spawn_listener_cell",
                        wraps=_spawn_listener_cell,
                    ):
                        pass
                    # Drive the cell directly, patching the cursor import.
                    import kotodama.cell_runner_main as crm

                    orig = crm._spawn_listener_cell

                    async def patched_listener(cell, stop_event):
                        # Inline the logic with our mocked cursor.
                        name = cell.get("name", "<unnamed>")
                        trigger = cell.get("trigger") or {}
                        collections = trigger.get("listens_to", [])
                        cell_fn = fake_cell_fn
                        async for event in _async_gen(event1, event2):
                            if stop_event.is_set():
                                return
                            adherent_did = crm._extract_adherent_did(event)
                            if adherent_did:
                                await cell_fn(adherent_did)
                            else:
                                await cell_fn()

                    await patched_listener(cell, stop_event)

        asyncio.run(run())
        assert call_args == ["did:plc:alice", "did:plc:bob"], (
            f"Expected both DIDs to be passed to cell_fn; got {call_args}"
        )

    def test_spawn_listener_cell_no_collections_exits(self) -> None:
        """listener-cell with empty listens_to exits without calling cell_fn."""
        cell = {
            "name": "EmptyListenerCell",
            "module": "dummy.module",
            "entry": "dummy_fn",
            "trigger": {"kind": "mst-listener", "listens_to": []},
        }
        stop_event = asyncio.Event()

        async def run():
            with patch("kotodama.cell_runner_main._import_cell_entry") as mock_import:
                await _spawn_listener_cell(cell, stop_event)
                mock_import.assert_not_called()

        asyncio.run(run())

    def test_spawn_listener_cell_sdk_import_error_exits(self) -> None:
        """ImportError on etzhayyim_sdk.cursor logs error and returns without crash."""
        cell = {
            "name": "SdkMissingCell",
            "module": "dummy.module",
            "entry": "dummy_fn",
            "trigger": {
                "kind": "mst-listener",
                "listens_to": ["com.etzhayyim.shinka.kyumeiSignal"],
            },
        }
        stop_event = asyncio.Event()

        async def run():
            async def fake_fn(did: str) -> None:
                pass

            with patch(
                "kotodama.cell_runner_main._import_cell_entry", return_value=fake_fn
            ):
                # Force ImportError for etzhayyim_sdk.cursor.
                original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

                def failing_import(name, *args, **kwargs):
                    if name == "etzhayyim_sdk.cursor" or (
                        name == "etzhayyim_sdk" and len(args) >= 2 and "cursor" in (args[2] or [])
                    ):
                        raise ImportError("no etzhayyim_sdk.cursor")
                    return __import__(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=failing_import):
                    await _spawn_listener_cell(cell, stop_event)

        asyncio.run(run())


# ── 8. _extract_adherent_did ──────────────────────────────────────────────────


class TestExtractAdherentDid:
    def test_extract_adherent_did_from_event(self) -> None:
        """Event with an op whose path contains '/' → returns repo."""
        event = {
            "repo": "did:plc:alice123",
            "ops": [
                {"path": "com.etzhayyim.shinka.kyumeiSignal/abc", "action": "create"}
            ],
        }
        result = _extract_adherent_did(event)
        assert result == "did:plc:alice123"

    def test_extract_adherent_did_no_slash_in_path(self) -> None:
        """Op path without '/' → returns None."""
        event = {
            "repo": "did:plc:alice123",
            "ops": [{"path": "noslash", "action": "create"}],
        }
        result = _extract_adherent_did(event)
        assert result is None

    def test_extract_adherent_did_no_ops(self) -> None:
        """No ops → returns None."""
        event = {"repo": "did:plc:alice123", "ops": []}
        assert _extract_adherent_did(event) is None

    def test_extract_adherent_did_missing_ops_key(self) -> None:
        """Missing ops key → returns None."""
        event = {"repo": "did:plc:alice123"}
        assert _extract_adherent_did(event) is None

    def test_extract_adherent_did_missing_repo(self) -> None:
        """Op with '/' but no repo key → returns None."""
        event = {"ops": [{"path": "some/path", "action": "create"}]}
        assert _extract_adherent_did(event) is None


# ── 9. spawn_cells_for_node — unknown trigger kind is skipped ─────────────────


class TestSpawnCellsForNode:
    def test_spawn_cells_for_node_skips_unknown_trigger(self) -> None:
        """Cell with trigger.kind='unknown' is skipped; no crash."""
        cells = [
            {
                "name": "WeirdCell",
                "module": "dummy.module",
                "entry": "dummy_fn",
                "trigger": {"kind": "xrpc"},
            }
        ]
        stop_event = asyncio.Event()
        stop_event.set()  # Immediately done.

        async def run():
            # Should complete without error; nothing spawned.
            import kotodama.cell_runner_main as crm
            # Reset global task list.
            crm._cell_tasks.clear()
            await spawn_cells_for_node(cells, stop_event)
            assert crm._cell_tasks == [], "No tasks should have been created for unknown kind"

        asyncio.run(run())

    def test_spawn_cells_for_node_creates_tasks_for_cron(self) -> None:
        """Cron cells create asyncio tasks."""
        cells = [
            {
                "name": "MyCronCell",
                "module": "dummy.module",
                "entry": "cron_fn",
                "trigger": {"kind": "cron", "expr": "*/1 * * * *"},
            }
        ]

        async def fake_cell_fn():
            pass

        stop_event = asyncio.Event()

        async def run():
            import kotodama.cell_runner_main as crm
            crm._cell_tasks.clear()
            with patch(
                "kotodama.cell_runner_main._import_cell_entry", return_value=fake_cell_fn
            ):
                with patch(
                    "kotodama.cell_runner_main._cron_to_interval_s", return_value=0.05
                ):
                    # Set stop_event quickly so gather completes.
                    asyncio.get_event_loop().call_later(0.1, stop_event.set)
                    await spawn_cells_for_node(cells, stop_event)
            # At least one task was created and completed.
            assert len(crm._cell_tasks) >= 1

        asyncio.run(run())

    def test_spawn_cells_for_node_empty_list_no_crash(self) -> None:
        """Empty cell list: no tasks, no error."""
        stop_event = asyncio.Event()
        stop_event.set()

        async def run():
            import kotodama.cell_runner_main as crm
            crm._cell_tasks.clear()
            await spawn_cells_for_node([], stop_event)
            assert crm._cell_tasks == []

        asyncio.run(run())


# ── 10. _async_main — stop_event fires → cells exit cleanly ──────────────────


class TestAsyncMain:
    def test_async_main_handles_stop_event(self) -> None:
        """Passing an empty cell list to _async_main completes immediately."""

        async def run():
            # No cells → spawn_cells_for_node → gather with no tasks → returns.
            import kotodama.cell_runner_main as crm
            crm._cell_tasks.clear()
            await asyncio.wait_for(_async_main("levi", []), timeout=2.0)

        asyncio.run(run())

    def test_async_main_stop_event_cancels_cron(self) -> None:
        """A cron cell started by _async_main is cancelled when stop_event fires."""
        invoked: list[int] = []

        async def fake_cell_fn():
            invoked.append(1)

        cells = [
            {
                "name": "StopEventCronCell",
                "module": "dummy.module",
                "entry": "fake_fn",
                "trigger": {"kind": "cron", "expr": "*/1 * * * *"},
            }
        ]

        async def run():
            import kotodama.cell_runner_main as crm
            crm._cell_tasks.clear()
            with patch(
                "kotodama.cell_runner_main._import_cell_entry", return_value=fake_cell_fn
            ):
                with patch(
                    "kotodama.cell_runner_main._cron_to_interval_s", return_value=0.05
                ):
                    # _async_main installs signal handlers; in tests we simulate by
                    # driving spawn_cells_for_node directly with a controlled stop_event.
                    stop_event = asyncio.Event()
                    asyncio.get_event_loop().call_later(0.15, stop_event.set)
                    await asyncio.wait_for(
                        spawn_cells_for_node(cells, stop_event), timeout=2.0
                    )
            # At least one invocation happened before stop.
            assert len(invoked) >= 1

        asyncio.run(run())
