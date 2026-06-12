"""Pure tests for patent_blob_convert Functional API port.

Validates:
  - build_graph returns an object with .invoke / .ainvoke (entrypoint shape)
  - Empty pending → {converted: 0, ok: True}
  - Exception path → {ok: False, error: ..., converted: 0}
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")
pytest.importorskip("langgraph.func", reason="langgraph functional API not available")


def test_build_graph_returns_entrypoint() -> None:
    from kotodama.langgraph_graphs import patent_blob_convert as m

    g = m.build_graph()
    # Entrypoint exposes the same callable surface as a compiled StateGraph.
    assert hasattr(g, "invoke")
    assert hasattr(g, "ainvoke")


def test_empty_pending_returns_ok_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama.langgraph_graphs import patent_blob_convert as m

    monkeypatch.setattr(m, "_select_pending", lambda limit: [])

    g = m.build_graph()
    out = g.invoke({"limit": 10})
    assert out == {"converted": 0, "ok": True}


def test_convert_path_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama.langgraph_graphs import patent_blob_convert as m

    fake_rows = [{"vertex_id": "v1"}, {"vertex_id": "v2"}]
    monkeypatch.setattr(m, "_select_pending", lambda limit: fake_rows)

    async def _fake_convert(rows):
        assert rows == fake_rows
        return {"ok_count": 2, "fail_count": 0}

    monkeypatch.setattr(m, "_convert", _fake_convert)

    g = m.build_graph()
    out = g.invoke({"limit": 10})
    assert out["converted"] == 2
    assert out["ok"] is True
    assert out["ok_count"] == 2


def test_exception_returns_error_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama.langgraph_graphs import patent_blob_convert as m

    def _boom(_limit):
        raise RuntimeError("db down")

    monkeypatch.setattr(m, "_select_pending", _boom)

    g = m.build_graph()
    out = g.invoke({"limit": 5})
    assert out["ok"] is False
    assert out["converted"] == 0
    assert "db down" in out["error"]
