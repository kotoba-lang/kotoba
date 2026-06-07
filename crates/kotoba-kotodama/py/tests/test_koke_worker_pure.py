"""Pure-logic tests for koke_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ─── helpers ──────────────────────────────────────────────────────────────


def test_uid_prefix():
    from kotodama.koke_worker_main import _uid

    a = _uid("kox")
    b = _uid("kflo")
    assert a.startswith("kox-")
    assert b.startswith("kflo-")
    assert a != b


def test_now_iso():
    from kotodama.koke_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_scan_raw_signals ────────────────────────────────────────────────


def test_scan_empty():
    with patch("kotodama.koke_worker_main.fetch_all", return_value=[]):
        from kotodama.koke_worker_main import task_scan_raw_signals

        result = _run(task_scan_raw_signals())

    assert result["signalCount"] == 0
    assert result["signals"] == []


def test_scan_returns_pending():
    rows = [
        ("at://koke.etzhayyim.com/rec/1", "text", "raw content A", "aabbcc"),
        ("at://koke.etzhayyim.com/rec/2", "url", "https://example.com", "ddeeff"),
    ]
    with patch("kotodama.koke_worker_main.fetch_all", return_value=rows):
        from kotodama.koke_worker_main import task_scan_raw_signals

        result = _run(task_scan_raw_signals())

    assert result["signalCount"] == 2
    assert result["signals"][0]["inputKind"] == "text"
    assert result["signals"][1]["inputKind"] == "url"


# ─── task_fix_signal ─────────────────────────────────────────────────────


def test_fix_signal_no_input():
    from kotodama.koke_worker_main import task_fix_signal

    result = _run(task_fix_signal())
    assert "error" in result


def test_fix_signal_new_record():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.koke_worker_main import task_fix_signal

        result = _run(task_fix_signal(inputKind="text", rawRef="hello world signal"))

    assert result["fixationId"].startswith("kox-")
    assert result["status"] == "fixed"
    assert result["signalHash"]
    assert result["inputKind"] == "text"


def test_fix_signal_from_scan_batch():
    """Processing signals from scan batch updates existing fixation row."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    signals = [
        {
            "vertexId": "at://koke.etzhayyim.com/com.etzhayyim.apps.koke.fixation/kox-abc",
            "inputKind": "text",
            "rawRef": "some raw content",
            "signalHash": "",
        }
    ]

    with patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.koke_worker_main import task_fix_signal

        result = _run(task_fix_signal(signals=signals))

    assert result["status"] == "fixed"
    assert result["signalHash"]
    assert result["fixationId"] == "kox-abc"


def test_fix_signal_hash_deterministic():
    """Same rawRef → same signalHash."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.koke_worker_main import task_fix_signal

        r1 = _run(task_fix_signal(inputKind="text", rawRef="deterministic content"))
        r2 = _run(task_fix_signal(inputKind="text", rawRef="deterministic content"))

    assert r1["signalHash"] == r2["signalHash"]


# ─── task_classify_fixation ───────────────────────────────────────────────


def test_classify_no_fixation_or_ref():
    from kotodama.koke_worker_main import task_classify_fixation

    result = _run(task_classify_fixation())
    assert "error" in result
    assert result["classification"] == "unknown"
    assert result["confidence"] == 0.0


def test_classify_valid_llm_response():
    mock_llm = MagicMock(return_value={
        "content": '{"classification":"knowledge","confidence":0.85,"summary":"test"}',
        "finish": "stop",
    })
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.llm.call_tier", mock_llm),
        patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.koke_worker_main import task_classify_fixation

        result = _run(task_classify_fixation(
            fixationId="kox-abc",
            inputKind="text",
            rawRef="Some knowledge content",
        ))

    assert result["classification"] == "knowledge"
    assert result["confidence"] == 0.85
    assert result["fixationId"] == "kox-abc"


def test_classify_invalid_llm_json_fallback():
    """Non-JSON LLM response → falls back to 'signal' with 0.5 confidence."""
    mock_llm = MagicMock(return_value={
        "content": "not valid json at all",
        "finish": "stop",
    })
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.llm.call_tier", mock_llm),
        patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.koke_worker_main import task_classify_fixation

        result = _run(task_classify_fixation(
            fixationId="kox-xyz",
            rawRef="ambiguous signal",
        ))

    assert result["classification"] == "signal"
    assert result["confidence"] == 0.5


def test_classify_without_fixation_id():
    """rawRef without fixationId → classifies but skips DB update."""
    mock_llm = MagicMock(return_value={
        "content": '{"classification":"noise","confidence":0.2,"summary":"low value"}',
        "finish": "stop",
    })

    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.koke_worker_main import task_classify_fixation

        result = _run(task_classify_fixation(
            fixationId="",
            rawRef="noise content here",
        ))

    assert result["classification"] == "noise"
    assert result["confidence"] == 0.2


# ─── task_handoff_to_hakkou ───────────────────────────────────────────────


def test_handoff_no_fixation_id():
    from kotodama.koke_worker_main import task_handoff_to_hakkou

    result = _run(task_handoff_to_hakkou(fixationId=""))
    assert "error" in result


def test_handoff_fixation_not_found():
    with patch("kotodama.koke_worker_main.fetch_one", return_value=None):
        from kotodama.koke_worker_main import task_handoff_to_hakkou

        result = _run(task_handoff_to_hakkou(fixationId="kox-missing"))
    assert "error" in result


def test_handoff_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    fixation_row = ("at://koke.etzhayyim.com/com.etzhayyim.apps.koke.fixation/kox-abc",)

    with (
        patch("kotodama.koke_worker_main.fetch_one", return_value=fixation_row),
        patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.koke_worker_main import task_handoff_to_hakkou

        result = _run(task_handoff_to_hakkou(
            fixationId="kox-abc",
            classification="knowledge",
            inputKind="text",
            rawRef="structured content",
        ))

    assert result["fermentId"].startswith("fmnt-")
    assert result["edgeId"].startswith("kflo-")
    assert result["fixationId"] == "kox-abc"
    assert result["handedOffAt"]


# ─── task_handoff_to_saikin ───────────────────────────────────────────────


def test_handoff_to_saikin_no_fixation_id():
    from kotodama.koke_worker_main import task_handoff_to_saikin

    result = _run(task_handoff_to_saikin(fixationId=""))
    assert "error" in result


def test_handoff_to_saikin_fixation_not_found():
    with patch("kotodama.koke_worker_main.fetch_one", return_value=None):
        from kotodama.koke_worker_main import task_handoff_to_saikin

        result = _run(task_handoff_to_saikin(fixationId="kox-missing"))
    assert "error" in result


def test_handoff_to_saikin_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    fixation_row = (
        "at://koke.etzhayyim.com/com.etzhayyim.apps.koke.fixation/kox-abc",
        "text",
        "raw signal content",
        "aabbcc112233",
    )

    with (
        patch("kotodama.koke_worker_main.fetch_one", return_value=fixation_row),
        patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.koke_worker_main import task_handoff_to_saikin

        result = _run(task_handoff_to_saikin(
            fixationId="kox-abc",
            classification="knowledge",
            inputKind="text",
            rawRef="raw signal content",
        ))

    assert result["saikinSignalId"].startswith("s41k-")
    assert result["saikinSignalVertexId"].startswith("at://did:web:saikin.etzhayyim.com/")
    assert result["edgeId"].startswith("kflo-")
    assert result["fixationId"] == "kox-abc"
    assert result["handedOffAt"]


def test_handoff_to_saikin_uses_fixation_fields():
    """Fixation's input_kind/raw_ref/signal_hash are propagated to saikin signal."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    executed_inserts: list[tuple] = []

    def capture_execute(sql, params):
        executed_inserts.append(params)

    mock_cursor = MagicMock()
    mock_cursor.execute = capture_execute
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)

    fixation_row = (
        "at://koke.etzhayyim.com/com.etzhayyim.apps.koke.fixation/kox-xyz",
        "url",
        "https://example.com/signal",
        "deadbeef1234",
    )

    with (
        patch("kotodama.koke_worker_main.fetch_one", return_value=fixation_row),
        patch("kotodama.koke_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.koke_worker_main import task_handoff_to_saikin

        result = _run(task_handoff_to_saikin(
            fixationId="kox-xyz",
            classification="signal",
        ))

    # First INSERT is vertex_saikin_signal; params[11]=input_kind, [12]=raw_ref, [13]=signal_hash, [14]=probe_source
    insert_params = executed_inserts[0]
    assert insert_params[11] == "url"
    assert insert_params[12] == "https://example.com/signal"
    assert insert_params[13] == "deadbeef1234"
    assert insert_params[14] == "koke"
