"""Tests for async task wrapper functions in primitives/robotics.py.

All task_* functions are thin kwargs wrappers around pure computation:
no DB, no HTTP, no asyncio side-effects. They are directly testable
with asyncio.run() and default (empty) arguments.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import robotics as R  # noqa: E402


# ─── helpers ─────────────────────────────────────────────────────────────────

def _run(coro):
    if not inspect.isawaitable(coro):
        return coro
    return asyncio.run(coro)


# ─── task_process_catalog ─────────────────────────────────────────────────────

def test_process_catalog_returns_dict() -> None:
    result = _run(R.task_process_catalog())
    assert isinstance(result, dict)


def test_process_catalog_has_key() -> None:
    result = _run(R.task_process_catalog())
    assert "roboticsProcessCatalog" in result


def test_process_catalog_inner_has_forms() -> None:
    result = _run(R.task_process_catalog())
    assert "forms" in result["roboticsProcessCatalog"]


def test_process_catalog_inner_has_dependencies() -> None:
    result = _run(R.task_process_catalog())
    assert "dependencies" in result["roboticsProcessCatalog"]


# ─── task_process_dependencies ────────────────────────────────────────────────

def test_process_dependencies_returns_dict() -> None:
    result = _run(R.task_process_dependencies())
    assert isinstance(result, dict)


def test_process_dependencies_has_key() -> None:
    result = _run(R.task_process_dependencies())
    assert "roboticsProcessDependencies" in result


# ─── task_workflow_plan ───────────────────────────────────────────────────────

def test_workflow_plan_returns_dict() -> None:
    result = _run(R.task_workflow_plan())
    assert isinstance(result, dict)


def test_workflow_plan_with_processes() -> None:
    result = _run(R.task_workflow_plan(processes=["sales", "requirements"]))
    assert isinstance(result, dict)


# ─── task_kami_scene_plan ─────────────────────────────────────────────────────

def test_kami_scene_plan_returns_dict() -> None:
    result = _run(R.task_kami_scene_plan())
    assert isinstance(result, dict)


def test_kami_scene_plan_with_cell_id() -> None:
    result = _run(R.task_kami_scene_plan(cellId="cell-42", assetKind="robot-arm"))
    assert isinstance(result, dict)


# ─── task_transport_plan ──────────────────────────────────────────────────────

def test_transport_plan_returns_dict() -> None:
    result = _run(R.task_transport_plan())
    assert isinstance(result, dict)


def test_transport_plan_with_args() -> None:
    result = _run(R.task_transport_plan(
        assetKind="agv",
        origin="Dock A",
        destination="Outbound",
    ))
    assert isinstance(result, dict)


# ─── task_sales_plan ─────────────────────────────────────────────────────────

def test_sales_plan_returns_dict() -> None:
    result = _run(R.task_sales_plan())
    assert isinstance(result, dict)


def test_sales_plan_with_customer() -> None:
    result = _run(R.task_sales_plan(customerId="cust-1", quantity=10))
    assert isinstance(result, dict)


# ─── task_mission_plan ───────────────────────────────────────────────────────

def test_mission_plan_returns_dict() -> None:
    result = _run(R.task_mission_plan())
    assert isinstance(result, dict)


def test_mission_plan_with_args() -> None:
    result = _run(R.task_mission_plan(
        missionId="m1",
        assetKind="robot-arm",
        missionType="welding",
    ))
    assert isinstance(result, dict)


# ─── task_telemetry_schema ───────────────────────────────────────────────────

def test_telemetry_schema_returns_dict() -> None:
    result = _run(R.task_telemetry_schema())
    assert isinstance(result, dict)


def test_telemetry_schema_with_schema_id() -> None:
    result = _run(R.task_telemetry_schema(schemaId="telem-v2"))
    assert isinstance(result, dict)


# ─── task_mission_simulate ───────────────────────────────────────────────────

def test_mission_simulate_returns_dict() -> None:
    result = _run(R.task_mission_simulate())
    assert isinstance(result, dict)


def test_mission_simulate_with_args() -> None:
    result = _run(R.task_mission_simulate(missionId="m1", assetKind="agv"))
    assert isinstance(result, dict)


# ─── task_approval_record ────────────────────────────────────────────────────

def test_approval_record_returns_dict() -> None:
    result = _run(R.task_approval_record())
    assert isinstance(result, dict)


def test_approval_record_with_decision() -> None:
    result = _run(R.task_approval_record(decision="approve", requestId="req-1"))
    assert isinstance(result, dict)


# ─── task_telemetry_ingest ───────────────────────────────────────────────────

def test_telemetry_ingest_returns_dict() -> None:
    result = _run(R.task_telemetry_ingest())
    assert isinstance(result, dict)


def test_telemetry_ingest_with_payload() -> None:
    result = _run(R.task_telemetry_ingest(
        topic="robotics.work.state",
        payload={"state": "running"},
    ))
    assert isinstance(result, dict)


# ─── task_mission_status ─────────────────────────────────────────────────────

def test_mission_status_returns_dict() -> None:
    result = _run(R.task_mission_status())
    assert isinstance(result, dict)


def test_mission_status_with_mission_id() -> None:
    result = _run(R.task_mission_status(missionId="m-123"))
    assert isinstance(result, dict)


# ─── task_fulfillment_close ──────────────────────────────────────────────────

def test_fulfillment_close_returns_dict() -> None:
    result = _run(R.task_fulfillment_close())
    assert isinstance(result, dict)


def test_fulfillment_close_with_request_id() -> None:
    result = _run(R.task_fulfillment_close(requestId="req-99"))
    assert isinstance(result, dict)


# ─── task_product_package_validate ───────────────────────────────────────────

def test_product_package_validate_returns_dict() -> None:
    result = _run(R.task_product_package_validate())
    assert isinstance(result, dict)


def test_product_package_validate_with_args() -> None:
    result = _run(R.task_product_package_validate(
        requestId="req-1",
        packageId="pkg-1",
        assetKind="sensor",
    ))
    assert isinstance(result, dict)


# ─── task_product_file_catalog ───────────────────────────────────────────────

def test_product_file_catalog_returns_dict() -> None:
    result = _run(R.task_product_file_catalog())
    assert isinstance(result, dict)


# ─── task_product_process_plan ───────────────────────────────────────────────

def test_product_process_plan_returns_dict() -> None:
    result = _run(R.task_product_process_plan())
    assert isinstance(result, dict)


# ─── task_product_rfq_export ─────────────────────────────────────────────────

def test_product_rfq_export_returns_dict() -> None:
    result = _run(R.task_product_rfq_export())
    assert isinstance(result, dict)


def test_product_rfq_export_with_args() -> None:
    result = _run(R.task_product_rfq_export(
        requestId="req-1",
        packageId="pkg-1",
        quantity=5,
        incoterms="CIF",
    ))
    assert isinstance(result, dict)


# ─── task_automotive_package_profile ─────────────────────────────────────────

def test_automotive_package_profile_returns_dict() -> None:
    result = _run(R.task_automotive_package_profile())
    assert isinstance(result, dict)


def test_automotive_package_profile_with_args() -> None:
    result = _run(R.task_automotive_package_profile(
        vehicleProgram="EV-2026",
        vehicleKind="electric_vehicle",
    ))
    assert isinstance(result, dict)


# ─── task_automotive_file_catalog ────────────────────────────────────────────

def test_automotive_file_catalog_returns_dict() -> None:
    result = _run(R.task_automotive_file_catalog())
    assert isinstance(result, dict)


# ─── task_automotive_supply_process_link ─────────────────────────────────────

def test_automotive_supply_process_link_returns_dict() -> None:
    result = _run(R.task_automotive_supply_process_link())
    assert isinstance(result, dict)


# ─── task_automotive_routing_plan ────────────────────────────────────────────

def test_automotive_routing_plan_returns_dict() -> None:
    result = _run(R.task_automotive_routing_plan())
    assert isinstance(result, dict)


# ─── task_automotive_quality_gate ────────────────────────────────────────────

def test_automotive_quality_gate_returns_dict() -> None:
    result = _run(R.task_automotive_quality_gate())
    assert isinstance(result, dict)


# ─── task_automotive_eol_plan ────────────────────────────────────────────────

def test_automotive_eol_plan_returns_dict() -> None:
    result = _run(R.task_automotive_eol_plan())
    assert isinstance(result, dict)


# ─── task_ems_company_search ─────────────────────────────────────────────────

def test_ems_company_search_returns_dict() -> None:
    result = _run(R.task_ems_company_search())
    assert isinstance(result, dict)


def test_ems_company_search_with_query() -> None:
    result = _run(R.task_ems_company_search(query="robot welding"))
    assert isinstance(result, dict)


# ─── task_ems_company_profile ────────────────────────────────────────────────

def test_ems_company_profile_returns_dict() -> None:
    result = _run(R.task_ems_company_profile())
    assert isinstance(result, dict)


def test_ems_company_profile_with_company_id() -> None:
    result = _run(R.task_ems_company_profile(companyId="ems-co-1"))
    assert isinstance(result, dict)


# ─── task_ems_supplier_shortlist ─────────────────────────────────────────────

def test_ems_supplier_shortlist_returns_dict() -> None:
    result = _run(R.task_ems_supplier_shortlist())
    assert isinstance(result, dict)


def test_ems_supplier_shortlist_with_criteria() -> None:
    result = _run(R.task_ems_supplier_shortlist(
        assetKind="robot-arm",
        region="asia",
    ))
    assert isinstance(result, dict)


# ─── robotics_kami_scene (untested underlying function) ──────────────────────

def test_kami_scene_returns_dict() -> None:
    result = R.robotics_kami_scene(cell_id="test-cell", asset_kind="agv")
    assert isinstance(result, dict)


def test_kami_scene_default_asset_kind() -> None:
    result = R.robotics_kami_scene(cell_id="c1", asset_kind="robot-arm")
    assert isinstance(result, dict)
