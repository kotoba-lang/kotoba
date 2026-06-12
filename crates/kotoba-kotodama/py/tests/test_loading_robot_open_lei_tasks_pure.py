"""Pure-path task tests for loading_robot.py and open_lei.py.

All tested paths are pure computation — no DB, HTTP, or LLM required.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import loading_robot as LR  # noqa: E402
from kotodama.primitives import open_lei as OL  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# loading_robot
# ═══════════════════════════════════════════════════════════════════════════════

# ─── task_vision_analyze ─────────────────────────────────────────────────────

def test_vision_analyze_returns_dict() -> None:
    result = asyncio.run(LR.task_vision_analyze())
    assert isinstance(result, dict)


def test_vision_analyze_has_vision_key() -> None:
    result = asyncio.run(LR.task_vision_analyze())
    assert "loadingRobotVision" in result


def test_vision_analyze_no_image_has_detected_objects() -> None:
    result = asyncio.run(LR.task_vision_analyze())
    vision = result["loadingRobotVision"]
    assert "detectedObjects" in vision


def test_vision_analyze_with_detections_kwarg() -> None:
    result = asyncio.run(LR.task_vision_analyze(detections=[{"label": "box", "count": 3}]))
    assert isinstance(result, dict)


# ─── task_plan_load ──────────────────────────────────────────────────────────

def test_plan_load_returns_dict() -> None:
    result = asyncio.run(LR.task_plan_load())
    assert isinstance(result, dict)


def test_plan_load_has_plan_key() -> None:
    result = asyncio.run(LR.task_plan_load())
    assert "loadingRobotLoadPlan" in result


def test_plan_load_empty_cargo_returns_empty_plan() -> None:
    result = asyncio.run(LR.task_plan_load(cargoItems=[]))
    plan = result["loadingRobotLoadPlan"]
    assert isinstance(plan, dict)


def test_plan_load_with_safety_margin() -> None:
    result = asyncio.run(LR.task_plan_load(safetyMarginMm=100))
    assert isinstance(result, dict)


# ─── task_robot_design ───────────────────────────────────────────────────────

def test_robot_design_returns_dict() -> None:
    result = asyncio.run(LR.task_robot_design())
    assert isinstance(result, dict)


def test_robot_design_has_cell_design_key() -> None:
    result = asyncio.run(LR.task_robot_design())
    assert "loadingRobotCellDesign" in result


def test_robot_design_no_plan_returns_default() -> None:
    result = asyncio.run(LR.task_robot_design(loadPlan={}))
    assert isinstance(result["loadingRobotCellDesign"], dict)


# ─── task_mission_plan ───────────────────────────────────────────────────────

def test_mission_plan_returns_dict() -> None:
    result = asyncio.run(LR.task_mission_plan())
    assert isinstance(result, dict)


def test_mission_plan_has_mission_key() -> None:
    result = asyncio.run(LR.task_mission_plan())
    assert "loadingRobotMission" in result


def test_mission_plan_with_mission_id() -> None:
    result = asyncio.run(LR.task_mission_plan(missionId="mission-001"))
    assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# open_lei
# ═══════════════════════════════════════════════════════════════════════════════

# ─── task_gleif_manifest_plan ────────────────────────────────────────────────

def test_manifest_plan_returns_dict() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan())
    assert isinstance(result, dict)


def test_manifest_plan_has_key() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan())
    assert "openLeiGleifManifestPlan" in result


def test_manifest_plan_default_three_datasets() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan())
    plan = result["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 3


def test_manifest_plan_specific_dataset() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan(datasets=["lei-cdf"]))
    plan = result["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 1
    assert plan["datasets"][0]["datasetKind"] == "lei-cdf"


def test_manifest_plan_with_date() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan(asOfDate="2026-01-01"))
    plan = result["openLeiGleifManifestPlan"]
    assert plan["asOfDate"] == "2026-01-01"


def test_manifest_plan_mode_delta() -> None:
    result = asyncio.run(OL.task_gleif_manifest_plan(mode="delta"))
    plan = result["openLeiGleifManifestPlan"]
    assert plan["mode"] == "delta"


# ─── task_gleif_bulk_collect ─────────────────────────────────────────────────

def test_bulk_collect_dry_run_returns_plan() -> None:
    result = asyncio.run(OL.task_gleif_bulk_collect(dryRun=True))
    assert isinstance(result, dict)


def test_bulk_collect_dry_run_has_key() -> None:
    result = asyncio.run(OL.task_gleif_bulk_collect(dryRun=True))
    assert "openLeiGleifBulkCollect" in result


def test_bulk_collect_dry_run_fetch_mode_plan() -> None:
    result = asyncio.run(OL.task_gleif_bulk_collect(dryRun=True))
    body = result["openLeiGleifBulkCollect"]
    assert body["fetchMode"] == "plan"


def test_bulk_collect_rr_cdf_no_fetch() -> None:
    result = asyncio.run(OL.task_gleif_bulk_collect(datasetKind="rr-cdf"))
    assert "openLeiGleifBulkCollect" in result


# ─── task_gleif_record_normalize ─────────────────────────────────────────────

def test_record_normalize_no_input_returns_dict() -> None:
    result = asyncio.run(OL.task_gleif_record_normalize())
    assert isinstance(result, dict)


def test_record_normalize_has_key() -> None:
    result = asyncio.run(OL.task_gleif_record_normalize())
    assert "openLeiGleifRecordNormalize" in result


def test_record_normalize_empty_records() -> None:
    result = asyncio.run(OL.task_gleif_record_normalize(records=[]))
    body = result["openLeiGleifRecordNormalize"]
    assert body["recordsRead"] == 0


# ─── task_gleif_ems_match ─────────────────────────────────────────────────────

def test_ems_match_no_input_returns_dict() -> None:
    result = asyncio.run(OL.task_gleif_ems_match())
    assert isinstance(result, dict)


def test_ems_match_has_key() -> None:
    result = asyncio.run(OL.task_gleif_ems_match())
    assert "openLeiGleifEmsMatch" in result


def test_ems_match_empty_rows_zero_candidates() -> None:
    result = asyncio.run(OL.task_gleif_ems_match(entityRows=[]))
    body = result["openLeiGleifEmsMatch"]
    assert body["candidateCount"] == 0


def test_ems_match_with_matching_entity() -> None:
    result = asyncio.run(OL.task_gleif_ems_match(
        entityRows=[{"legal_name": "Acme Electronics Manufacturing", "country": "US", "lei": "ABCDEF"}],
    ))
    body = result["openLeiGleifEmsMatch"]
    assert body["candidateCount"] == 1
