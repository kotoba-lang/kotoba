"""Verify _pod_submit_and_wait sends curl-compatible UA and survives the
submit -> poll -> COMPLETED flow using an httpx MockTransport.

This test does not prove the RunPod proxy accepts the UA — only that the
client sends it. The end-to-end retry against the real proxy is tracked
in ADR 2605092345.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest


def _patch_client_factory(monkeypatch, transport: httpx.MockTransport) -> list[dict]:
    """Replace httpx.Client constructor so the function under test gets a
    client wired to our MockTransport. Returns a list that captures every
    request dict the mock observes (method, path, headers).
    """
    seen: list[dict] = []
    real_client = httpx.Client

    def _factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _factory)
    return seen


def test_pod_submit_and_wait_sends_curl_ua_and_completes(monkeypatch):
    monkeypatch.setenv("TRAINING_POD_BASE_URL", "https://pod.example/test")
    monkeypatch.setenv("TRAINING_POD_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TRAINING_POD_POLL_INTERVAL_SEC", "0")

    # Fresh import so module-level env reads pick up the monkeypatched values.
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    seen: list[dict] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append({
            "method": request.method,
            "url": str(request.url),
            "user_agent": request.headers.get("user-agent"),
            "authorization": request.headers.get("authorization"),
        })
        if request.method == "POST" and request.url.path.endswith("/train/run"):
            return httpx.Response(200, json={"id": "job-123", "status": "IN_QUEUE"})
        if request.method == "GET" and "/train/status/" in request.url.path:
            # First poll: IN_PROGRESS; second: COMPLETED.
            n = sum(1 for s in seen if s["method"] == "GET")
            if n == 1:
                return httpx.Response(200, json={"status": "IN_PROGRESS"})
            return httpx.Response(200, json={
                "status": "COMPLETED",
                "output": {"runId": "rw-row-1", "ok": True},
            })
        return httpx.Response(404, text="unexpected")

    transport = httpx.MockTransport(_handler)
    _patch_client_factory(monkeypatch, transport)

    out = tr._pod_submit_and_wait({"kind": "lora", "payload": {"foo": "bar"}})

    assert out == {"runId": "rw-row-1", "ok": True}
    # All requests must carry the curl-compatible UA + bearer.
    assert all(r["user_agent"] == "curl/8.7.1" for r in seen), seen
    assert all(r["authorization"] == "Bearer test-token" for r in seen), seen
    # No urllib remnants: at least 1 POST + 2 GET observed.
    methods = [r["method"] for r in seen]
    assert methods[0] == "POST"
    assert methods.count("GET") >= 2


def test_training_default_base_model_is_gemma_4_e4b(monkeypatch):
    monkeypatch.delenv("TRAINING_DEFAULT_BASE_MODEL", raising=False)
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)
    assert tr._TRAINING_DEFAULT_BASE_MODEL == "google/gemma-4-E4B"


def test_pod_submit_and_wait_surfaces_403_from_proxy(monkeypatch):
    monkeypatch.setenv("TRAINING_POD_BASE_URL", "https://pod.example/test")
    monkeypatch.setenv("TRAINING_POD_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TRAINING_POD_POLL_INTERVAL_SEC", "0")

    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="proxy says no")

    transport = httpx.MockTransport(_handler)
    _patch_client_factory(monkeypatch, transport)

    with pytest.raises(RuntimeError) as exc:
        tr._pod_submit_and_wait({"kind": "lora"})
    assert "HTTP 403" in str(exc.value)


def test_baien_lora_task_dispatches_baien_kind(monkeypatch):
    """task_train_baien_lora_run must produce kind='baien-lora' on the
    wire and default baseModel to the BitNet bf16 master when the caller
    omits it. ADR 2605092350."""
    monkeypatch.setenv("TRAINING_POD_BASE_URL", "https://pod.example/test")
    monkeypatch.setenv("TRAINING_POD_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TRAINING_POD_POLL_INTERVAL_SEC", "0")

    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    captured: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/train/run"):
            captured.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"id": "job-baien", "status": "IN_QUEUE"})
        return httpx.Response(200, json={
            "status": "COMPLETED",
            "output": {"runId": "rw-baien", "ok": True},
        })

    transport = httpx.MockTransport(_handler)
    _patch_client_factory(monkeypatch, transport)

    monkeypatch.setattr(tr, "_resolve_snapshot", lambda sid: {
        "snapshotId": sid, "datasetName": "ds-x", "label": "ds-x@v1",
    })

    out = tr.task_train_baien_lora_run(
        datasetSnapshotId="snap-1",
        hyperparams={"loraRank": 8},
    )

    assert out == {"runId": "rw-baien", "ok": True}
    inp = captured["input"]
    assert inp["kind"] == "baien-lora"
    assert inp["baseModel"] == "microsoft/bitnet-b1.58-2B-4T-bf16"
    assert inp["hyperparams"]["loraRank"] == 8


def test_baien_mx_task_dispatches_baien_mx_kind_and_modalities(monkeypatch):
    """task_train_baien_mx_run must produce kind='baien-mx-train',
    default baseModel to the BitNet bf16 master, and forward the
    declared `modalities` list verbatim. ADR 2605101000."""
    monkeypatch.setenv("TRAINING_POD_BASE_URL", "https://pod.example/test")
    monkeypatch.setenv("TRAINING_POD_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TRAINING_POD_POLL_INTERVAL_SEC", "0")

    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)

    captured: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/train/run"):
            captured.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"id": "job-mx", "status": "IN_QUEUE"})
        return httpx.Response(200, json={
            "status": "COMPLETED",
            "output": {
                "ok": True,
                "runId": "rw-mx",
                "modalities": ["triple", "vec768"],
                "fusionCheckpointId": "ckpt-fusion",
                "projectorCheckpoints": "{\"triple\":\"ckpt-t\",\"vec768\":\"ckpt-v\"}",
            },
        })

    transport = httpx.MockTransport(_handler)
    _patch_client_factory(monkeypatch, transport)
    monkeypatch.setattr(tr, "_resolve_snapshot", lambda sid: {
        "snapshotId": sid, "datasetName": "ds-mx", "label": "ds-mx@v1",
    })

    out = tr.task_train_baien_mx_run(
        datasetSnapshotId="snap-mm-1",
        modalities=["triple", "vec768"],
        hyperparams={"learningRate": 1e-3},
        fusionLayerIndex=15,
        trunkFrozen=True,
    )

    assert out["ok"] is True
    assert out["modalities"] == ["triple", "vec768"]
    inp = captured["input"]
    assert inp["kind"] == "baien-mx-train"
    assert inp["baseModel"] == "microsoft/bitnet-b1.58-2B-4T-bf16"
    assert inp["modalities"] == ["triple", "vec768"]
    assert inp["fusionLayerIndex"] == 15
    assert inp["trunkFrozen"] is True
    assert inp["hyperparams"]["learningRate"] == 1e-3


def test_default_base_models(monkeypatch):
    """Oka (Gemma 4 E4B) and Baien (BitNet b1.58 2B 4T bf16) trunk
    defaults must remain wired to the canonical HF IDs. ADR 2605092345
    pins Oka; ADR 2605092350 pins Baien."""
    monkeypatch.delenv("TRAINING_DEFAULT_BASE_MODEL", raising=False)
    monkeypatch.delenv("BAIEN_DEFAULT_TRUNK_MODEL", raising=False)
    import importlib
    import kotodama.primitives.training_run as tr
    importlib.reload(tr)
    assert tr._TRAINING_DEFAULT_BASE_MODEL == "google/gemma-4-E4B"
    assert tr._BAIEN_DEFAULT_TRUNK_MODEL == "microsoft/bitnet-b1.58-2B-4T-bf16"
