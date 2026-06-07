"""Selector → endpoint resolution.

Pure function on ``(GpuSpec | None, model, FleetView)`` → ``ResolvedRoute``.
No HTTP traffic here; live dispatch lives in :mod:`kotoba_murakumo.client`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..exceptions import FleetUnreachable, MurakumoCompatNotImplemented
from ..fleet import FleetView, InferenceEndpoint
from ..gpu import Any as AnyGpu
from ..gpu import EvoX2, GpuSpec, MacMini, WebGPU


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    """Concrete dispatch target."""

    url: str
    model: str
    backend: str          # "litellm-gateway" | "evo-x2" | "mac-mini/<node>"
    kind: str             # "openai-compatible" | "ollama-native" | "comfyui-native"
    auth_bearer_env: str | None
    note: str = ""


def resolve(
    gpu: GpuSpec | str | None,
    model: str | None,
    fleet: FleetView,
    *,
    gateway_node: str = "judah",
) -> ResolvedRoute:
    """Resolve a routing decision deterministically.

    Rules (R0; see ADR-2605282000 §"Fleet routing policy"):

    1. ``gpu=gpu.MacMini(node=...)`` → that node's own-node Ollama at :11434.
    2. ``gpu=gpu.EvoX2(prefer=...)`` → EVO-X2 LiteLLM / Ollama / ComfyUI.
    3. ``gpu=gpu.WebGPU()`` → R2 not-yet-implemented.
    4. ``gpu=None`` / ``gpu="any"`` / ``gpu=gpu.Any()`` → judah LiteLLM gateway.
    5. Modal-string GPU → converted to a fleet selector via gpu.from_modal_string.
    """
    if isinstance(gpu, str):
        from ..gpu import from_modal_string
        gpu = from_modal_string(gpu)

    resolved_model = model or "gemma3:4b"

    if gpu is None or isinstance(gpu, AnyGpu):
        url = fleet.litellm_gateway_url(gateway_node=gateway_node)
        return ResolvedRoute(
            url=url,
            model=resolved_model,
            backend="litellm-gateway",
            kind="openai-compatible",
            # The judah-hosted LiteLLM gateway requires bearer auth (config:
            # 60-apps/etzhayyim-project-murakumo/litellm/config.yaml master_key:
            # os.environ/LITELLM_MASTER_KEY). Empirically verified 2026-05-28:
            # without this bearer, judah :4000 returns 401 Unauthorized
            # (ADR-2605282400 §"Routing fix"). The env var name is the
            # standard one used across the murakumo ansible role + litellm
            # daemon + every consumer Worker.
            auth_bearer_env="LITELLM_MASTER_KEY",
            note=f"routed to LiteLLM gateway on {gateway_node}",
        )

    if isinstance(gpu, MacMini):
        node = fleet.node(gpu.node)
        return ResolvedRoute(
            url=f"http://{node.ip_lan}:11434",
            model=resolved_model,
            backend=f"mac-mini/{node.name}",
            kind="ollama-native",
            auth_bearer_env=None,
            note=f"own-node Ollama on {node.name}",
        )

    if isinstance(gpu, EvoX2):
        ep: InferenceEndpoint = fleet.endpoint("evo-x2", gpu.prefer)
        return ResolvedRoute(
            url=ep.url,
            model=resolved_model,
            backend="evo-x2",
            kind=ep.api,
            auth_bearer_env=ep.master_key_env,
            note=f"EVO-X2 {gpu.prefer} backend",
        )

    if isinstance(gpu, WebGPU):
        raise MurakumoCompatNotImplemented(
            "gpu=WebGPU()",
            "WebGPU dispatch via kotoba-vm WASM Component lands R2 per ADR-2605282000",
        )

    raise FleetUnreachable(
        f"unrecognised GPU spec: {gpu!r}",
        attempted=[repr(gpu)],
    )


def bearer_token(route: ResolvedRoute) -> str | None:
    """Read the bearer token from the env var the fleet declared, if any."""
    if route.auth_bearer_env is None:
        return None
    val = os.environ.get(route.auth_bearer_env)
    return val if val else None
