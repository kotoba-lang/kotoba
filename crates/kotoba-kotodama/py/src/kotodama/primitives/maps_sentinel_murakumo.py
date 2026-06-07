"""Maps Sentinel T2 — Semantic segmentation via VLM (vision LLM dispatch).

Per ADR-2605215100 §1 T2. Dispatches to EVO-X2 ROCm or M4 Mac mini MLX
depending on available memory.

For M3 milestone, returns coarse label-level prediction (no pixel-level mask).
Full pixel segmentation deferred to T3+ when rasterio + Florence-2 MLX port land.
"""

from __future__ import annotations

from typing import Any

# Placeholder for etzhayyim_sdk.llm module (imported on-demand)
_llm_mod: Any = None


def _lazy_import_llm() -> Any:
    """Lazy-load etzhayyim_sdk.llm module on first use."""
    global _llm_mod
    if _llm_mod is None:
        try:
            from etzhayyim_sdk import llm as llm_module
            _llm_mod = llm_module
        except ImportError:
            _llm_mod = None
    return _llm_mod


def _scene_to_thumbnail_png(scene: dict[str, Any]) -> bytes:
    """Extract thumbnail bytes from Sentinel1Scene or Sentinel2Scene.

    M3 milestone: placeholder — raises NotImplementedError until T0
    rasterio + thumbnail extraction lands in M2.

    Depends on rasterio + Sentinel metadata parsing.
    """
    raise NotImplementedError(
        "T0 thumbnail extraction pending M2 milestone (rasterio GeoTIFF read + "
        "PNG encoding not yet ported to MLX). Scene: {scene.get('sceneId', 'unknown')}"
    )


async def t2_semantic_segment(
    scene: dict[str, Any],
    label_set: str = "land-cover",
) -> dict[str, Any]:
    """T2 — Semantic segmentation via VLM (Florence-2-base or SegFormer).

    Per ADR-2605215100 §1 T2. Dispatches to EVO-X2 ROCm or M4 Mac mini MLX
    depending on available memory.

    For M3 milestone, returns coarse label-level prediction (no pixel-level mask).
    Full pixel segmentation deferred to T3+ when rasterio + Florence-2 MLX port land.

    Args:
        scene: Sentinel1Scene or Sentinel2Scene dict with sceneId, platform, etc.
        label_set: Label taxonomy to use:
            - "land-cover": forest|water|urban|bare|cropland|other
            - "water-body": water|land (binary)
            - Custom string for domain-specific segmentation

    Returns:
        dict with keys:
            - ok (bool): segmentation succeeded
            - label_set (str): which label taxonomy was used
            - label (str|None): predicted dominant class
            - confidence (float): 0.0-1.0 confidence score
            - description (str): optional explanation from VLM
            - error (str): error message if ok=False
    """
    llm_mod = _lazy_import_llm()
    if llm_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed; t2_semantic_segment requires "
            "etzhayyim_sdk.llm for vision dispatch"
        )

    # Build segmentation prompt based on label_set
    if label_set == "land-cover":
        prompt = (
            "Identify the dominant land cover class in this satellite tile. "
            "Return JSON: {\"label\": \"forest|water|urban|bare|cropland|other\", "
            "\"confidence\": 0.0-1.0, \"description\": \"...\"}"
        )
    elif label_set == "water-body":
        prompt = (
            "Is this satellite tile dominated by a water body? "
            "Return JSON: {\"label\": \"water|land\", "
            "\"confidence\": 0.0-1.0, \"description\": \"...\"}"
        )
    else:
        prompt = (
            f"Segment this satellite tile by class '{label_set}'. "
            f"Return JSON: {{\"label\": str, \"confidence\": 0.0-1.0, "
            f"\"description\": \"...\"}}"
        )

    # Extract thumbnail (T0 dependency — placeholder until M2 lands)
    try:
        tile_bytes = _scene_to_thumbnail_png(scene)
    except NotImplementedError as e:
        # M3 milestone: gracefully report T0 dep gap
        return {
            "ok": False,
            "label_set": label_set,
            "label": None,
            "confidence": 0.0,
            "error": f"T0 thumbnail extraction pending M2 (rasterio dep): {e}",
        }

    # Dispatch to VLM
    try:
        result = await llm_mod.vision_json(
            prompt=prompt,
            image_bytes=tile_bytes,
            image_format="png",
            max_tokens=256,
        )
    except Exception as e:
        return {
            "ok": False,
            "label_set": label_set,
            "label": None,
            "confidence": 0.0,
            "error": f"VLM dispatch failed: {e}",
        }

    return {
        "ok": True,
        "label_set": label_set,
        "label": result.get("label"),
        "confidence": float(result.get("confidence", 0.0)),
        "description": result.get("description", ""),
    }
