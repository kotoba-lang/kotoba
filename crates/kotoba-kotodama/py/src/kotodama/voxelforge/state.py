"""Pydantic v2 state contract for the voxelforge LangGraph (ADR-2605080200).

All boundary IO (XRPC body, LangGraph state, Anthropic tool_use) is
type-checked here. Internal hot-path code consumes only validated
``BaseModelState``-derived structs.
"""

from __future__ import annotations

import enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class DesignKind(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    CAD = "cad"


class TargetFormat(str, enum.Enum):
    GLB = "glb"
    VOX = "vox"
    BOTH = "both"


class GenerateInput(BaseModel):
    """Body of `com.etzhayyim.apps.voxelforge.generate` (Pydantic-validated).

    The CF Worker forwards the parsed JSON body verbatim; this model is
    the canonical wire-format contract.
    """

    kind: DesignKind
    prompt: Optional[str] = Field(default=None, max_length=4000)
    image_url: Optional[str] = Field(default=None, alias="imageUrl")
    cad_code: Optional[str] = Field(default=None, alias="cadCode", max_length=32_000)
    reference_artifact_id: Optional[str] = Field(default=None, alias="referenceArtifactId")
    target_format: TargetFormat = Field(alias="targetFormat")
    target_voxel_dim: int = Field(default=64, ge=8, le=256, alias="targetVoxelDim")
    palette: Optional[list[str]] = Field(default=None, max_length=256)
    params: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class Artifact(BaseModel):
    """One materialized artifact (matching `vertex_voxelforge_artifact`)."""

    vertex_id: str
    design_vertex_id: str
    run_vertex_id: str
    format: str  # "glb" | "vox" | "voxel_grid_json" | "manifest_json"
    b2_bucket: str
    b2_key: str
    sha256_hex: str
    byte_size: int
    voxel_dim: Optional[int] = None
    polygon_count: Optional[int] = None
    vertex_count: Optional[int] = None
    generated_by: str  # "trellis" | "comfy3d" | "cadquery"
    ts_ms: int


def _merge_artifacts(left: list[Artifact], right: list[Artifact]) -> list[Artifact]:
    """LangGraph reducer: append-only, dedupe by ``(format, sha256_hex)``."""

    seen: set[tuple[str, str]] = {(a.format, a.sha256_hex) for a in left}
    out = list(left)
    for a in right:
        key = (a.format, a.sha256_hex)
        if key not in seen:
            out.append(a)
            seen.add(key)
    return out


class VoxelforgeState(BaseModel):
    """LangGraph Pregel state for the voxelforge graph.

    Single-step nodes mutate this in-place via ``return {"field": value}``
    (LangGraph merge semantics).  ``artifacts`` uses a custom reducer to
    accumulate across nodes.
    """

    # ── input (set once at START) ──
    input: GenerateInput
    actor_did: str
    org_did: str
    design_vertex_id: str
    run_id: str
    started_at: str  # ISO 8601

    # ── parsed/normalized after parse_input ──
    prompt_hash: Optional[str] = None
    spec: dict = Field(default_factory=dict)

    # ── route_generator decision ──
    generator: Optional[str] = None  # "trellis" | "comfy3d" | "cadquery"

    # ── intermediate mesh (post-generate, pre-export) ──
    mesh_b64: Optional[str] = None  # base64 of intermediate .glb bytes
    mesh_polygon_count: Optional[int] = None
    mesh_vertex_count: Optional[int] = None

    # ── voxelization output ──
    voxel_grid_b64: Optional[str] = None  # base64 of voxel_grid.json
    voxel_dim_actual: Optional[int] = None

    # ── final artifact records ──
    artifacts: Annotated[list[Artifact], _merge_artifacts] = Field(default_factory=list)

    # ── status / error ──
    current_node: Optional[str] = None
    error_text: Optional[str] = None

    # ── cost accounting ──
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    gpu_seconds: float = 0.0
    cost_jpy_micro: int = 0
