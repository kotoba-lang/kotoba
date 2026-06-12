"""Pure-logic tests for kinoko_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


def test_uid_prefix():
    from kotodama.kinoko_worker_main import _uid

    a = _uid("blk")
    b = _uid("rec")
    assert a.startswith("blk-")
    assert b.startswith("rec-")
    assert a != b


def test_now_iso():
    from kotodama.kinoko_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_check_flow_threshold ────────────────────────────────────────────────


def test_threshold_not_met_low_flow():
    """totalFlow < FLOW_THRESHOLD → blockFormed=False."""
    with patch(
        "kotodama.kinoko_worker_main.fetch_one",
        return_value=(40.0, 0.8, 3),
    ):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold())

    assert result["blockFormed"] is False
    assert result["totalFlow"] == 40.0
    assert result["participantCount"] == 3
    assert result["minEta"] == 0.8


def test_threshold_not_met_low_eta():
    """totalFlow >= 100 but minEta < 0.5 → blockFormed=False."""
    with patch(
        "kotodama.kinoko_worker_main.fetch_one",
        return_value=(150.0, 0.3, 5),
    ):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold())

    assert result["blockFormed"] is False
    assert result["totalFlow"] == 150.0
    assert result["minEta"] == 0.3


def test_threshold_not_met_no_rows():
    """No active hyphae → defaults (flow=0, eta=1.0) → blockFormed=False."""
    with patch("kotodama.kinoko_worker_main.fetch_one", return_value=None):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold())

    assert result["blockFormed"] is False
    assert result["totalFlow"] == 0.0


def test_threshold_met_forms_block():
    """totalFlow >= 100 and minEta >= 0.5 → blockFormed=True, block inserted."""
    mock_cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.kinoko_worker_main.fetch_one",
            return_value=(120.0, 0.72, 7),
        ),
        patch("kotodama.kinoko_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold())

    assert result["blockFormed"] is True
    assert result["blockId"].startswith("blk-")
    assert result["blockVertexId"].startswith("at://did:web:kinoko.etzhayyim.com/")
    assert result["totalFlow"] == 120.0
    assert result["participantCount"] == 7
    assert result["minEta"] == 0.72
    assert result["snapshotHash"]
    assert len(result["snapshotHash"]) == 32


def test_block_formation_resets_hyphae():
    """After block formation, consumed UPDATE is called on edge_kabi_hypha."""
    mock_cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.kinoko_worker_main.fetch_one",
            return_value=(200.0, 0.9, 10),
        ),
        patch("kotodama.kinoko_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold(lastBlockId="blk-previous"))

    assert result["blockFormed"] is True
    # Two execute calls: INSERT vertex_kinoko_block + UPDATE edge_kabi_hypha
    assert mock_cursor.execute.call_count == 2
    update_call = mock_cursor.execute.call_args_list[1]
    assert "consumed" in update_call[0][0]


def test_threshold_exact_boundary():
    """totalFlow == 100.0, minEta == 0.5 → exactly on boundary → blockFormed=True."""
    mock_cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.kinoko_worker_main.fetch_one",
            return_value=(100.0, 0.5, 4),
        ),
        patch("kotodama.kinoko_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kinoko_worker_main import task_check_flow_threshold

        result = _run(task_check_flow_threshold())

    assert result["blockFormed"] is True
