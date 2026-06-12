"""LangGraph StateGraph for voxelforge (ADR-2605080700).

7-node Pregel pipeline:

    parse_input
        ↓
    route_generator
       ┌──┴──────────────────┐
       ▼                     ▼                     ▼
    generate_trellis    generate_comfy3d    exec_cadquery
       └──┬──────────────────┘                     │
          ▼                                        │
    post_process_mesh ◀───────────────────────────┘
          ▼
    voxelize
          ▼
    export_artifacts
          ▼
    register_artifact
          ▼
        END

Per ADR-2605080600 the graph runs inside Granian/LangGraph Server with
checkpoint persistence in ``vertex_voxelforge_run.checkpoint_json``
(custom ``BaseCheckpointSaver`` over RisingWave).  HITL via
``interrupt()`` is not used in Phase A — generation is one-shot.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from kotodama.voxelforge.state import (
    Artifact,
    DesignKind,
    GenerateInput,
    TargetFormat,
    VoxelforgeState,
)

try:  # langgraph 0.2.x
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover — runtime image always has it
    StateGraph = None  # type: ignore[assignment]
    END = "__END__"


# ── node implementations ─────────────────────────────────────────────


def parse_input(state: VoxelforgeState) -> dict[str, Any]:
    inp = state.input
    spec: dict[str, Any] = {
        "kind": inp.kind.value,
        "target_format": inp.target_format.value,
        "target_voxel_dim": inp.target_voxel_dim,
    }
    if inp.kind is DesignKind.TEXT:
        if not inp.prompt:
            return {"error_text": "prompt required when kind=text", "current_node": "parse_input"}
        spec["prompt"] = inp.prompt
        prompt_hash = hashlib.sha256(inp.prompt.encode()).hexdigest()
    elif inp.kind is DesignKind.IMAGE:
        if not inp.image_url:
            return {"error_text": "imageUrl required when kind=image", "current_node": "parse_input"}
        spec["image_url"] = inp.image_url
        prompt_hash = hashlib.sha256(inp.image_url.encode()).hexdigest()
    elif inp.kind is DesignKind.CAD:
        if not inp.cad_code:
            return {"error_text": "cadCode required when kind=cad", "current_node": "parse_input"}
        spec["cad_code"] = inp.cad_code
        prompt_hash = hashlib.sha256(inp.cad_code.encode()).hexdigest()
    else:  # pragma: no cover
        return {"error_text": f"unknown kind={inp.kind!r}", "current_node": "parse_input"}

    if inp.palette:
        spec["palette"] = inp.palette
    if inp.params:
        spec["params"] = inp.params
    if inp.reference_artifact_id:
        spec["reference_artifact_id"] = inp.reference_artifact_id
    return {"spec": spec, "prompt_hash": prompt_hash, "current_node": "parse_input"}


def route_generator(state: VoxelforgeState) -> dict[str, Any]:
    """Pick which generator node to run next based on input kind."""

    if state.error_text:
        return {"current_node": "route_generator"}
    kind = state.input.kind
    override = (state.input.params or {}).get("generator")  # type: ignore[union-attr]
    if override in {"trellis", "comfy3d", "cadquery"}:
        return {"generator": override, "current_node": "route_generator"}
    if kind is DesignKind.TEXT:
        return {"generator": "trellis", "current_node": "route_generator"}
    if kind is DesignKind.IMAGE:
        # Phase A default: TRELLIS for image too. ComfyUI 3D-Pack is
        # operator opt-in via params.generator="comfy3d".
        return {"generator": "trellis", "current_node": "route_generator"}
    if kind is DesignKind.CAD:
        return {"generator": "cadquery", "current_node": "route_generator"}
    return {"error_text": "no generator route", "current_node": "route_generator"}


def _branch_router(state: VoxelforgeState) -> str:
    if state.error_text:
        return "post_process_mesh"  # surface error downstream
    return state.generator or "generate_trellis"


def generate_trellis(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.runpod_client import call_trellis

    t0 = time.monotonic()
    glb_bytes, polys, verts = call_trellis(
        prompt=state.spec.get("prompt"),
        image_url=state.spec.get("image_url"),
        params=state.spec.get("params") or {},
    )
    return {
        "mesh_b64": _b64(glb_bytes),
        "mesh_polygon_count": polys,
        "mesh_vertex_count": verts,
        "gpu_seconds": time.monotonic() - t0,
        "current_node": "generate_trellis",
    }


def generate_comfy3d(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.runpod_client import call_comfyui_3d

    t0 = time.monotonic()
    glb_bytes, polys, verts = call_comfyui_3d(
        image_url=state.spec.get("image_url"),
        params=state.spec.get("params") or {},
    )
    return {
        "mesh_b64": _b64(glb_bytes),
        "mesh_polygon_count": polys,
        "mesh_vertex_count": verts,
        "gpu_seconds": time.monotonic() - t0,
        "current_node": "generate_comfy3d",
    }


def exec_cadquery(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.converters import cadquery_to_glb

    t0 = time.monotonic()
    glb_bytes, polys, verts = cadquery_to_glb(cad_code=state.spec["cad_code"])
    return {
        "mesh_b64": _b64(glb_bytes),
        "mesh_polygon_count": polys,
        "mesh_vertex_count": verts,
        "gpu_seconds": 0.0,
        "current_node": "exec_cadquery",
    }


def post_process_mesh(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.converters import decimate_glb

    if state.error_text or not state.mesh_b64:
        return {"current_node": "post_process_mesh"}
    raw = _b64d(state.mesh_b64)
    decimated, polys, verts = decimate_glb(raw, target_polys=20_000)
    return {
        "mesh_b64": _b64(decimated),
        "mesh_polygon_count": polys,
        "mesh_vertex_count": verts,
        "current_node": "post_process_mesh",
    }


def voxelize(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.converters import glb_to_voxel_grid_json

    if state.error_text or state.input.target_format is TargetFormat.GLB:
        return {"current_node": "voxelize"}
    if not state.mesh_b64:
        return {"error_text": "no mesh to voxelize", "current_node": "voxelize"}
    grid_json, dim = glb_to_voxel_grid_json(
        glb_bytes=_b64d(state.mesh_b64),
        target_dim=state.input.target_voxel_dim,
        palette=state.spec.get("palette"),
    )
    return {
        "voxel_grid_b64": _b64(grid_json.encode()),
        "voxel_dim_actual": dim,
        "current_node": "voxelize",
    }


def export_artifacts(state: VoxelforgeState) -> dict[str, Any]:
    from kotodama.voxelforge.converters import (
        b2_put,
        voxel_grid_json_to_vox_bytes,
    )

    if state.error_text:
        return {"current_node": "export_artifacts"}

    bucket = os.environ.get("VOXELFORGE_B2_BUCKET", "etzhayyim-nats")
    out: list[Artifact] = []
    ts_ms = int(time.time() * 1000)
    design_id = state.design_vertex_id
    run_id = state.run_id
    base = f"voxelforge/v1/{state.actor_did}/{state.run_id}"
    target = state.input.target_format

    # 1. .glb
    if target in (TargetFormat.GLB, TargetFormat.BOTH) and state.mesh_b64:
        glb = _b64d(state.mesh_b64)
        sha = _sha256(glb)
        key = f"{base}/model.glb"
        b2_put(bucket, key, glb, "model/gltf-binary")
        out.append(
            Artifact(
                vertex_id=f"at://{state.actor_did}/com.etzhayyim.apps.voxelforge.artifact/{sha[:16]}-glb",
                design_vertex_id=design_id,
                run_vertex_id=run_id,
                format="glb",
                b2_bucket=bucket,
                b2_key=key,
                sha256_hex=sha,
                byte_size=len(glb),
                polygon_count=state.mesh_polygon_count,
                vertex_count=state.mesh_vertex_count,
                generated_by=state.generator or "unknown",
                ts_ms=ts_ms,
            )
        )

    # 2. voxel_grid.json + .vox
    if target in (TargetFormat.VOX, TargetFormat.BOTH) and state.voxel_grid_b64:
        grid_json_bytes = _b64d(state.voxel_grid_b64)
        sha_g = _sha256(grid_json_bytes)
        key_g = f"{base}/voxel_grid.json"
        b2_put(bucket, key_g, grid_json_bytes, "application/json")
        out.append(
            Artifact(
                vertex_id=f"at://{state.actor_did}/com.etzhayyim.apps.voxelforge.artifact/{sha_g[:16]}-grid",
                design_vertex_id=design_id,
                run_vertex_id=run_id,
                format="voxel_grid_json",
                b2_bucket=bucket,
                b2_key=key_g,
                sha256_hex=sha_g,
                byte_size=len(grid_json_bytes),
                voxel_dim=state.voxel_dim_actual,
                generated_by=state.generator or "unknown",
                ts_ms=ts_ms,
            )
        )
        vox_bytes = voxel_grid_json_to_vox_bytes(grid_json_bytes)
        sha_v = _sha256(vox_bytes)
        key_v = f"{base}/model.vox"
        b2_put(bucket, key_v, vox_bytes, "application/octet-stream")
        out.append(
            Artifact(
                vertex_id=f"at://{state.actor_did}/com.etzhayyim.apps.voxelforge.artifact/{sha_v[:16]}-vox",
                design_vertex_id=design_id,
                run_vertex_id=run_id,
                format="vox",
                b2_bucket=bucket,
                b2_key=key_v,
                sha256_hex=sha_v,
                byte_size=len(vox_bytes),
                voxel_dim=state.voxel_dim_actual,
                generated_by=state.generator or "unknown",
                ts_ms=ts_ms,
            )
        )

    # 3. manifest.json (always)
    manifest = {
        "designVertexId": design_id,
        "runId": run_id,
        "actorDid": state.actor_did,
        "kind": state.input.kind.value,
        "generator": state.generator,
        "targetFormat": state.input.target_format.value,
        "voxelDim": state.voxel_dim_actual,
        "tsMs": ts_ms,
        "artifacts": [a.model_dump(mode="json") for a in out],
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    sha_m = _sha256(manifest_bytes)
    key_m = f"{base}/manifest.json"
    b2_put(bucket, key_m, manifest_bytes, "application/json")
    out.append(
        Artifact(
            vertex_id=f"at://{state.actor_did}/com.etzhayyim.apps.voxelforge.artifact/{sha_m[:16]}-mf",
            design_vertex_id=design_id,
            run_vertex_id=run_id,
            format="manifest_json",
            b2_bucket=bucket,
            b2_key=key_m,
            sha256_hex=sha_m,
            byte_size=len(manifest_bytes),
            generated_by=state.generator or "unknown",
            ts_ms=ts_ms,
        )
    )

    return {"artifacts": out, "current_node": "export_artifacts"}


def register_artifact(state: VoxelforgeState) -> dict[str, Any]:
    """Hyperdrive direct INSERT (ADR-0036) into vertex_voxelforge_artifact +
    edge_voxelforge_derived_from for every artifact emitted upstream."""

    from kotodama.voxelforge.converters import register_artifacts_to_rw

    if state.error_text or not state.artifacts:
        return {"current_node": "register_artifact"}
    register_artifacts_to_rw(
        artifacts=state.artifacts,
        design_vertex_id=state.design_vertex_id,
        run_vertex_id=state.run_id,
        actor_did=state.actor_did,
        org_did=state.org_did,
    )
    return {"current_node": "register_artifact"}


# ── helpers ──────────────────────────────────────────────────────────


def _b64(b: bytes) -> str:
    import base64

    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    import base64

    return base64.b64decode(s)


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── graph factory ────────────────────────────────────────────────────


def build_graph():
    """Compile the voxelforge StateGraph.

    Returns the compiled graph object (langgraph 0.2.x ``CompiledStateGraph``).
    """
    if StateGraph is None:  # pragma: no cover — runtime always has it
        raise RuntimeError("langgraph not installed; pip install langgraph")

    g: Any = StateGraph(VoxelforgeState)
    g.add_node("parse_input", parse_input)
    g.add_node("route_generator", route_generator)
    g.add_node("generate_trellis", generate_trellis)
    g.add_node("generate_comfy3d", generate_comfy3d)
    g.add_node("exec_cadquery", exec_cadquery)
    g.add_node("post_process_mesh", post_process_mesh)
    g.add_node("voxelize", voxelize)
    g.add_node("export_artifacts", export_artifacts)
    g.add_node("register_artifact", register_artifact)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "route_generator")
    g.add_conditional_edges(
        "route_generator",
        _branch_router,
        {
            "trellis": "generate_trellis",
            "comfy3d": "generate_comfy3d",
            "cadquery": "exec_cadquery",
            # error fallback
            "post_process_mesh": "post_process_mesh",
        },
    )
    g.add_edge("generate_trellis", "post_process_mesh")
    g.add_edge("generate_comfy3d", "post_process_mesh")
    g.add_edge("exec_cadquery", "post_process_mesh")
    g.add_edge("post_process_mesh", "voxelize")
    g.add_edge("voxelize", "export_artifacts")
    g.add_edge("export_artifacts", "register_artifact")
    g.add_edge("register_artifact", END)

    return g.compile()
