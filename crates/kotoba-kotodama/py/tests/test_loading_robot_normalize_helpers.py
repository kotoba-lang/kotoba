"""Tests for _normalize_detections, _normalize_container, _normalize_cargo in loading_robot.py."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


def _load(name: str, rel: str) -> types.ModuleType:
    path = _py_src / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


LR = _load("_loading_robot_norm", "kotodama/primitives/loading_robot.py")


# ─── _normalize_detections ───────────────────────────────────────────────────

def test_normalize_detections_empty_returns_empty() -> None:
    assert LR._normalize_detections([]) == []


def test_normalize_detections_non_list_returns_empty() -> None:
    assert LR._normalize_detections(None) == []
    assert LR._normalize_detections("string") == []


def test_normalize_detections_basic_detection() -> None:
    detections = [{"label": "box", "confidence": 0.9}]
    result = LR._normalize_detections(detections)
    assert len(result) == 1
    det = result[0]
    assert det["label"] == "box"
    assert det["confidence"] == 0.9


def test_normalize_detections_has_required_keys() -> None:
    detections = [{"label": "pallet", "confidence": 0.8}]
    result = LR._normalize_detections(detections)
    det = result[0]
    assert "id" in det
    assert "label" in det
    assert "confidence" in det
    assert "bbox" in det
    assert "estimatedWeightKg" in det
    assert "attributes" in det


def test_normalize_detections_confidence_clamped() -> None:
    detections = [{"label": "box", "confidence": 1.5}]
    result = LR._normalize_detections(detections)
    assert result[0]["confidence"] <= 1.0


def test_normalize_detections_confidence_negative_clamped() -> None:
    detections = [{"label": "box", "confidence": -0.5}]
    result = LR._normalize_detections(detections)
    assert result[0]["confidence"] >= 0.0


def test_normalize_detections_uses_class_fallback() -> None:
    detections = [{"class": "carton", "confidence": 0.7}]
    result = LR._normalize_detections(detections)
    assert result[0]["label"] == "carton"


def test_normalize_detections_sorted_by_confidence_desc() -> None:
    detections = [
        {"label": "low", "confidence": 0.3},
        {"label": "high", "confidence": 0.9},
    ]
    result = LR._normalize_detections(detections)
    assert result[0]["confidence"] > result[1]["confidence"]


def test_normalize_detections_default_id_generated() -> None:
    detections = [{"label": "box", "confidence": 0.5}]
    result = LR._normalize_detections(detections)
    assert result[0]["id"].startswith("det-")


def test_normalize_detections_custom_id_preserved() -> None:
    detections = [{"id": "custom-001", "label": "box", "confidence": 0.5}]
    result = LR._normalize_detections(detections)
    assert result[0]["id"] == "custom-001"


def test_normalize_detections_skips_non_dict_items() -> None:
    detections = ["string-item", {"label": "box", "confidence": 0.8}, 42]
    result = LR._normalize_detections(detections)
    assert len(result) == 1
    assert result[0]["label"] == "box"


# ─── _normalize_container ────────────────────────────────────────────────────

def test_normalize_container_empty_uses_defaults() -> None:
    result = LR._normalize_container({})
    assert result["lengthMm"] >= 1.0
    assert result["widthMm"] >= 1.0
    assert result["heightMm"] >= 1.0
    assert result["maxPayloadKg"] >= 1.0


def test_normalize_container_custom_values() -> None:
    result = LR._normalize_container({"lengthMm": 12000, "widthMm": 2400, "heightMm": 2600, "maxPayloadKg": 25000})
    assert result["lengthMm"] == 12000.0
    assert result["widthMm"] == 2400.0
    assert result["heightMm"] == 2600.0
    assert result["maxPayloadKg"] == 25000.0


def test_normalize_container_min_values_clamped_at_1() -> None:
    result = LR._normalize_container({"lengthMm": 0, "widthMm": -100})
    assert result["lengthMm"] >= 1.0
    assert result["widthMm"] >= 1.0


def test_normalize_container_none_uses_defaults() -> None:
    result = LR._normalize_container(None)
    assert isinstance(result, dict)
    assert "lengthMm" in result


def test_normalize_container_has_all_keys() -> None:
    result = LR._normalize_container({})
    assert set(result.keys()) == {"lengthMm", "widthMm", "heightMm", "maxPayloadKg"}


# ─── _normalize_cargo ────────────────────────────────────────────────────────

def test_normalize_cargo_empty_returns_empty() -> None:
    assert LR._normalize_cargo([]) == []


def test_normalize_cargo_none_returns_empty() -> None:
    assert LR._normalize_cargo(None) == []


def test_normalize_cargo_basic_item() -> None:
    items = [{"label": "box", "weightKg": 10, "lengthMm": 300, "widthMm": 200, "heightMm": 150}]
    result = LR._normalize_cargo(items)
    assert len(result) == 1
    assert result[0]["label"] == "box"
    assert result[0]["weightKg"] == 10.0


def test_normalize_cargo_has_required_keys() -> None:
    items = [{"label": "crate"}]
    result = LR._normalize_cargo(items)
    item = result[0]
    assert "id" in item
    assert "label" in item
    assert "lengthMm" in item
    assert "widthMm" in item
    assert "heightMm" in item
    assert "weightKg" in item
    assert "fragile" in item


def test_normalize_cargo_weight_clamped_at_min() -> None:
    items = [{"label": "box", "weightKg": 0}]
    result = LR._normalize_cargo(items)
    assert result[0]["weightKg"] >= 0.1


def test_normalize_cargo_sorted_by_weight_desc() -> None:
    items = [
        {"label": "light", "weightKg": 1.0},
        {"label": "heavy", "weightKg": 50.0},
    ]
    result = LR._normalize_cargo(items)
    assert result[0]["weightKg"] > result[1]["weightKg"]


def test_normalize_cargo_uses_sku_as_label_fallback() -> None:
    items = [{"sku": "SKU-001"}]
    result = LR._normalize_cargo(items)
    assert result[0]["label"] == "SKU-001"


def test_normalize_cargo_fragile_flag() -> None:
    items = [{"label": "glass", "fragile": True}]
    result = LR._normalize_cargo(items)
    assert result[0]["fragile"] is True


def test_normalize_cargo_uses_vision_candidates_when_items_empty() -> None:
    vision = {
        "cargoCandidates": [
            {"label": "box", "weightKg": 5}
        ]
    }
    result = LR._normalize_cargo([], vision=vision)
    assert len(result) == 1
    assert result[0]["label"] == "box"
