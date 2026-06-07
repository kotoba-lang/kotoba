"""Unit tests for maps_sentinel_murakumo T2 semantic segmentation."""

from __future__ import annotations

import sys
from pathlib import Path as _P
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_sentinel_murakumo as MSM  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def _sentinel2_scene() -> dict[str, Any]:
    """Create a test Sentinel-2 scene dict."""
    return {
        "sceneId": "S2A_TEST_001",
        "platform": "sentinel-2-l2a",
        "cloudCover": 5.2,
        "bbox": [139.7, 35.4, 140.0, 35.7],
        "datetime": "2026-04-20T03:00:00Z",
    }


def _sentinel1_scene() -> dict[str, Any]:
    """Create a test Sentinel-1 scene dict."""
    return {
        "sceneId": "S1A_TEST_001",
        "platform": "sentinel-1-grd",
        "bbox": [139.7, 35.4, 140.0, 35.7],
        "datetime": "2026-04-20T03:00:00Z",
    }


# ── t2_semantic_segment ──────────────────────────────────────────────────────


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_land_cover_dispatches_to_llm(mock_lazy_import):
    """Test t2_semantic_segment with land-cover label_set dispatches to VLM."""
    # Mock the LLM module
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    # Mock vision_json to return a plausible result
    mock_llm.vision_json = AsyncMock(
        return_value={
            "label": "forest",
            "confidence": 0.87,
            "description": "Dense forest coverage detected in satellite tile",
        }
    )

    # Mock the thumbnail function to return dummy bytes
    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"dummy_png_data",
    ):
        scene = _sentinel2_scene()
        result = await MSM.t2_semantic_segment(scene, label_set="land-cover")

    # Verify the VLM was called with the land-cover prompt
    assert mock_llm.vision_json.called
    call_kwargs = mock_llm.vision_json.call_args.kwargs
    assert "land cover" in call_kwargs["prompt"].lower()
    assert call_kwargs["image_format"] == "png"
    assert call_kwargs["max_tokens"] == 256

    # Verify the result
    assert result["ok"] is True
    assert result["label_set"] == "land-cover"
    assert result["label"] == "forest"
    assert result["confidence"] == 0.87
    assert result["description"] == "Dense forest coverage detected in satellite tile"


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_water_body_label_set(mock_lazy_import):
    """Test t2_semantic_segment with water-body label_set."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    mock_llm.vision_json = AsyncMock(
        return_value={
            "label": "water",
            "confidence": 0.95,
            "description": "Large water body detected",
        }
    )

    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"png_data",
    ):
        scene = _sentinel1_scene()
        result = await MSM.t2_semantic_segment(scene, label_set="water-body")

    # Verify water-body prompt was used
    call_kwargs = mock_llm.vision_json.call_args.kwargs
    assert "water body" in call_kwargs["prompt"].lower()

    # Verify the result
    assert result["ok"] is True
    assert result["label_set"] == "water-body"
    assert result["label"] == "water"
    assert result["confidence"] == 0.95


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_returns_error_when_thumbnail_unavailable(
    mock_lazy_import,
):
    """Test t2_semantic_segment gracefully handles missing T0 (thumbnail)."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    # Don't mock _scene_to_thumbnail_png → NotImplementedError will be raised
    scene = _sentinel2_scene()
    result = await MSM.t2_semantic_segment(scene, label_set="land-cover")

    # Verify graceful error response
    assert result["ok"] is False
    assert result["label_set"] == "land-cover"
    assert result["label"] is None
    assert result["confidence"] == 0.0
    assert "T0 thumbnail extraction" in result["error"]
    assert "rasterio" in result["error"]

    # VLM should not have been called
    mock_llm.vision_json.assert_not_called()


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_handles_vlm_dispatch_error(mock_lazy_import):
    """Test t2_semantic_segment handles VLM dispatch errors."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    # Mock VLM to raise an exception
    mock_llm.vision_json = AsyncMock(
        side_effect=RuntimeError("VLM service timeout")
    )

    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"png_data",
    ):
        scene = _sentinel2_scene()
        result = await MSM.t2_semantic_segment(scene, label_set="land-cover")

    # Verify error handling
    assert result["ok"] is False
    assert result["label_set"] == "land-cover"
    assert result["label"] is None
    assert result["confidence"] == 0.0
    assert "VLM dispatch failed" in result["error"]
    assert "VLM service timeout" in result["error"]


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_custom_label_set(mock_lazy_import):
    """Test t2_semantic_segment with custom label_set string."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    mock_llm.vision_json = AsyncMock(
        return_value={
            "label": "rice-paddy",
            "confidence": 0.72,
        }
    )

    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"png_data",
    ):
        scene = _sentinel2_scene()
        result = await MSM.t2_semantic_segment(
            scene, label_set="agricultural-japan"
        )

    # Verify custom prompt
    call_kwargs = mock_llm.vision_json.call_args.kwargs
    assert "agricultural-japan" in call_kwargs["prompt"]

    # Verify the result
    assert result["ok"] is True
    assert result["label_set"] == "agricultural-japan"
    assert result["label"] == "rice-paddy"
    assert result["confidence"] == 0.72


def test_t2_no_sdk_raises_import_error():
    """Test t2_semantic_segment raises ImportError when etzhayyim_sdk not available."""
    # Simulate missing etzhayyim_sdk by mocking _lazy_import_llm to return None
    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm",
        return_value=None,
    ):
        scene = _sentinel2_scene()

        # We need to use a sync wrapper since t2_semantic_segment is async
        import asyncio

        with patch.object(
            asyncio, "iscoroutinefunction", return_value=True
        ):
            try:
                # Call the function; it should raise ImportError before the first await
                # (when checking if llm_mod is None)
                async def _test():
                    await MSM.t2_semantic_segment(scene)

                # Run the test
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(_test())
                    assert False, "Expected ImportError"
                except ImportError as e:
                    assert "etzhayyim_sdk" in str(e)
                    assert "llm" in str(e)
                finally:
                    loop.close()
            except ImportError:
                # Expected
                pass


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_confidence_handling(mock_lazy_import):
    """Test t2_semantic_segment properly converts confidence to float."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    # Return confidence as string (to test float conversion)
    mock_llm.vision_json = AsyncMock(
        return_value={
            "label": "cropland",
            "confidence": "0.65",  # String, should be converted
        }
    )

    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"png_data",
    ):
        scene = _sentinel2_scene()
        result = await MSM.t2_semantic_segment(scene)

    # Confidence should be converted to float
    assert isinstance(result["confidence"], float)
    assert result["confidence"] == 0.65


@patch("kotodama.primitives.maps_sentinel_murakumo._lazy_import_llm")
async def test_t2_semantic_segment_missing_fields_in_result(mock_lazy_import):
    """Test t2_semantic_segment handles missing fields in VLM response."""
    mock_llm = AsyncMock()
    mock_lazy_import.return_value = mock_llm

    # Return minimal response (missing description)
    mock_llm.vision_json = AsyncMock(
        return_value={
            "label": "urban",
            # confidence and description missing
        }
    )

    with patch(
        "kotodama.primitives.maps_sentinel_murakumo._scene_to_thumbnail_png",
        return_value=b"\x89PNG\r\n\x1a\n" + b"png_data",
    ):
        scene = _sentinel2_scene()
        result = await MSM.t2_semantic_segment(scene)

    # Should fill defaults
    assert result["ok"] is True
    assert result["label"] == "urban"
    assert result["confidence"] == 0.0  # Default fallback
    assert result["description"] == ""  # Default fallback
