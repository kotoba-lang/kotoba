"""Pure-logic tests for saikin_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ─── helpers ──────────────────────────────────────────────────────────────


def test_uid_prefix():
    from kotodama.saikin_worker_main import _uid

    a = _uid("hgt")
    b = _uid("col")
    assert a.startswith("hgt-")
    assert b.startswith("col-")
    assert a != b


def test_now_iso():
    from kotodama.saikin_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_probe_environment ───────────────────────────────────────────────


def test_probe_empty():
    with patch("kotodama.saikin_worker_main.fetch_all", return_value=[]):
        from kotodama.saikin_worker_main import task_probe_environment

        result = _run(task_probe_environment())

    assert result["signalCount"] == 0
    assert result["signals"] == []


def test_probe_returns_signals():
    rows = [
        ("at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.signal/s41k-abc", "hash1", "text", "content A"),
        ("at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.signal/s41k-def", "hash2", "url", "https://x.com"),
    ]
    with patch("kotodama.saikin_worker_main.fetch_all", return_value=rows):
        from kotodama.saikin_worker_main import task_probe_environment

        result = _run(task_probe_environment())

    assert result["signalCount"] == 2
    assert result["signals"][0]["inputKind"] == "text"
    assert result["signals"][1]["inputKind"] == "url"


# ─── task_transfer_signal ─────────────────────────────────────────────────


def test_transfer_no_input():
    from kotodama.saikin_worker_main import task_transfer_signal

    result = _run(task_transfer_signal())
    assert "error" in result


def test_transfer_by_signal_id():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.saikin_worker_main import task_transfer_signal

        result = _run(task_transfer_signal(
            signalId="s41k-abc",
            targetActorDid="did:web:koke.etzhayyim.com",
        ))

    assert result["transferId"].startswith("hgt-")
    assert result["signalId"] == "s41k-abc"
    assert result["targetActorDid"] == "did:web:koke.etzhayyim.com"
    assert result["status"] == "transferred"


def test_transfer_from_probe_batch():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    signals = [{"signalId": "s41k-xyz", "rawRef": "test", "inputKind": "text"}]

    with patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.saikin_worker_main import task_transfer_signal

        result = _run(task_transfer_signal(signals=signals))

    assert result["transferId"].startswith("hgt-")
    assert result["signalId"] == "s41k-xyz"
    assert result["status"] == "transferred"


# ─── task_form_colony ─────────────────────────────────────────────────────


def test_form_colony_no_signals():
    from kotodama.saikin_worker_main import task_form_colony

    result = _run(task_form_colony())
    assert "error" in result


def test_form_colony_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    signal_ids = ["s41k-a", "s41k-b", "s41k-c"]

    with patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.saikin_worker_main import task_form_colony

        result = _run(task_form_colony(signalIds=signal_ids, colonyLabel="test-colony"))

    assert result["colonyId"].startswith("col-")
    assert result["memberCount"] == 3
    assert result["status"] == "active"
    assert result["formedAt"]


def test_form_colony_member_count():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.saikin_worker_main import task_form_colony

        result = _run(task_form_colony(signalIds=["a", "b"]))

    assert result["memberCount"] == 2


# ─── task_lyse ────────────────────────────────────────────────────────────


def test_lyse_no_signal_id():
    from kotodama.saikin_worker_main import task_lyse

    result = _run(task_lyse())
    assert "error" in result


def test_lyse_not_found():
    with patch("kotodama.saikin_worker_main.fetch_one", return_value=None):
        from kotodama.saikin_worker_main import task_lyse

        result = _run(task_lyse(signalId="s41k-missing"))
    assert "error" in result


def test_lyse_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    row = ("at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.signal/s41k-abc",)

    with (
        patch("kotodama.saikin_worker_main.fetch_one", return_value=row),
        patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.saikin_worker_main import task_lyse

        result = _run(task_lyse(signalId="s41k-abc", reason="processed"))

    assert result["lysed"] is True
    assert result["signalId"] == "s41k-abc"
    assert result["reason"] == "processed"
    assert result["lysedAt"]


# ─── task_handoff_to_ki ───────────────────────────────────────────────────


def test_handoff_to_ki_no_args():
    from kotodama.saikin_worker_main import task_handoff_to_ki

    result = _run(task_handoff_to_ki())
    assert "error" in result


def test_handoff_to_ki_colony_not_found():
    with patch("kotodama.saikin_worker_main.fetch_one", return_value=None):
        from kotodama.saikin_worker_main import task_handoff_to_ki

        result = _run(task_handoff_to_ki(colonyId="col-missing", signalId=""))
    assert "error" in result


def test_handoff_to_ki_via_colony():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    colony_row = (
        "at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.colony/col-abc",
        "knowledge colony",
        '{"signalIds":["s41k-001"]}',
    )

    with (
        patch("kotodama.saikin_worker_main.fetch_one", return_value=colony_row),
        patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.saikin_worker_main import task_handoff_to_ki

        result = _run(task_handoff_to_ki(colonyId="col-abc", signalId=""))

    assert result["kiAbsorbId"].startswith("xyl-")
    assert result["kiAbsorbVertexId"].startswith("at://did:web:ki.etzhayyim.com/")
    assert result["sourceVertexId"] == "at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.colony/col-abc"
    assert result["handedOffAt"]


def test_handoff_to_ki_falls_back_to_signal():
    """When colony not found, falls back to signalId lookup."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    signal_row = (
        "at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.signal/s41k-xyz",
        "text",
        "horizontal gene transfer content",
    )

    # first fetch_one for colony returns None; second for signal returns the row
    with (
        patch("kotodama.saikin_worker_main.fetch_one", side_effect=[None, signal_row]),
        patch("kotodama.saikin_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.saikin_worker_main import task_handoff_to_ki

        result = _run(task_handoff_to_ki(colonyId="col-missing", signalId="s41k-xyz"))

    assert result["kiAbsorbId"].startswith("xyl-")
    assert result["sourceVertexId"] == "at://saikin.etzhayyim.com/com.etzhayyim.apps.saikin.signal/s41k-xyz"
