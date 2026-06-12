"""Compatibility registration shim for legacy task modules.

The runtime target is pod-side LangServer through AgentGateway MCP. Some older
modules still expose handlers through a worker.task(...) decorator shape; this
shim preserves that registration API without importing a broker client.
"""

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException
import uvicorn


class LangServerJob:
    def __init__(self, variables: dict[str, Any] | None = None) -> None:
        self.variables = variables or {}


def create_langserver_channel(*_: Any, **__: Any) -> None:
    return None


class LangServerWorker:
    def __init__(self, _channel: Any = None, *, name: str = "langserver-worker") -> None:
        self.name = name
        self.handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def task(self, *, task_type: str, **_: Any) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self.handlers[task_type] = fn
            return fn

        return decorator

    async def work(self) -> None:
        port = int(os.environ.get("PORT", os.environ.get("HEALTH_PORT", "8080")))
        agentgateway_mcp_url = os.environ.get(
            "AGENTGATEWAY_MCP_URL",
            "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080",
        )
        app = FastAPI(title=self.name, version="1.0.0")

        @app.get("/healthz")
        async def healthz() -> dict[str, Any]:
            return {
                "ok": True,
                "runtimeKind": "k8s-langserver",
                "agentGatewayMcpUrl": agentgateway_mcp_url,
                "tools": sorted(self.handlers),
            }

        @app.get("/tools")
        async def tools() -> dict[str, Any]:
            return {"tools": [{"name": name, "runtime": "langserver"} for name in sorted(self.handlers)]}

        async def invoke_tool(name: str, arguments: dict[str, Any]) -> Any:
            handler = self.handlers.get(name)
            if handler is None:
                raise HTTPException(status_code=404, detail=f"unknown tool: {name}")
            return await handler(**arguments)

        @app.post("/invoke")
        async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
            name = str(payload.get("name") or payload.get("tool") or "")
            arguments = payload.get("arguments") or payload.get("input") or {}
            if not isinstance(arguments, dict):
                raise HTTPException(status_code=400, detail="arguments must be an object")
            return {"ok": True, "name": name, "result": await invoke_tool(name, arguments)}

        @app.post("/runs")
        async def runs(payload: dict[str, Any]) -> dict[str, Any]:
            assistant_id = str(payload.get("assistant_id") or "")
            arguments = payload.get("input") or payload.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise HTTPException(status_code=400, detail="input must be an object")
            return {"status": "completed", "assistant_id": assistant_id, "output": await invoke_tool(assistant_id, arguments)}

        await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")).serve()
