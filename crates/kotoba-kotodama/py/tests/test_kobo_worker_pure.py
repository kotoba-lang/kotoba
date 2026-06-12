"""Pure-logic tests for kobo_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


def test_uid_prefix():
    from kotodama.kobo_worker_main import _uid

    a = _uid("bud")
    b = _uid("spore")
    assert a.startswith("bud-")
    assert b.startswith("spore-")
    assert a != b


# ─── task_bud_agent ───────────────────────────────────────────────────────────


def test_bud_agent_no_dids():
    from kotodama.kobo_worker_main import task_bud_agent

    result = _run(task_bud_agent())
    assert "error" in result


def test_bud_agent_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.kobo_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.kobo_worker_main import task_bud_agent

        result = _run(task_bud_agent(
            parentDid="did:web:kobo.etzhayyim.com",
            childDid="did:web:kobo-child.etzhayyim.com",
            parentEta=0.75,
        ))

    assert result["buddingEdgeId"].startswith("bud-")
    assert result["parentDid"] == "did:web:kobo.etzhayyim.com"
    assert result["childDid"] == "did:web:kobo-child.etzhayyim.com"
    assert result["buddedAt"]


def test_bud_agent_uses_provided_edge_id():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.kobo_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.kobo_worker_main import task_bud_agent

        result = _run(task_bud_agent(
            parentDid="did:web:a.etzhayyim.com",
            childDid="did:web:b.etzhayyim.com",
            buddingEdgeId="bud-custom123",
        ))

    assert result["buddingEdgeId"] == "bud-custom123"


# ─── task_sporulate ───────────────────────────────────────────────────────────


def test_sporulate_no_agent_did():
    from kotodama.kobo_worker_main import task_sporulate

    result = _run(task_sporulate())
    assert "error" in result


def test_sporulate_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.kobo_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.kobo_worker_main import task_sporulate

        result = _run(task_sporulate(
            agentDid="did:web:kobo.etzhayyim.com",
            blobCbor="cbor_blob_data",
            quorumN=3,
        ))

    assert result["sporeHash"]
    assert result["agentDid"] == "did:web:kobo.etzhayyim.com"
    assert result["sporulatedAt"]
    assert result["sporeVertexId"].startswith("at://did:web:houshi.etzhayyim.com/")


# ─── task_germinate ───────────────────────────────────────────────────────────


def test_germinate_no_spore_vertex():
    from kotodama.kobo_worker_main import task_germinate

    result = _run(task_germinate())
    assert "error" in result
    assert result["germinated"] is False


def test_germinate_spore_not_found():
    with patch("kotodama.kobo_worker_main.fetch_one", return_value=None):
        from kotodama.kobo_worker_main import task_germinate

        result = _run(task_germinate(sporeVertexId="at://houshi/spore/spore-missing"))

    assert "error" in result
    assert result["germinated"] is False


def test_germinate_quorum_not_reached():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    # custody_count=0, quorum_n=3 → 1 confirmation not enough
    spore_row = ("at://houshi/spore/spore-abc", 0, 3, "did:web:kobo.etzhayyim.com")
    with (
        patch("kotodama.kobo_worker_main.fetch_one", return_value=spore_row),
        patch("kotodama.kobo_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kobo_worker_main import task_germinate

        result = _run(task_germinate(sporeVertexId="at://houshi/spore/spore-abc"))

    assert result["germinated"] is False
    assert result["confirmedCount"] == 1
    assert result["requiredCount"] == 3


def test_germinate_quorum_reached():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    # custody_count=1, quorum_n=2 → 2nd confirmation reaches quorum
    spore_row = ("at://houshi/spore/spore-abc", 1, 2, "did:web:kobo.etzhayyim.com")
    with (
        patch("kotodama.kobo_worker_main.fetch_one", return_value=spore_row),
        patch("kotodama.kobo_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kobo_worker_main import task_germinate

        result = _run(task_germinate(
            sporeVertexId="at://houshi/spore/spore-abc",
            newAgentDid="did:web:kobo-revived.etzhayyim.com",
        ))

    assert result["germinated"] is True
    assert result["confirmedCount"] == 2
    assert result["germinatedAt"]
