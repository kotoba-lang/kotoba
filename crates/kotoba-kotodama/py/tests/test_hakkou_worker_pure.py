"""Pure-logic tests for hakkou_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


def test_uid_prefix():
    from kotodama.hakkou_worker_main import _uid

    a = _uid("hak")
    b = _uid("rec")
    assert a.startswith("hak-")
    assert b.startswith("rec-")
    assert a != b


def test_now_iso():
    from kotodama.hakkou_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_create_ferment_record ───────────────────────────────────────────────


def test_create_ferment_record_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.hakkou_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.hakkou_worker_main import task_create_ferment_record

        result = _run(task_create_ferment_record(
            inputKind="text",
            inputRef="some raw content",
            outputKind="insight",
        ))

    assert result["fermentId"]
    assert result["status"] == "pending"
    assert result["fermentVertexId"].startswith("at://did:web:hakkou.etzhayyim.com/")
    assert result["createdAt"]


def test_create_ferment_record_uses_provided_vertex_id():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    vid = "at://did:web:hakkou.etzhayyim.com/com.etzhayyim.apps.hakkou.ferment/hak-abc123"
    with patch("kotodama.hakkou_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.hakkou_worker_main import task_create_ferment_record

        result = _run(task_create_ferment_record(fermentVertexId=vid))

    assert result["fermentVertexId"] == vid
    assert result["fermentId"] == "hak-abc123"


# ─── task_llm_transform ───────────────────────────────────────────────────────


def test_llm_transform_valid():
    mock_llm = MagicMock(return_value={
        "content": '{"fermentedContent":"structured output","confidence":0.9,"tags":["test"]}',
        "finish": "stop",
    })

    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.hakkou_worker_main import task_llm_transform

        result = _run(task_llm_transform(inputKind="text", inputRef="raw input"))

    assert result["fermentOutput"]["content"] == "structured output"
    assert result["fermentOutput"]["confidence"] == 0.9
    assert result["ethanolHash"]


def test_llm_transform_invalid_json_fallback():
    mock_llm = MagicMock(return_value={"content": "not json", "finish": "stop"})

    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.hakkou_worker_main import task_llm_transform

        result = _run(task_llm_transform(inputRef="content"))

    assert result["fermentOutput"]["confidence"] == 0.5
    assert result["ethanolHash"]


# ─── task_finalize_ferment ────────────────────────────────────────────────────


def test_finalize_ferment_no_vertex_id():
    from kotodama.hakkou_worker_main import task_finalize_ferment

    result = _run(task_finalize_ferment())
    assert "error" in result


def test_finalize_ferment_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    vid = "at://did:web:hakkou.etzhayyim.com/com.etzhayyim.apps.hakkou.ferment/hak-xyz"
    with patch("kotodama.hakkou_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.hakkou_worker_main import task_finalize_ferment

        result = _run(task_finalize_ferment(
            fermentVertexId=vid,
            ethanolHash="deadbeef",
            outputVertexId="at://ki.etzhayyim.com/absorb/xyl-001",
        ))

    assert result["fermented"] is True
    assert result["fermentVertexId"] == vid
    assert result["ethanolHash"] == "deadbeef"
    assert result["fermentedAt"]
