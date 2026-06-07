from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path as _P


ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lr = _load("_loading_robot", "primitives/loading_robot.py")


def test_analyze_loading_image_normalizes_detections_and_review_flag():
    out = lr.analyze_loading_image(
        image_uri="s3://dock/frame-001.jpg",
        detections=[
            {"class": "box", "score": 0.91, "bbox": [10, 20, 100, 120], "weightKg": 8},
            {"label": "pallet", "confidence": 0.88, "boundingBox": {"x": 0, "y": 0, "width": 300, "height": 200}},
        ],
        scene={"sceneId": "dock-a", "loadingSurface": "pallet"},
    )
    vision = out["loadingRobotVision"]
    assert vision["imageUri"] == "s3://dock/frame-001.jpg"
    assert vision["sceneId"] == "dock-a"
    assert [det["label"] for det in vision["detectedObjects"]] == ["box", "pallet"]
    assert len(vision["cargoCandidates"]) == 1
    assert len(vision["floorMarkers"]) == 1
    assert vision["constraints"]["requiresHumanReview"] is False


def test_plan_load_generates_weighted_placements():
    out = lr.plan_load(
        cargo_items=[
            {"id": "A", "weightKg": 10, "lengthMm": 400, "widthMm": 300, "heightMm": 200},
            {"id": "B", "weightKg": 5, "lengthMm": 300, "widthMm": 250, "heightMm": 180, "fragile": True},
        ],
        container={"lengthMm": 1000, "widthMm": 800, "heightMm": 900, "maxPayloadKg": 100},
        safety_margin_mm=25,
    )
    plan = out["loadingRobotLoadPlan"]
    assert [p["cargoId"] for p in plan["placements"]] == ["A", "B"]
    assert plan["totalWeightKg"] == 15
    assert plan["placements"][1]["grip"] == "soft-parallel"
    assert plan["requiresHumanApproval"] is False


def test_robot_design_and_mission_plan_are_protocol_ready():
    load_plan = lr.plan_load(cargo_items=[{"id": "C", "weightKg": 30}])["loadingRobotLoadPlan"]
    cell = lr.design_robot_cell(load_plan=load_plan, site_constraints={"pickZone": "dock-2"})["loadingRobotCellDesign"]
    mission = lr.plan_loading_mission(
        load_plan=load_plan,
        cell_design=cell,
        mission_id="mission-001",
    )["loadingRobotMission"]
    assert cell["endEffector"] == "hybrid-vacuum-soft-parallel-gripper"
    assert cell["zones"]["pick"] == "dock-2"
    assert mission["missionId"] == "mission-001"
    assert mission["protocol"] == "robot-waypoint-json"
    assert [cmd["op"] for cmd in mission["commands"]] == ["move", "grip", "move", "place"]


def test_register_exposes_four_pyzeebe_tasks():
    registered: list[tuple[str, bool, int]] = []

    class FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            registered.append((task_type, single_value, timeout_ms))

            def decorator(fn):
                return fn

            return decorator

    lr.register(FakeWorker(), timeout_ms=123)
    assert registered == [
        ("loadingRobot.vision.analyze", False, 123),
        ("loadingRobot.plan.load", False, 123),
        ("loadingRobot.robot.design", False, 123),
        ("loadingRobot.mission.plan", False, 123),
    ]
