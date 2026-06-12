from __future__ import annotations

import json
import math
from typing import Any


Number = int | float


DEFAULT_CONTAINER = {
    "lengthMm": 1200,
    "widthMm": 1000,
    "heightMm": 1400,
    "maxPayloadKg": 750,
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _num(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return default
        return parsed if math.isfinite(parsed) else default
    return default


def _text(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _bbox(det: dict[str, Any]) -> dict[str, float]:
    box = det.get("bbox") or det.get("boundingBox") or det.get("box") or {}
    if isinstance(box, list) and len(box) >= 4:
        x, y, w, h = box[:4]
        return {
            "x": _num(x, 0),
            "y": _num(y, 0),
            "width": max(0.0, _num(w, 0)),
            "height": max(0.0, _num(h, 0)),
        }
    box_dict = _as_dict(box)
    return {
        "x": _num(box_dict.get("x", det.get("x")), 0),
        "y": _num(box_dict.get("y", det.get("y")), 0),
        "width": max(0.0, _num(box_dict.get("width", det.get("width")), 0)),
        "height": max(0.0, _num(box_dict.get("height", det.get("height")), 0)),
    }


def _normalize_detections(value: Any) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    for index, raw in enumerate(_as_list(value)):
        det = _as_dict(raw)
        if not det:
            continue
        label = _text(
            det.get("label") or det.get("class") or det.get("name") or det.get("type"),
            f"object-{index + 1}",
        )
        detections.append(
            {
                "id": _text(det.get("id"), f"det-{index + 1:03d}"),
                "label": label,
                "confidence": round(max(0.0, min(1.0, _num(det.get("confidence", det.get("score")), 0.5))), 3),
                "bbox": _bbox(det),
                "estimatedWeightKg": round(max(0.0, _num(det.get("estimatedWeightKg", det.get("weightKg")), 0)), 3),
                "attributes": _as_dict(det.get("attributes")),
            }
        )
    detections.sort(key=lambda item: (-item["confidence"], item["id"]))
    return detections


def analyze_loading_image(
    *,
    image_uri: str | None = None,
    image_analysis: Any = None,
    detections: Any = None,
    scene: Any = None,
) -> dict[str, Any]:
    analysis = _as_dict(image_analysis)
    scene_dict = {**_as_dict(scene), **_as_dict(analysis.get("scene"))}
    detected = _normalize_detections(detections or analysis.get("detections") or analysis.get("objects"))
    floor_markers = [
        det for det in detected
        if det["label"].lower() in {"pallet", "truck-bed", "container", "dock", "floor-marker"}
    ]
    cargo = [
        det for det in detected
        if det["label"].lower() in {"box", "carton", "crate", "case", "cargo", "pallet-load"}
    ]
    confidence = round(
        sum(det["confidence"] for det in detected) / len(detected),
        3,
    ) if detected else 0.0
    constraints = {
        "loadingSurface": _text(scene_dict.get("loadingSurface"), "unknown"),
        "lighting": _text(scene_dict.get("lighting"), "unknown"),
        "humanPresence": bool(scene_dict.get("humanPresence", False)),
        "occlusionRisk": bool(scene_dict.get("occlusionRisk", not detected)),
        "requiresHumanReview": confidence < 0.72 or bool(scene_dict.get("humanPresence", False)),
    }
    return {
        "loadingRobotVision": {
            "imageUri": _text(image_uri or analysis.get("imageUri") or analysis.get("uri"), ""),
            "sceneId": _text(scene_dict.get("sceneId"), "loading-scene"),
            "detectedObjects": detected,
            "cargoCandidates": cargo,
            "floorMarkers": floor_markers,
            "constraints": constraints,
            "confidence": confidence,
        }
    }


def _normalize_container(container: Any) -> dict[str, float]:
    raw = {**DEFAULT_CONTAINER, **_as_dict(container)}
    return {
        "lengthMm": max(1.0, _num(raw.get("lengthMm"), DEFAULT_CONTAINER["lengthMm"])),
        "widthMm": max(1.0, _num(raw.get("widthMm"), DEFAULT_CONTAINER["widthMm"])),
        "heightMm": max(1.0, _num(raw.get("heightMm"), DEFAULT_CONTAINER["heightMm"])),
        "maxPayloadKg": max(1.0, _num(raw.get("maxPayloadKg"), DEFAULT_CONTAINER["maxPayloadKg"])),
    }


def _normalize_cargo(items: Any, vision: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    raw_items = _as_list(items)
    if not raw_items and vision:
        raw_items = vision.get("cargoCandidates", [])
    cargo: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items):
        item = _as_dict(raw)
        if not item:
            continue
        dims = _as_dict(item.get("dimensionsMm"))
        cargo.append(
            {
                "id": _text(item.get("id"), f"cargo-{index + 1:03d}"),
                "label": _text(item.get("label") or item.get("sku"), f"cargo-{index + 1}"),
                "lengthMm": max(1.0, _num(dims.get("length", item.get("lengthMm")), 300)),
                "widthMm": max(1.0, _num(dims.get("width", item.get("widthMm")), 240)),
                "heightMm": max(1.0, _num(dims.get("height", item.get("heightMm")), 180)),
                "weightKg": max(0.1, _num(item.get("weightKg", item.get("estimatedWeightKg")), 5)),
                "fragile": bool(item.get("fragile", item.get("attributes", {}).get("fragile", False)) if isinstance(item.get("attributes"), dict) else item.get("fragile", False)),
            }
        )
    cargo.sort(key=lambda item: (-item["weightKg"], item["fragile"], item["id"]))
    return cargo


def plan_load(
    *,
    cargo_items: Any = None,
    container: Any = None,
    image_analysis: Any = None,
    safety_margin_mm: Number = 50,
) -> dict[str, Any]:
    vision = _as_dict(image_analysis).get("loadingRobotVision", _as_dict(image_analysis))
    cargo = _normalize_cargo(cargo_items, vision if isinstance(vision, dict) else None)
    box = _normalize_container(container)
    margin = max(0.0, _num(safety_margin_mm, 50))
    cursor_x = margin
    cursor_y = margin
    row_depth = 0.0
    total_weight = 0.0
    placements: list[dict[str, Any]] = []
    warnings: list[str] = []

    for sequence, item in enumerate(cargo, start=1):
        if cursor_x + item["lengthMm"] + margin > box["lengthMm"]:
            cursor_x = margin
            cursor_y += row_depth + margin
            row_depth = 0.0
        if cursor_y + item["widthMm"] + margin > box["widthMm"]:
            warnings.append(f"{item['id']} does not fit in the first layer")
            continue
        total_weight += item["weightKg"]
        if total_weight > box["maxPayloadKg"]:
            warnings.append("payload exceeds container maxPayloadKg")
        placements.append(
            {
                "sequence": sequence,
                "cargoId": item["id"],
                "label": item["label"],
                "pose": {
                    "xMm": round(cursor_x + item["lengthMm"] / 2, 1),
                    "yMm": round(cursor_y + item["widthMm"] / 2, 1),
                    "zMm": round(item["heightMm"] / 2, 1),
                    "yawDeg": 0,
                },
                "grip": "vacuum-pad" if not item["fragile"] and item["weightKg"] <= 25 else "soft-parallel",
                "weightKg": item["weightKg"],
            }
        )
        cursor_x += item["lengthMm"] + margin
        row_depth = max(row_depth, item["widthMm"])

    if not placements:
        warnings.append("no cargo placements generated; require operator review")
    center_x = sum(p["pose"]["xMm"] * p["weightKg"] for p in placements) / total_weight if total_weight else 0
    center_y = sum(p["pose"]["yMm"] * p["weightKg"] for p in placements) / total_weight if total_weight else 0
    return {
        "loadingRobotLoadPlan": {
            "container": box,
            "placements": placements,
            "totalWeightKg": round(total_weight, 3),
            "centerOfMassMm": {"x": round(center_x, 1), "y": round(center_y, 1), "z": 0},
            "warnings": warnings,
            "requiresHumanApproval": bool(warnings) or total_weight > box["maxPayloadKg"] * 0.9,
        }
    }


def design_robot_cell(
    *,
    load_plan: Any = None,
    site_constraints: Any = None,
    robot: Any = None,
) -> dict[str, Any]:
    plan = _as_dict(load_plan).get("loadingRobotLoadPlan", _as_dict(load_plan))
    constraints = _as_dict(site_constraints)
    robot_spec = {**{"type": "6-axis-arm", "payloadKg": 35, "reachMm": 1600}, **_as_dict(robot)}
    placements = _as_list(plan.get("placements")) if isinstance(plan, dict) else []
    max_item_weight = max((_num(p.get("weightKg"), 0) for p in placements if isinstance(p, dict)), default=0.0)
    end_effector = "soft-parallel-gripper" if max_item_weight > 25 else "vacuum-array-gripper"
    if any(isinstance(p, dict) and p.get("grip") == "soft-parallel" for p in placements):
        end_effector = "hybrid-vacuum-soft-parallel-gripper"
    return {
        "loadingRobotCellDesign": {
            "robot": robot_spec,
            "endEffector": end_effector,
            "sensors": [
                "overhead-rgbd-camera",
                "wrist-depth-camera",
                "force-torque-sensor",
                "safety-lidar",
            ],
            "zones": {
                "pick": _text(constraints.get("pickZone"), "dock-pick-zone"),
                "place": _text(constraints.get("placeZone"), "truck-or-pallet-zone"),
                "humanExclusion": bool(constraints.get("humanExclusion", True)),
            },
            "waypoints": [
                {"id": "home", "pose": [0, -600, 900, 0, 180, 0]},
                {"id": "scan", "pose": [0, -900, 1200, 0, 180, 0]},
                {"id": "approach-pick", "pose": [-450, -750, 650, 0, 180, 0]},
                {"id": "approach-place", "pose": [450, 750, 650, 0, 180, 0]},
            ],
            "interfaces": {
                "missionTopic": "loading-robot/mission",
                "telemetryTopic": "loading-robot/telemetry",
                "estopInput": "safety/estop",
                "outputFormats": ["robot-waypoint-json", "opcua-command", "ros2-action"],
            },
            "requiresHumanApproval": bool(plan.get("requiresHumanApproval", True)) if isinstance(plan, dict) else True,
        }
    }


def plan_loading_mission(
    *,
    load_plan: Any = None,
    cell_design: Any = None,
    mission_id: str | None = None,
) -> dict[str, Any]:
    plan = _as_dict(load_plan).get("loadingRobotLoadPlan", _as_dict(load_plan))
    cell = _as_dict(cell_design).get("loadingRobotCellDesign", _as_dict(cell_design))
    placements = _as_list(plan.get("placements")) if isinstance(plan, dict) else []
    commands = []
    for placement in placements:
        if not isinstance(placement, dict):
            continue
        commands.extend(
            [
                {"op": "move", "target": "approach-pick", "cargoId": placement.get("cargoId")},
                {"op": "grip", "tool": placement.get("grip", "vacuum-pad"), "cargoId": placement.get("cargoId")},
                {"op": "move", "target": "approach-place", "cargoId": placement.get("cargoId")},
                {"op": "place", "pose": placement.get("pose"), "cargoId": placement.get("cargoId")},
            ]
        )
    return {
        "loadingRobotMission": {
            "missionId": _text(mission_id, "loading-mission"),
            "protocol": "robot-waypoint-json",
            "approvalRequired": bool(cell.get("requiresHumanApproval", True)) if isinstance(cell, dict) else True,
            "commands": commands,
            "telemetry": {
                "topic": _as_dict(cell.get("interfaces")).get("telemetryTopic", "loading-robot/telemetry") if isinstance(cell, dict) else "loading-robot/telemetry",
                "requiredSignals": ["pose", "gripState", "payloadKg", "safetyState"],
            },
            "emergencyStop": {
                "input": _as_dict(cell.get("interfaces")).get("estopInput", "safety/estop") if isinstance(cell, dict) else "safety/estop",
                "policy": "stop-motion-drop-to-safe-hold",
            },
        }
    }


def task_vision_analyze(**kwargs: Any) -> dict[str, Any]:
    return analyze_loading_image(
        image_uri=kwargs.get("imageUri") or kwargs.get("image_uri"),
        image_analysis=kwargs.get("imageAnalysis") or kwargs.get("image_analysis"),
        detections=kwargs.get("detections"),
        scene=kwargs.get("scene"),
    )


def task_plan_load(**kwargs: Any) -> dict[str, Any]:
    return plan_load(
        cargo_items=kwargs.get("cargoItems") or kwargs.get("cargo_items"),
        container=kwargs.get("container"),
        image_analysis=kwargs.get("loadingRobotVision") or kwargs.get("imageAnalysis"),
        safety_margin_mm=kwargs.get("safetyMarginMm", 50),
    )


def task_robot_design(**kwargs: Any) -> dict[str, Any]:
    return design_robot_cell(
        load_plan=kwargs.get("loadingRobotLoadPlan") or kwargs.get("loadPlan"),
        site_constraints=kwargs.get("siteConstraints") or kwargs.get("site_constraints"),
        robot=kwargs.get("robot"),
    )


def task_mission_plan(**kwargs: Any) -> dict[str, Any]:
    return plan_loading_mission(
        load_plan=kwargs.get("loadingRobotLoadPlan") or kwargs.get("loadPlan"),
        cell_design=kwargs.get("loadingRobotCellDesign") or kwargs.get("cellDesign"),
        mission_id=kwargs.get("missionId") or kwargs.get("mission_id"),
    )


def register(worker: Any, timeout_ms: int = 180_000) -> None:
    worker.task(task_type="loadingRobot.vision.analyze", single_value=False, timeout_ms=timeout_ms)(task_vision_analyze)
    worker.task(task_type="loadingRobot.plan.load", single_value=False, timeout_ms=timeout_ms)(task_plan_load)
    worker.task(task_type="loadingRobot.robot.design", single_value=False, timeout_ms=timeout_ms)(task_robot_design)
    worker.task(task_type="loadingRobot.mission.plan", single_value=False, timeout_ms=timeout_ms)(task_mission_plan)
