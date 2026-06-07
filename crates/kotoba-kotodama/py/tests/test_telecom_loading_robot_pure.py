"""Pure-path tests for telecom.py and loading_robot.py task functions.

telecom.py:
  - All 6 tasks tested with dryRun=True — the `_insert()` helper skips DB
    when dry_run=True, making these tasks pure computations when required
    fields are supplied.

loading_robot.py:
  - All 4 tasks are pure computations with no DB/HTTP dependencies.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom as TC
from kotodama.primitives import loading_robot as LR


# ══════════════════════════════════════════════════════════════════════════════
# telecom — dryRun=True paths
# ══════════════════════════════════════════════════════════════════════════════

def test_telecom_subscriber_onboard_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_subscriber_onboard(
        customerName="Test User",
        msisdn="09012345678",
        kycStatus="verified",
        planId="plan-01",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_subscriber_onboard_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_subscriber_onboard(
        customerName="Test User",
        msisdn="09012345678",
        kycStatus="verified",
        planId="plan-01",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_telecom_subscriber_onboard_dry_run_has_vertex_id() -> None:
    result = asyncio.run(TC.task_telecom_subscriber_onboard(
        customerName="Test User",
        msisdn="09012345678",
        kycStatus="verified",
        planId="plan-01",
        dryRun=True,
    ))
    assert "vertexId" in result


def test_telecom_sim_activate_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_sim_activate(
        iccid="8981000000000000001",
        subscriberId="sub-001",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_sim_activate_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_sim_activate(
        iccid="8981000000000000001",
        subscriberId="sub-001",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_telecom_service_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_service_provision(
        subscriberId="sub-001",
        serviceType="voice",
        planId="plan-01",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_service_provision_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_service_provision(
        subscriberId="sub-001",
        serviceType="voice",
        planId="plan-01",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_telecom_usage_record_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_usage_record(
        subscriberId="sub-001",
        serviceId="svc-001",
        usageType="voice",
        startedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_usage_record_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_usage_record(
        subscriberId="sub-001",
        serviceId="svc-001",
        usageType="voice",
        startedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_telecom_billing_cycle_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_billing_cycle(
        subscriberId="sub-001",
        periodStart="2026-01-01",
        periodEnd="2026-01-31",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_billing_cycle_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_billing_cycle(
        subscriberId="sub-001",
        periodStart="2026-01-01",
        periodEnd="2026-01-31",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_telecom_sla_escalate_dry_run_returns_dict() -> None:
    result = asyncio.run(TC.task_telecom_sla_escalate(
        serviceId="svc-001",
        breachType="outage",
        severity="major",
        observedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_telecom_sla_escalate_dry_run_ok_true() -> None:
    result = asyncio.run(TC.task_telecom_sla_escalate(
        serviceId="svc-001",
        breachType="outage",
        severity="major",
        observedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


# ══════════════════════════════════════════════════════════════════════════════
# loading_robot — pure computation tasks
# ══════════════════════════════════════════════════════════════════════════════

def test_loading_robot_vision_analyze_empty_returns_dict() -> None:
    result = asyncio.run(LR.task_vision_analyze())
    assert isinstance(result, dict)


def test_loading_robot_vision_analyze_has_constraints() -> None:
    result = asyncio.run(LR.task_vision_analyze())
    assert "loadingRobotVision" in result or "constraints" in result or "confidence" in result


def test_loading_robot_vision_analyze_with_image_uri() -> None:
    result = asyncio.run(LR.task_vision_analyze(imageUri="at://example/image/001"))
    assert isinstance(result, dict)


def test_loading_robot_plan_load_empty_returns_dict() -> None:
    result = asyncio.run(LR.task_plan_load())
    assert isinstance(result, dict)


def test_loading_robot_plan_load_has_expected_key() -> None:
    result = asyncio.run(LR.task_plan_load())
    # Should have some kind of plan key or status
    assert len(result) > 0


def test_loading_robot_plan_load_with_cargo() -> None:
    result = asyncio.run(LR.task_plan_load(cargoItems=[{"label": "box", "widthMm": 300}]))
    assert isinstance(result, dict)


def test_loading_robot_robot_design_empty_returns_dict() -> None:
    result = asyncio.run(LR.task_robot_design())
    assert isinstance(result, dict)


def test_loading_robot_robot_design_has_keys() -> None:
    result = asyncio.run(LR.task_robot_design())
    assert len(result) > 0


def test_loading_robot_mission_plan_empty_returns_dict() -> None:
    result = asyncio.run(LR.task_mission_plan())
    assert isinstance(result, dict)


def test_loading_robot_mission_plan_has_keys() -> None:
    result = asyncio.run(LR.task_mission_plan())
    assert len(result) > 0


def test_loading_robot_mission_plan_with_mission_id() -> None:
    result = asyncio.run(LR.task_mission_plan(missionId="mission-001"))
    assert isinstance(result, dict)
