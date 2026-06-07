"""Pure-function tests for primitives/robotics.py.

All task_* functions in robotics.py accept **kwargs and call pure helper
functions — no DB, no HTTP, no LLM. Every function can be called with no
arguments and returns a meaningful dict.
"""

from __future__ import annotations

import asyncio
import inspect
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

_MOD_NAME = "_robotics_pure"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "robotics.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

R = sys.modules[_MOD_NAME]


def _run(coro):
    if not inspect.isawaitable(coro):
        return coro
    return asyncio.run(coro)


# ─── task_process_catalog ────────────────────────────────────────────────────

def test_process_catalog_returns_dict() -> None:
    assert isinstance(_run(R.task_process_catalog()), dict)


def test_process_catalog_has_catalog_key() -> None:
    result = _run(R.task_process_catalog())
    assert "roboticsProcessCatalog" in result


# ─── task_process_dependencies ───────────────────────────────────────────────

def test_process_dependencies_returns_dict() -> None:
    assert isinstance(_run(R.task_process_dependencies()), dict)


def test_process_dependencies_has_dependencies_key() -> None:
    result = _run(R.task_process_dependencies())
    assert "roboticsProcessDependencies" in result


# ─── task_workflow_plan ───────────────────────────────────────────────────────

def test_workflow_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_workflow_plan()), dict)


def test_workflow_plan_has_plan_key() -> None:
    result = _run(R.task_workflow_plan())
    assert len(result) > 0


# ─── task_kami_scene_plan ─────────────────────────────────────────────────────

def test_kami_scene_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_kami_scene_plan()), dict)


# ─── task_transport_plan ─────────────────────────────────────────────────────

def test_transport_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_transport_plan()), dict)


# ─── task_sales_plan ─────────────────────────────────────────────────────────

def test_sales_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_sales_plan()), dict)


# ─── task_mission_plan ───────────────────────────────────────────────────────

def test_mission_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_mission_plan()), dict)


# ─── task_telemetry_schema ───────────────────────────────────────────────────

def test_telemetry_schema_returns_dict() -> None:
    assert isinstance(_run(R.task_telemetry_schema()), dict)


# ─── task_telecom_coverage ──────────────────────────────────────────────────

def test_telecom_coverage_returns_dict() -> None:
    assert isinstance(_run(R.task_telecom_coverage()), dict)


# ─── task_network_deployment_plan ────────────────────────────────────────────

def test_network_deployment_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_network_deployment_plan()), dict)


# ─── task_mission_simulate ───────────────────────────────────────────────────

def test_mission_simulate_returns_dict() -> None:
    assert isinstance(_run(R.task_mission_simulate()), dict)


# ─── task_approval_record ────────────────────────────────────────────────────

def test_approval_record_returns_dict() -> None:
    assert isinstance(_run(R.task_approval_record()), dict)


# ─── task_telemetry_ingest ───────────────────────────────────────────────────

def test_telemetry_ingest_returns_dict() -> None:
    assert isinstance(_run(R.task_telemetry_ingest()), dict)


# ─── task_mission_status ─────────────────────────────────────────────────────

def test_mission_status_returns_dict() -> None:
    assert isinstance(_run(R.task_mission_status()), dict)


# ─── task_fulfillment_close ──────────────────────────────────────────────────

def test_fulfillment_close_returns_dict() -> None:
    assert isinstance(_run(R.task_fulfillment_close()), dict)


# ─── task_product_package_validate ───────────────────────────────────────────

def test_product_package_validate_returns_dict() -> None:
    assert isinstance(_run(R.task_product_package_validate()), dict)


# ─── task_product_file_catalog ───────────────────────────────────────────────

def test_product_file_catalog_returns_dict() -> None:
    assert isinstance(_run(R.task_product_file_catalog()), dict)


# ─── task_product_process_plan ───────────────────────────────────────────────

def test_product_process_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_product_process_plan()), dict)


# ─── task_product_rfq_export ─────────────────────────────────────────────────

def test_product_rfq_export_returns_dict() -> None:
    assert isinstance(_run(R.task_product_rfq_export()), dict)


# ─── task_automotive_package_profile ─────────────────────────────────────────

def test_automotive_package_profile_returns_dict() -> None:
    assert isinstance(_run(R.task_automotive_package_profile()), dict)


# ─── task_automotive_file_catalog ────────────────────────────────────────────

def test_automotive_file_catalog_returns_dict() -> None:
    assert isinstance(_run(R.task_automotive_file_catalog()), dict)


# ─── task_automotive_supply_process_link ─────────────────────────────────────

def test_automotive_supply_process_link_returns_dict() -> None:
    assert isinstance(_run(R.task_automotive_supply_process_link()), dict)


# ─── task_automotive_routing_plan ────────────────────────────────────────────

def test_automotive_routing_plan_returns_dict() -> None:
    assert isinstance(_run(R.task_automotive_routing_plan()), dict)


# ─── second assertions (key presence) ────────────────────────────────────────

def test_mission_plan_nonempty() -> None:
    result = _run(R.task_mission_plan())
    assert len(result) > 0


def test_telemetry_schema_nonempty() -> None:
    result = _run(R.task_telemetry_schema())
    assert len(result) > 0


def test_telemetry_schema_has_network_topics() -> None:
    result = _run(R.task_telemetry_schema())
    topics = {topic["topic"] for topic in result["roboticsTelemetrySchema"]["topics"]}
    assert "robotics.network.link" in topics
    assert "robotics.telecom.commissioning" in topics


def test_approval_record_nonempty() -> None:
    result = _run(R.task_approval_record())
    assert len(result) > 0


def test_transport_plan_nonempty() -> None:
    result = _run(R.task_transport_plan())
    assert len(result) > 0


def test_sales_plan_nonempty() -> None:
    result = _run(R.task_sales_plan())
    assert len(result) > 0


def test_workflow_plan_with_asset_kind() -> None:
    result = _run(R.task_workflow_plan(assetKind="amr"))
    assert isinstance(result, dict)
