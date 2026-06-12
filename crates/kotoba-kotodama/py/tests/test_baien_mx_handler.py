"""Pod-side handler tests for kind='baien-mx-train' (ADR 2605101000).

These cover validation paths that do not need a live RW connection.
The full happy path (RW INSERTs + per-modality checkpoint placeholders)
is exercised end-to-end on the H100 pod itself in step 5/6.
"""

from __future__ import annotations

import pytest


def test_run_baien_mx_rejects_unknown_modality(monkeypatch):
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    with pytest.raises(ValueError, match="unknown Baien-MX modality"):
        tr._run_baien_mx(
            runId="r1",
            baseModel="microsoft/bitnet-b1.58-2B-4T-bf16",
            baseModelRevision="main",
            datasetSnapshotId="snap",
            modalities=["triple", "definitely-not-a-modality"],
            fusionLayerIndex=15,
            trunkFrozen=True,
            loraOverFirst4Layers=False,
            hyperparams={},
            gpuTarget=None,
            seed=None,
            triggeredBy=None,
            bpmnProcessInstanceKey=None,
        )


def test_run_baien_mx_rejects_empty_modalities(monkeypatch):
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    with pytest.raises(ValueError, match="at least one"):
        tr._run_baien_mx(
            runId="r2",
            baseModel="microsoft/bitnet-b1.58-2B-4T-bf16",
            baseModelRevision="main",
            datasetSnapshotId="snap",
            modalities=[],
            fusionLayerIndex=15,
            trunkFrozen=True,
            loraOverFirst4Layers=False,
            hyperparams={},
            gpuTarget=None,
            seed=None,
            triggeredBy=None,
            bpmnProcessInstanceKey=None,
        )


def test_runpod_handler_dispatches_baien_mx_kind(monkeypatch):
    """Confirm runpod_handler routes kind='baien-mx-train' to
    _run_baien_mx. Validation rejection from _run_baien_mx is the
    cheapest signal that the dispatch path is wired."""
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    with pytest.raises(ValueError, match="unknown Baien-MX modality"):
        tr.runpod_handler({
            "input": {
                "kind": "baien-mx-train",
                "datasetSnapshotId": "snap",
                "modalities": ["bogus"],
            },
        })


def test_runpod_handler_unknown_kind_returns_error_dict(monkeypatch):
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    out = tr.runpod_handler({"input": {"kind": "definitely-not-a-kind"}})
    assert out["ok"] is False
    assert "unknown training kind" in out["error"]
