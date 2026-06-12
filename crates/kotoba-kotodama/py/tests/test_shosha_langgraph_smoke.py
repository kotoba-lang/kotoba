from __future__ import annotations

import json

from kotodama import shosha_langgraph_smoke as smoke


def test_config_from_env_defaults(monkeypatch) -> None:
    monkeypatch.delenv("SHOSHA_LANGGRAPH_SMOKE_DISPATCHER_URL", raising=False)
    monkeypatch.delenv("DISPATCHER_INTERNAL_SECRET", raising=False)
    monkeypatch.delenv("SHOSHA_LANGGRAPH_SMOKE_TIER", raising=False)

    config = smoke.config_from_env()

    assert config.dispatcher_url == "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080"
    assert config.internal_trust == ""
    assert config.tier == "fast"


def test_headers_include_internal_trust_when_present() -> None:
    config = smoke.SmokeConfig(dispatcher_url="http://dispatcher", internal_trust="secret")

    headers = smoke._headers(config)

    assert headers["x-internal-trust"] == "secret"
    assert headers["user-agent"] == smoke.USER_AGENT


def test_find_binding_returns_matching_nsid() -> None:
    payload = {
        "bindings": [
            {"nsid": "com.etzhayyim.apps.other", "routingTarget": "zeebe"},
            {"nsid": smoke.NSID, "routingTarget": "langgraph"},
        ]
    }

    assert smoke._find_binding(payload) == {"nsid": smoke.NSID, "routingTarget": "langgraph"}


def test_assert_binding_is_langgraph_accepts_canary(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "_request_json",
        lambda **kwargs: {
            "bindings": [
                {
                    "nsid": smoke.NSID,
                    "routingTarget": "langgraph",
                    "bpmnProcessId": smoke.ASSISTANT_ID,
                }
            ]
        },
    )

    binding = smoke.assert_binding_is_langgraph(smoke.SmokeConfig(dispatcher_url="http://d"))

    assert binding["routingTarget"] == "langgraph"


def test_assert_binding_is_langgraph_rejects_zeebe(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "_request_json",
        lambda **kwargs: {
            "bindings": [
                {
                    "nsid": smoke.NSID,
                    "routingTarget": "zeebe",
                    "bpmnProcessId": smoke.ASSISTANT_ID,
                }
            ]
        },
    )

    try:
        smoke.assert_binding_is_langgraph(smoke.SmokeConfig(dispatcher_url="http://d"))
    except RuntimeError as exc:
        assert "routingTarget" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_agent_loop_builds_identity_payload(monkeypatch) -> None:
    calls = {}

    def fake_request_json(**kwargs):
        calls.update(kwargs)
        return {
            "_httpStatus": 202,
            "assistant_id": smoke.ASSISTANT_ID,
            "run_id": "run-1",
            "thread_id": "thread-1",
            "status": "pending",
        }

    monkeypatch.setattr(smoke, "_request_json", fake_request_json)

    out = smoke.dispatch_agent_loop(smoke.SmokeConfig(dispatcher_url="http://d"), now=123)

    assert out["run_id"] == "run-1"
    assert calls["url"] == f"http://d/xrpc/{smoke.NSID}"
    assert calls["payload"]["actorDid"] == smoke.ACTOR_DID
    assert calls["payload"]["threadId"] == "shosha-langgraph-smoke-123"
    assert calls["payload"]["tier"] == "fast"


def test_run_smoke_returns_compact_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "assert_binding_is_langgraph",
        lambda config: {"routingTarget": "langgraph"},
    )
    monkeypatch.setattr(
        smoke,
        "dispatch_agent_loop",
        lambda config: {"run_id": "run-1", "thread_id": "thread-1", "status": "pending"},
    )

    out = smoke.run_smoke(smoke.SmokeConfig(dispatcher_url="http://d"))

    assert out == {
        "ok": True,
        "nsid": smoke.NSID,
        "assistantId": smoke.ASSISTANT_ID,
        "routingTarget": "langgraph",
        "runId": "run-1",
        "threadId": "thread-1",
        "status": "pending",
        "dispatcherUrl": "http://d",
    }


def test_main_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        smoke,
        "run_smoke",
        lambda config: {"ok": True, "dispatcherUrl": config.dispatcher_url},
    )
    monkeypatch.setenv("SHOSHA_LANGGRAPH_SMOKE_DISPATCHER_URL", "http://dispatcher/")

    smoke.main()

    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "dispatcherUrl": "http://dispatcher",
    }
