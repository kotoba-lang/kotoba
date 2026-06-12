"""Pure-logic tests for kabi_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _run(coro):
    return asyncio.run(coro)


def test_uid_prefix():
    from kotodama.kabi_worker_main import _uid

    a = _uid("anast")
    b = _uid("hyph")
    assert a.startswith("anast-")
    assert b.startswith("hyph-")
    assert a != b


def test_now_iso():
    from kotodama.kabi_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_anastomosis_probe ───────────────────────────────────────────────────


def test_anastomosis_probe_missing_dids():
    """No DIDs → compatible=False."""
    from kotodama.kabi_worker_main import task_anastomosis_probe

    result = _run(task_anastomosis_probe())
    assert result["probeResult"]["compatible"] is False
    assert "missing" in result["probeResult"]["reason"]


def test_anastomosis_probe_only_one_did():
    """Only one DID → compatible=False."""
    from kotodama.kabi_worker_main import task_anastomosis_probe

    result = _run(task_anastomosis_probe(networkADid="did:web:kabi.etzhayyim.com:a"))
    assert result["probeResult"]["compatible"] is False


def test_anastomosis_probe_no_actor_rows():
    """Both DIDs present but no vertex_actor rows → falls back to default eta=0.5, compatible."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.kabi_worker_main.fetch_one", return_value=None),
        patch("kotodama.kabi_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kabi_worker_main import task_anastomosis_probe

        result = _run(task_anastomosis_probe(
            networkADid="did:web:kabi.etzhayyim.com:a",
            networkBDid="did:web:kabi.etzhayyim.com:b",
            edgeId="anast-test",
        ))

    probe = result["probeResult"]
    # Both eta=0.5, diff=0.0 ≤ 0.1 threshold, no prion conflict → compatible
    assert probe["compatible"] is True
    assert probe["eta_diff"] == 0.0
    assert probe["prion_conflict"] is False


def test_anastomosis_probe_high_eta_diff():
    """η diff > threshold → compatible=False."""
    import json

    # fetch_one called twice: first for networkA, then for networkB
    side = [
        (json.dumps({"eta": 0.9, "prions": []}),),
        (json.dumps({"eta": 0.5, "prions": []}),),
    ]

    with patch("kotodama.kabi_worker_main.fetch_one", side_effect=side):
        from kotodama.kabi_worker_main import task_anastomosis_probe

        result = _run(task_anastomosis_probe(
            networkADid="did:web:kabi.etzhayyim.com:a",
            networkBDid="did:web:kabi.etzhayyim.com:b",
        ))

    probe = result["probeResult"]
    assert probe["compatible"] is False
    assert abs(probe["eta_diff"] - 0.4) < 0.01


def test_anastomosis_probe_prion_conflict():
    """Shared prion hash → prion_conflict=True, compatible=False."""
    import json

    def _mock_fetch(q, p):
        if "kabi.etzhayyim.com:a" in p[0]:
            return (json.dumps({"eta": 0.8, "prions": ["bad-prion"]}),)
        return (json.dumps({"eta": 0.82, "prions": ["bad-prion"]}),)

    with patch("kotodama.kabi_worker_main.fetch_one", side_effect=_mock_fetch):
        from kotodama.kabi_worker_main import task_anastomosis_probe

        result = _run(task_anastomosis_probe(
            networkADid="did:web:kabi.etzhayyim.com:a",
            networkBDid="did:web:kabi.etzhayyim.com:b",
        ))

    probe = result["probeResult"]
    assert probe["prion_conflict"] is True
    assert probe["compatible"] is False


def test_anastomosis_probe_accept_inserts_edge():
    """Compatible networks with edgeId → edge is inserted."""
    import json

    mock_cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)

    def _mock_fetch(q, p):
        return (json.dumps({"eta": 0.75, "prions": []}),)

    with (
        patch("kotodama.kabi_worker_main.fetch_one", side_effect=_mock_fetch),
        patch("kotodama.kabi_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.kabi_worker_main import task_anastomosis_probe

        result = _run(task_anastomosis_probe(
            networkADid="did:web:kabi.etzhayyim.com:a",
            networkBDid="did:web:kabi.etzhayyim.com:b",
            edgeId="anast-explicit-id",
        ))

    assert result["probeResult"]["compatible"] is True
    mock_cursor.execute.assert_called_once()
    call_args = mock_cursor.execute.call_args[0][1]
    assert "anast-explicit-id" in call_args
