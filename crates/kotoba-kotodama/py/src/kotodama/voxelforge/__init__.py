"""voxelforge — LangGraph 3D design pipeline (ADR-2605080700).

Public API surface for the voxelforge actor:

  - :class:`VoxelforgeState`     — Pydantic v2 StateGraph state (ADR-2605080200)
  - :func:`build_graph`          — compiled LangGraph StateGraph
  - :func:`build_app`            — Granian-ready FastAPI app exposing
                                   `/runs`, `/runs/{id}`, `/health`,
                                   `/_app/meta` per ADR-2605080600.
  - :func:`register_xrpc_handlers` — bpmn-dispatcher XRPC bridge
                                     (`com.etzhayyim.apps.voxelforge.*` →
                                     graph invocation).

Deployment: `kotodama.voxelforge.server:app` is the canonical Granian
ASGI target. Image: `ghcr.io/etzhayyim/kotodama:<tag>-amd64` (same
image as the Zeebe worker; profile-branched in `__main__.py` and via
`VOXELFORGE_RUNTIME=langgraph` env var).
"""

from kotodama.voxelforge.state import (  # noqa: F401
    VoxelforgeState,
    GenerateInput,
    Artifact,
    DesignKind,
    TargetFormat,
)
from kotodama.voxelforge.graph import build_graph  # noqa: F401

__all__ = [
    "VoxelforgeState",
    "GenerateInput",
    "Artifact",
    "DesignKind",
    "TargetFormat",
    "build_graph",
]
