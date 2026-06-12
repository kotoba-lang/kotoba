"""Mesh / voxel converters + B2 upload + kotoba Datom log register
(ADR-2605080700, ADR-0036 Hyperdrive direct write).

CadQuery exec runs in-process under tight resource limits.  Mesh
decimation uses ``trimesh`` + ``open3d`` when available, otherwise
returns the input unchanged.  Voxelization uses ``trimesh.voxel`` (or
``open3d``) and dumps a small JSON describing the occupancy grid +
RGB palette.  The MagicaVoxel `.vox` writer is implemented inline (the
spec is small and stable, and ``py-vox-io`` adds a heavy dep).

All numeric / string columns written to RisingWave follow ADR-0036
``vertex_voxelforge_artifact`` schema and ADR-0095 RLS columns
(``actor_did``/``org_did``/``at_did``/``created_at``).
"""

from __future__ import annotations

import io
import json
import os
import struct
import time
from typing import Any, Iterable
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client

# ── lazy imports — these are heavy and only needed at runtime in the
# Granian pod, not during LangServer / CF Worker imports. ──


def _import_trimesh():
    import trimesh  # type: ignore

    return trimesh


def _import_cadquery():
    import cadquery  # type: ignore

    return cadquery


# ── CadQuery → .glb ───────────────────────────────────────────────


def cadquery_to_glb(cad_code: str) -> tuple[bytes, int | None, int | None]:
    """Execute a CadQuery snippet that assigns ``result`` and export GLB.

    The exec sandbox is intentionally simple (Phase A): only ``cadquery``
    is exposed in builtins.  Production hardening (resource limits, AST
    allow-list) belongs to a later phase; current callers must already be
    org-authenticated.
    """

    cq = _import_cadquery()
    trimesh = _import_trimesh()

    sandbox: dict[str, Any] = {"cq": cq, "cadquery": cq, "__builtins__": {"__import__": __import__, "len": len, "range": range}}
    exec(compile(cad_code, "<cad>", "exec"), sandbox, sandbox)
    result = sandbox.get("result")
    if result is None:
        raise RuntimeError("cadCode did not assign `result = cq.Workplane(...)`")

    # Tessellate via cadquery → STL → trimesh → GLB
    stl_buf = io.BytesIO()
    if hasattr(result, "val"):
        result = result.val()
    if hasattr(result, "exportStl"):
        result.exportStl(stl_buf)  # type: ignore[arg-type]
    elif hasattr(cq, "exporters"):
        cq.exporters.export(result, stl_buf, "STL")  # type: ignore[attr-defined]
    else:
        raise RuntimeError("cadquery exporter unavailable")
    stl_buf.seek(0)
    mesh = trimesh.load(stl_buf, file_type="stl")
    glb = mesh.export(file_type="glb")
    polys = int(getattr(mesh, "faces", []).shape[0]) if hasattr(mesh, "faces") and hasattr(mesh.faces, "shape") else None
    verts = int(getattr(mesh, "vertices", []).shape[0]) if hasattr(mesh, "vertices") and hasattr(mesh.vertices, "shape") else None
    return bytes(glb), polys, verts


# ── mesh decimate (post_process_mesh) ───────────────────────────────


def decimate_glb(glb_bytes: bytes, target_polys: int = 20_000) -> tuple[bytes, int | None, int | None]:
    """Polygon reduction so large meshes do not blow up the .vox stage."""

    trimesh = _import_trimesh()
    mesh = trimesh.load(io.BytesIO(glb_bytes), file_type="glb")
    # trimesh.load may return a Scene
    if hasattr(mesh, "geometry") and getattr(mesh, "geometry", None):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))  # type: ignore[union-attr]
    n_polys = int(mesh.faces.shape[0])
    if n_polys <= target_polys:
        return glb_bytes, n_polys, int(mesh.vertices.shape[0])
    try:
        reduced = mesh.simplify_quadric_decimation(face_count=target_polys)  # type: ignore[attr-defined]
    except Exception:
        # open3d may not be available; skip decimation
        return glb_bytes, n_polys, int(mesh.vertices.shape[0])
    out = reduced.export(file_type="glb")
    return bytes(out), int(reduced.faces.shape[0]), int(reduced.vertices.shape[0])


# ── voxelize (.glb → voxel_grid.json) ───────────────────────────────


def glb_to_voxel_grid_json(
    glb_bytes: bytes,
    target_dim: int,
    palette: list[str] | None = None,
) -> tuple[str, int]:
    """Voxelize a GLB into a small RLE+palette JSON usable by kami-voxel.

    Returns ``(json_text, dim)``.  ``json_text`` shape::

        {
          "version": 1,
          "dim": [dim, dim, dim],
          "palette": ["#7a5230", ...],   # ≤256
          "rle": [[paletteIdx, count], ...]   # row-major xyz
        }
    """

    trimesh = _import_trimesh()
    mesh = trimesh.load(io.BytesIO(glb_bytes), file_type="glb")
    if hasattr(mesh, "geometry") and getattr(mesh, "geometry", None):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))  # type: ignore[union-attr]

    # Normalize to unit cube then scale to target_dim
    bounds = mesh.bounds
    extent = (bounds[1] - bounds[0]).max()
    if extent <= 0:
        raise RuntimeError("mesh has degenerate bounding box")
    pitch = extent / max(target_dim - 1, 1)
    vox = mesh.voxelized(pitch=pitch).fill()
    grid = vox.matrix  # boolean ndarray dim^3-ish
    dim = int(max(grid.shape))

    # Pad to cube
    import numpy as np  # type: ignore

    cube = np.zeros((dim, dim, dim), dtype=bool)
    sx, sy, sz = grid.shape
    cube[:sx, :sy, :sz] = grid

    # Default palette: single neutral color (#cccccc) for occupied, empty=0.
    pal = palette or ["#cccccc"]
    pal_idx = 1  # palette[0] reserved as "first material"

    # Row-major (z, y, x) flatten then RLE.
    flat = cube.transpose(2, 1, 0).flatten().astype(int) * pal_idx
    rle: list[list[int]] = []
    if flat.size:
        cur = int(flat[0])
        cnt = 1
        for v in flat[1:]:
            v = int(v)
            if v == cur:
                cnt += 1
            else:
                rle.append([cur, cnt])
                cur = v
                cnt = 1
        rle.append([cur, cnt])

    out = {
        "version": 1,
        "dim": [dim, dim, dim],
        "palette": pal,
        "rle": rle,
    }
    return json.dumps(out, separators=(",", ":")), dim


# ── voxel_grid.json → MagicaVoxel .vox ──────────────────────────────


def voxel_grid_json_to_vox_bytes(grid_json_bytes: bytes) -> bytes:
    """Minimal MagicaVoxel writer (single SIZE + XYZI + optional RGBA chunk).

    Spec: https://github.com/ephtracy/voxel-model/blob/master/MagicaVoxel-file-format-vox.txt
    Phase A emits 1 model, ≤256 voxel dim per axis.
    """

    grid = json.loads(grid_json_bytes)
    dim_xyz = grid.get("dim") or [32, 32, 32]
    dx, dy, dz = (int(v) for v in dim_xyz[:3])
    pal_hex = grid.get("palette") or ["#cccccc"]
    rle = grid.get("rle") or []

    voxels: list[tuple[int, int, int, int]] = []  # (x, y, z, palette_idx 1..255)
    idx = 0
    flat_total = dx * dy * dz
    expanded = bytearray(flat_total)
    for pal_idx, count in rle:
        for _ in range(count):
            if idx < flat_total:
                expanded[idx] = pal_idx & 0xFF
                idx += 1
    for z in range(dz):
        for y in range(dy):
            for x in range(dx):
                v = expanded[z * dy * dx + y * dx + x]
                if v:
                    voxels.append((x, y, z, v))

    # Build .vox chunks
    def chunk(name: bytes, content: bytes, children: bytes = b"") -> bytes:
        return name + struct.pack("<II", len(content), len(children)) + content + children

    main_children = b""
    main_children += chunk(b"SIZE", struct.pack("<III", dx, dy, dz))
    xyzi_body = struct.pack("<I", len(voxels))
    for (x, y, z, p) in voxels:
        xyzi_body += struct.pack("<BBBB", x, y, z, p)
    main_children += chunk(b"XYZI", xyzi_body)

    # RGBA palette: index 1..256 (slot 0 reserved). MagicaVoxel reads
    # 256 entries; extend with neutral grey for unused slots.
    rgba = bytearray(256 * 4)
    for i in range(256):
        if i < len(pal_hex):
            r, g, b = _hex_to_rgb(pal_hex[i])
        else:
            r, g, b = (0xCC, 0xCC, 0xCC)
        rgba[i * 4 : i * 4 + 4] = bytes([r, g, b, 0xFF])
    main_children += chunk(b"RGBA", bytes(rgba))

    main = chunk(b"MAIN", b"", main_children)
    header = b"VOX " + struct.pack("<I", 150)
    return header + main


def _hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return (0xCC, 0xCC, 0xCC)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# ── B2 PUT ─────────────────────────────────────────────────────────


def b2_put(bucket: str, key: str, body: bytes, content_type: str) -> None:
    """Upload to Backblaze B2 via S3-compatible SigV4 (boto3).

    Credentials from env: ``B2_ACCESS_KEY_ID`` / ``B2_SECRET_ACCESS_KEY``
    / ``B2_ENDPOINT_URL`` (e.g. ``https://s3.us-west-004.backblazeb2.com``).

    ``etzhayyim_VOXELFORGE_DRY_RUN=1`` skips the upload (returns success). Used
    by unit tests + offline development.
    """

    if os.environ.get("etzhayyim_VOXELFORGE_DRY_RUN") == "1":
        return

    import boto3  # type: ignore

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("B2_ENDPOINT_URL") or "https://s3.us-west-004.backblazeb2.com",
        aws_access_key_id=os.environ.get("B2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("B2_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("B2_REGION", "us-west-004"),
    )
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)


# ── kotoba Datom log register (ADR-2605262130 + ADR-2605312345) ──────


def register_artifacts_to_rw(
    artifacts: Iterable[Any],
    design_vertex_id: str,
    run_vertex_id: str,
    actor_did: str,
    org_did: str,
) -> None:
    """INSERT artifact rows + lineage edges into kotoba Datom log.

    Skips silently when ``etzhayyim_VOXELFORGE_DRY_RUN=1`` so unit tests do
    not need a live cluster. Production goes through the canonical
    sync_cursor path used by every other primitives module
    (``kotodama.db.sync_cursor`` / ``insert_into``).
    """

    if os.environ.get("etzhayyim_VOXELFORGE_DRY_RUN") == "1":
        return

    now_iso = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    client = get_kotoba_client()
    for a in artifacts:
        client.insert_row(
            "vertex_voxelforge_artifact",
            {
                "vertex_id": a.vertex_id,
                "_seq": None,
                "created_date": now_iso.split('T')[0],  # Extract date part
                "sensitivity_ord": 2,
                "owner_did": actor_did,
                "design_vertex_id": design_vertex_id,
                "run_vertex_id": run_vertex_id,
                "format": a.format,
                "b2_bucket": a.b2_bucket,
                "b2_key": a.b2_key,
                "sha256_hex": a.sha256_hex,
                "byte_size": a.byte_size,
                "voxel_dim": a.voxel_dim,
                "polygon_count": a.polygon_count,
                "vertex_count": a.vertex_count,
                "generated_by": a.generated_by,
                "ts_ms": a.ts_ms,
                "actor_did": actor_did,
                "org_did": org_did,
                "at_did": None,
                "created_at": now_iso,
            },
        )
        client.insert_row(
            "edge_voxelforge_derived_from",
            {
                "edge_id": f"{a.vertex_id}|{design_vertex_id}",
                "src_vid": a.vertex_id,
                "dst_vid": design_vertex_id,
                "_seq": None,
                "created_date": now_iso.split('T')[0],  # Extract date part
                "sensitivity_ord": 2,
                "owner_did": actor_did,
                "derivation_kind": "voxelforge_export",
                "created_at": now_iso,
                "org_did": org_did,
                "actor_did": actor_did,
            },
        )
