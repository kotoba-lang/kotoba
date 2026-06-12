"""fleet.toml loader.

The fleet is the SSoT (ADR-2605215000 + ADR-2605282000). This module reads it
once and exposes a typed view; it never invents endpoints not in the file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import FleetUnreachable


@dataclass(frozen=True, slots=True)
class FleetNode:
    """One Mac mini node from ``[[nodes]]``."""

    name: str
    hostname: str
    ip_lan: str
    ip_tailscale: str
    role: str
    cells: tuple[str, ...]

    @property
    def stable_ip(self) -> str:
        """Prefer tailnet reachability; keep LAN as a local fallback."""
        return self.ip_tailscale or self.ip_lan


@dataclass(frozen=True, slots=True)
class InferenceEndpoint:
    """One row from ``[inference_backends.<name>.endpoints.<kind>]``."""

    backend: str  # "evo-x2"
    kind: str     # "ollama" | "litellm" | "comfyui"
    url: str
    api: str
    auth: str
    master_key_env: str | None = None
    models: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FleetView:
    """Read-only typed view over fleet.toml."""

    path: Path
    name: str
    nodes: dict[str, FleetNode] = field(default_factory=dict)
    endpoints: dict[tuple[str, str], InferenceEndpoint] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def node(self, name: str) -> FleetNode:
        try:
            return self.nodes[name]
        except KeyError:
            raise FleetUnreachable(
                f"node {name!r} not in fleet {self.name!r}",
                attempted=[name],
            ) from None

    def endpoint(self, backend: str, kind: str) -> InferenceEndpoint:
        try:
            return self.endpoints[(backend, kind)]
        except KeyError:
            raise FleetUnreachable(
                f"endpoint {backend}/{kind} not in fleet {self.name!r}",
                attempted=[f"{backend}/{kind}"],
            ) from None

    def litellm_gateway_url(self, *, gateway_node: str = "judah") -> str:
        """Resolve the LiteLLM gateway URL.

        Per CLAUDE.md substrate boundary: the LiteLLM gateway lives on judah.
        Use the tailnet address when present because LAN addresses drift across
        reboot/reconnect events.
        """
        try:
            node = self.node(gateway_node)
        except FleetUnreachable as e:
            raise FleetUnreachable(
                f"LiteLLM gateway node {gateway_node!r} not in fleet",
                attempted=e.attempted,
            ) from None
        return f"http://{node.stable_ip}:4000"


def load(path: str | Path) -> FleetView:
    """Parse fleet.toml and return a typed view.

    Raises ``FleetUnreachable`` if the file is missing — there is no implicit
    fallback per ADR-2605282000 N4.
    """
    p = Path(path)
    if not p.exists():
        raise FleetUnreachable(
            f"fleet.toml not found at {p}; refusing to route anywhere else "
            "per ADR-2605215000 + ADR-2605282000",
            attempted=[str(p)],
        )

    with p.open("rb") as f:
        raw = tomllib.load(f)

    fleet_block = raw.get("fleet", {})
    name = fleet_block.get("name", p.stem)

    nodes: dict[str, FleetNode] = {}
    for n in raw.get("nodes", []):
        node = FleetNode(
            name=n["name"],
            hostname=n.get("hostname", ""),
            ip_lan=n.get("ip_lan", ""),
            ip_tailscale=n.get("ip_tailscale", ""),
            role=n.get("role", ""),
            cells=tuple(n.get("cells", [])),
        )
        nodes[node.name] = node

    endpoints: dict[tuple[str, str], InferenceEndpoint] = {}
    # fleet.toml writes each backend as ``[[inference_backends]]`` (array)
    # immediately followed by ``[inference_backends.<name>.endpoints.<kind>]``
    # blocks. tomllib resolves the latter into a sub-table whose key is the
    # backend name *inside the array element*, e.g.::
    #
    #   raw["inference_backends"][0]["evo-x2"]["endpoints"]["litellm"] = {...}
    #
    # so we walk that shape rather than expecting a separate top-level dict.
    for backend_block in raw.get("inference_backends", []):
        backend = backend_block.get("name")
        if not backend:
            continue
        nested = backend_block.get(backend, {})
        for kind, cfg in nested.get("endpoints", {}).items():
            endpoints[(backend, kind)] = InferenceEndpoint(
                backend=backend,
                kind=kind,
                url=cfg["url"],
                api=cfg.get("api", "openai-compatible"),
                auth=cfg.get("auth", "lan-only"),
                master_key_env=cfg.get("master_key_env"),
                models=tuple(cfg.get("models", [])),
            )

    return FleetView(
        path=p.resolve(),
        name=name,
        nodes=nodes,
        endpoints=endpoints,
        raw=raw,
    )
