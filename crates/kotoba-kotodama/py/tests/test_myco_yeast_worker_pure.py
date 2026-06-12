"""Pure-logic tests for myco_yeast_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ─── helpers ──────────────────────────────────────────────────────────────


def test_uid_prefix():
    from kotodama.myco_yeast_worker_main import _uid

    a = _uid("ana")
    b = _uid("blk")
    assert a.startswith("ana-")
    assert b.startswith("blk-")
    assert a != b


def test_now_iso():
    from kotodama.myco_yeast_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_kabi_anastomosis_probe ─────────────────────────────────────────


def test_anastomosis_no_networks():
    """Both networks absent → REJECT."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.myco_yeast_worker_main.fetch_one",
            side_effect=[None, None, (None,), (None,), (0,), (0,)],
        ),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kabi_anastomosis_probe

        result = _run(task_kabi_anastomosis_probe(
            network_a_did="did:web:kabi.etzhayyim.com:a",
            network_b_did="did:web:kabi.etzhayyim.com:b",
        ))

    assert result["result"] == "REJECT"
    assert result["edgeId"].startswith("ana-")


def test_anastomosis_malignant_prion():
    """Malignant prion on side A → REJECT."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.myco_yeast_worker_main.fetch_one",
            side_effect=[
                ("v1", 5, 10),    # row_a
                ("v2", 3, 6),     # row_b
                (0.8,),           # eta_a avg
                (0.75,),          # eta_b avg
                (2,),             # malignant_a count = 2 → REJECT
                (0,),             # malignant_b count
            ],
        ),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kabi_anastomosis_probe

        result = _run(task_kabi_anastomosis_probe(
            network_a_did="did:web:kabi.etzhayyim.com:a",
            network_b_did="did:web:kabi.etzhayyim.com:b",
        ))

    assert result["result"] == "REJECT"
    assert "prion" in result["reason"]


def test_anastomosis_accept():
    """Clean networks with close η → ACCEPT."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.myco_yeast_worker_main.fetch_one",
            side_effect=[
                ("v1", 5, 10),   # row_a
                ("v2", 3, 6),    # row_b
                (0.8,),          # eta_a
                (0.85,),         # eta_b — diff = 0.05 < 0.3
                (0,),            # malignant_a
                (0,),            # malignant_b
            ],
        ),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kabi_anastomosis_probe

        result = _run(task_kabi_anastomosis_probe(
            network_a_did="did:web:kabi.etzhayyim.com:a",
            network_b_did="did:web:kabi.etzhayyim.com:b",
        ))

    assert result["result"] == "ACCEPT"
    assert result["compatibilityScore"] > 0.5


# ─── task_kobo_bud_agent ─────────────────────────────────────────────────


def test_bud_agent_no_parent():
    """No parent_did → error."""
    from kotodama.myco_yeast_worker_main import task_kobo_bud_agent

    result = _run(task_kobo_bud_agent(parent_did=""))
    assert "error" in result


def test_bud_agent_parent_not_found():
    with patch("kotodama.myco_yeast_worker_main.fetch_one", return_value=None):
        from kotodama.myco_yeast_worker_main import task_kobo_bud_agent

        result = _run(task_kobo_bud_agent(parent_did="did:web:kobo.etzhayyim.com:p1"))
    assert "error" in result


def test_bud_agent_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    parent_row = ("at://kobo.etzhayyim.com/rec/1", 0.7, "scout", 0.1)
    prions = [("ph1", True, 0.0, "pattern_a"), ("ph2", True, 0.0, "pattern_b")]

    with (
        patch("kotodama.myco_yeast_worker_main.fetch_one", return_value=parent_row),
        patch("kotodama.myco_yeast_worker_main.fetch_all", return_value=prions),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kobo_bud_agent

        result = _run(task_kobo_bud_agent(
            parent_did="did:web:kobo.etzhayyim.com:p1",
            child_did="did:web:kobo.etzhayyim.com:c1",
        ))

    assert result["childDid"] == "did:web:kobo.etzhayyim.com:c1"
    assert result["prionCount"] == 2
    assert result["edgeId"].startswith("bud-")


# ─── task_kobo_sporulate ─────────────────────────────────────────────────


def test_sporulate_no_agent_did():
    from kotodama.myco_yeast_worker_main import task_kobo_sporulate

    result = _run(task_kobo_sporulate(agent_did=""))
    assert "error" in result


def test_sporulate_agent_not_found():
    with patch("kotodama.myco_yeast_worker_main.fetch_one", return_value=None):
        from kotodama.myco_yeast_worker_main import task_kobo_sporulate

        result = _run(task_kobo_sporulate(agent_did="did:web:kobo.etzhayyim.com:a1"))
    assert "error" in result


def test_sporulate_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    agent = ("at://kobo.etzhayyim.com/rec/1", 0.8, '{"state":"active"}')
    prions = [("ph1", True, "foo")]

    with (
        patch("kotodama.myco_yeast_worker_main.fetch_one", return_value=agent),
        patch("kotodama.myco_yeast_worker_main.fetch_all", return_value=prions),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kobo_sporulate

        result = _run(task_kobo_sporulate(agent_did="did:web:kobo.etzhayyim.com:a1"))

    assert result["sporeId"].startswith("spr-")
    assert result["revivalKeyHint"]


# ─── task_kobo_germinate ─────────────────────────────────────────────────


def test_germinate_no_spore_id():
    from kotodama.myco_yeast_worker_main import task_kobo_germinate

    result = _run(task_kobo_germinate(spore_id=""))
    assert "error" in result


def test_germinate_spore_not_found():
    with patch("kotodama.myco_yeast_worker_main.fetch_one", return_value=None):
        from kotodama.myco_yeast_worker_main import task_kobo_germinate

        result = _run(task_kobo_germinate(spore_id="spr-abc123"))
    assert "error" in result


def test_germinate_quorum_not_met():
    spore = ("at://houshi.etzhayyim.com/rec/1", "did:web:kobo.etzhayyim.com:a1", "{}", 3, None)
    custody_count = (1,)  # need 2, only have 1

    with patch(
        "kotodama.myco_yeast_worker_main.fetch_one",
        side_effect=[spore, custody_count],
    ):
        from kotodama.myco_yeast_worker_main import task_kobo_germinate

        result = _run(task_kobo_germinate(spore_id="spr-abc123"))

    assert result["quorumMet"] is False
    assert result["required"] == 2


def test_germinate_quorum_met():
    spore = ("at://houshi.etzhayyim.com/rec/1", "did:web:kobo.etzhayyim.com:a1", "{}", 3, None)
    custody_count = (2,)  # 2 >= 3//2+1=2

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.myco_yeast_worker_main.fetch_one",
            side_effect=[spore, custody_count],
        ),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kobo_germinate

        result = _run(task_kobo_germinate(spore_id="spr-abc123"))

    assert result["quorumMet"] is True
    assert result["agentDid"] == "did:web:kobo.etzhayyim.com:a1"


# ─── task_kinoko_check_flow_threshold ────────────────────────────────────


def test_ponf_threshold_not_met():
    with patch(
        "kotodama.myco_yeast_worker_main.fetch_one",
        return_value=(50.0, 0.4, 3),  # flow=50 < 100
    ):
        from kotodama.myco_yeast_worker_main import task_kinoko_check_flow_threshold

        result = _run(task_kinoko_check_flow_threshold())

    assert result["thresholdMet"] is False
    assert result["totalFlow"] == 50.0


def test_ponf_threshold_met():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.myco_yeast_worker_main.fetch_one",
            side_effect=[
                (120.0, 0.75, 5),   # main query: flow=120>=100, eta=0.75>=0.5
                ("blk-old", "aabbcc"),  # prev block
            ],
        ),
        patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.myco_yeast_worker_main import task_kinoko_check_flow_threshold

        result = _run(task_kinoko_check_flow_threshold())

    assert result["thresholdMet"] is True
    assert result["blockId"].startswith("blk-")
    assert result["participantCount"] == 5


# ─── task_hakkou_create_ferment_record ────────────────────────────────────


def test_create_ferment_no_input_ref():
    from kotodama.myco_yeast_worker_main import task_hakkou_create_ferment_record

    result = _run(task_hakkou_create_ferment_record(input_ref=""))
    assert "error" in result


def test_create_ferment_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.myco_yeast_worker_main import task_hakkou_create_ferment_record

        result = _run(task_hakkou_create_ferment_record(
            input_kind="text",
            input_ref="raw signal content",
        ))

    assert result["fermentId"].startswith("fmnt-")
    assert result["status"] == "pending"


# ─── task_hakkou_llm_transform ────────────────────────────────────────────


def test_llm_transform_no_input_ref():
    from kotodama.myco_yeast_worker_main import task_hakkou_llm_transform

    result = _run(task_hakkou_llm_transform(ferment_id="fmnt-abc", input_ref=""))
    assert "error" in result


def test_llm_transform_success():
    mock_llm = MagicMock(return_value={
        "content": '{"summary":"test","entities":[],"category":"test","confidence":0.9}',
        "finish": "stop",
    })
    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.myco_yeast_worker_main import task_hakkou_llm_transform

        result = _run(task_hakkou_llm_transform(
            ferment_id="fmnt-abc",
            input_kind="text",
            input_ref="some raw signal to transform",
        ))

    assert result["fermentId"] == "fmnt-abc"
    assert result["ethanolHash"]
    assert len(result["ethanolHash"]) == 32


# ─── task_hakkou_finalize_ferment ─────────────────────────────────────────


def test_finalize_no_ferment_id():
    from kotodama.myco_yeast_worker_main import task_hakkou_finalize_ferment

    result = _run(task_hakkou_finalize_ferment(ferment_id=""))
    assert "error" in result


def test_finalize_success():
    mock_cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.myco_yeast_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.myco_yeast_worker_main import task_hakkou_finalize_ferment

        result = _run(task_hakkou_finalize_ferment(
            ferment_id="fmnt-abc",
            llmOutput="structured knowledge output",
            ethanolHash="deadbeef" * 4,
        ))

    assert result["fermentId"] == "fmnt-abc"
    assert result["co2AuditRef"].startswith("co2-")
    assert result["updated"] == 1
