"""Smoke test for the shosha.agentLoop LangGraph canary route.

This is intentionally dispatcher-facing. It verifies the rollout contract:

1. /bindings exposes com.etzhayyim.apps.shosha.agentLoop as routingTarget=langgraph.
2. /xrpc/com.etzhayyim.apps.shosha.agentLoop returns a LangGraph async run handle.

It does not require direct RisingWave access and does not assume the caller can
reach the LangGraph Server service directly.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

NSID = "com.etzhayyim.apps.shosha.agentLoop"
ASSISTANT_ID = "shosha_agent_loop"
ACTOR_DID = "did:web:shosha.etzhayyim.com"
USER_AGENT = "shosha-langgraph-smoke/1 (+https://shosha.etzhayyim.com)"


@dataclass(frozen=True)
class SmokeConfig:
    dispatcher_url: str
    internal_trust: str = ""
    prompt: str = "LangGraph canary smoke: summarize current shosha route status in one sentence."
    tier: str = "fast"
    max_tokens: int = 160
    timeout_sec: float = 30.0


def config_from_env() -> SmokeConfig:
    return SmokeConfig(
        dispatcher_url=os.environ.get(
            "SHOSHA_LANGGRAPH_SMOKE_DISPATCHER_URL",
            "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
        ).rstrip("/"),
        internal_trust=os.environ.get("DISPATCHER_INTERNAL_SECRET", ""),
        prompt=os.environ.get(
            "SHOSHA_LANGGRAPH_SMOKE_PROMPT",
            "LangGraph canary smoke: summarize current shosha route status in one sentence.",
        ),
        tier=os.environ.get("SHOSHA_LANGGRAPH_SMOKE_TIER", "fast"),
        max_tokens=int(os.environ.get("SHOSHA_LANGGRAPH_SMOKE_MAX_TOKENS", "160")),
        timeout_sec=float(os.environ.get("SHOSHA_LANGGRAPH_SMOKE_TIMEOUT_SEC", "30")),
    )


def _headers(config: SmokeConfig) -> dict[str, str]:
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": USER_AGENT,
    }
    if config.internal_trust:
        headers["x-internal-trust"] = config.internal_trust
    return headers


def _request_json(
    *,
    url: str,
    config: SmokeConfig,
    payload: dict[str, Any] | None = None,
    method: str = "GET",
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=_headers(config))
    try:
        with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError(f"{url} returned non-object JSON")
            parsed["_httpStatus"] = resp.status
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body[:500]}") from exc


def _find_binding(bindings_payload: dict[str, Any]) -> dict[str, Any] | None:
    bindings = bindings_payload.get("bindings")
    if not isinstance(bindings, list):
        return None
    for row in bindings:
        if isinstance(row, dict) and row.get("nsid") == NSID:
            return row
    return None


def assert_binding_is_langgraph(config: SmokeConfig) -> dict[str, Any]:
    payload = _request_json(url=f"{config.dispatcher_url}/bindings", config=config)
    binding = _find_binding(payload)
    if not binding:
        raise RuntimeError(f"{NSID} binding not found")
    if binding.get("routingTarget") != "langgraph":
        raise RuntimeError(f"{NSID} routingTarget={binding.get('routingTarget')!r}, want 'langgraph'")
    if binding.get("bpmnProcessId") != ASSISTANT_ID:
        raise RuntimeError(
            f"{NSID} bpmnProcessId={binding.get('bpmnProcessId')!r}, want {ASSISTANT_ID!r}"
        )
    return binding


def dispatch_agent_loop(config: SmokeConfig, now: int | None = None) -> dict[str, Any]:
    thread_suffix = now if now is not None else int(time.time())
    body = {
        "actorDid": ACTOR_DID,
        "threadId": f"shosha-langgraph-smoke-{thread_suffix}",
        "prompt": config.prompt,
        "tier": config.tier,
        "maxTokens": config.max_tokens,
    }
    payload = _request_json(
        url=f"{config.dispatcher_url}/xrpc/{NSID}",
        config=config,
        payload=body,
        method="POST",
    )
    if payload.get("_httpStatus") != 202:
        raise RuntimeError(f"expected HTTP 202 from dispatcher, got {payload.get('_httpStatus')}")
    if payload.get("assistant_id") != ASSISTANT_ID:
        raise RuntimeError(f"assistant_id={payload.get('assistant_id')!r}, want {ASSISTANT_ID!r}")
    if not payload.get("run_id"):
        raise RuntimeError(f"dispatcher response missing run_id: {payload}")
    return payload


def run_smoke(config: SmokeConfig) -> dict[str, Any]:
    binding = assert_binding_is_langgraph(config)
    run = dispatch_agent_loop(config)
    return {
        "ok": True,
        "nsid": NSID,
        "assistantId": ASSISTANT_ID,
        "routingTarget": binding.get("routingTarget"),
        "runId": run.get("run_id"),
        "threadId": run.get("thread_id"),
        "status": run.get("status"),
        "dispatcherUrl": config.dispatcher_url,
    }


def main() -> None:
    print(json.dumps(run_smoke(config_from_env()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
