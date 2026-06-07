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


robotics = _load("_robotics_primitives", "primitives/robotics.py")


def test_workflow_plan_covers_sales_manufacturing_transport_finance():
    out = robotics.robotics_workflow_plan(
        request_id="req-1",
        processes=["sales", "manufacturing", "transport", "finance"],
    )
    plan = out["roboticsWorkflowPlan"]
    assert plan["requestId"] == "req-1"
    assert [form["process"] for form in plan["forms"]] == ["sales", "manufacturing", "transport", "finance"]
    assert "robotics.workflow.plan" in plan["mcpTools"]
    assert "robotics.process.dependencies" in plan["mcpTools"]
    assert "erp.salesOrder" in plan["integrationRecords"]
    assert [dep["id"] for dep in plan["dependencies"]] == ["dep-transport-finance"]
    assert "dep-production-manufacturing" in [dep["id"] for dep in plan["missingPrerequisites"]]
    assert plan["kamiReview"]["sceneNodes"]


def test_transport_sales_and_mission_plans_are_agent_ready():
    transport = robotics.robotics_transport_plan(asset_kind="drone")["roboticsTransportPlan"]
    sales = robotics.robotics_sales_plan(customer_id="c1", quantity=3)["roboticsSalesPlan"]
    mission = robotics.robotics_mission_plan(asset_kind="agv", route_id=transport["routeId"])["roboticsMission"]
    assert transport["mode"] == "air"
    assert "tms.proofOfDelivery" in transport["handoffRecords"]
    assert sales["quantity"] == 3
    assert mission["commandProtocol"] == "vda5050-json"
    assert mission["commands"][0]["command"] == "validate-safety-envelope"


def test_simulation_telemetry_and_approval_chain():
    mission = robotics.robotics_mission_plan(asset_kind="robot-arm")["roboticsMission"]
    sim = robotics.robotics_mission_simulate(mission=mission)["roboticsMissionSimulation"]
    telemetry = robotics.robotics_telemetry_schema()["roboticsTelemetrySchema"]
    approval = robotics.robotics_approval_record(
        request_id="req-1",
        decision="approve",
        approver_did="did:web:ops.etzhayyim.com",
    )["roboticsApprovalRecord"]
    assert sim["status"] == "pass"
    assert "robotics.safety.event" in [topic["topic"] for topic in telemetry["topics"]]
    assert approval["auditAction"] == "robotics.approval.approve"


def test_telemetry_status_and_fulfillment_close_chain():
    simulation = robotics.robotics_mission_simulate()["roboticsMissionSimulation"]
    approval = robotics.robotics_approval_record(decision="approve")["roboticsApprovalRecord"]
    frame = robotics.robotics_telemetry_ingest(
        payload={
            "missionId": "robotics-mission",
            "state": "completed",
            "stepId": "handoff",
            "timestamp": "2026-04-25T00:00:00Z",
        }
    )["roboticsTelemetryFrame"]
    status = robotics.robotics_mission_status(
        simulation=simulation,
        approval=approval,
        telemetry_frames=[frame],
    )["roboticsMissionStatus"]
    close = robotics.robotics_fulfillment_close(
        records=["qms.qualityRelease", "tms.proofOfDelivery", "erp.salesOrder", "erp.invoice"]
    )["roboticsFulfillmentClose"]
    assert frame["accepted"] is True
    assert status["state"] == "completed"
    assert close["status"] == "ready-to-invoice"


def test_ems_company_data_chain_shortlists_suppliers():
    search = robotics.robotics_ems_company_search(
        query="robot arm PCBA box build",
        regions=["CN", "JP"],
        capabilities=["PCBA", "box-build"],
    )["roboticsEmsCompanySearch"]
    profiles = robotics.robotics_ems_company_profile(
        companies=search["candidates"],
        source="public-search",
    )["roboticsEmsCompanyProfiles"]
    shortlist = robotics.robotics_ems_supplier_shortlist(
        request_id="rfq-1",
        rfq={"preferredRegion": "JP"},
        company_profiles=profiles["companyProfiles"],
        required_capabilities=["PCBA", "box-build"],
    )["roboticsEmsSupplierShortlist"]
    assert search["candidates"][0]["capabilities"] == ["PCBA", "box-build"]
    assert profiles["source"] == "public-search"
    assert shortlist["recommendedSupplierIds"]
    assert shortlist["supplierCandidates"][0]["decision"] == "shortlist"


def test_product_package_chain_builds_rfq_export():
    manifest = {
        "files": [
            {"path": "robot-arm.step", "sha256": "a" * 64},
            {"path": "bom.csv", "sha256": "b" * 64},
            {"path": "inspection.pdf", "sha256": "c" * 64},
            {"path": "program.nc", "sha256": "d" * 64},
        ]
    }
    validation = robotics.robotics_product_package_validate(
        request_id="req-1",
        package_id="pkg-1",
        asset_kind="robot-arm",
        package_manifest=manifest,
    )["roboticsProductPackageValidation"]
    catalog = robotics.robotics_product_file_catalog(
        package_id="pkg-1",
        package_manifest=manifest,
        package_validation=validation,
    )["roboticsProductFileCatalog"]
    plan = robotics.robotics_product_process_plan(
        request_id="req-1",
        package_id="pkg-1",
        asset_kind="robot-arm",
        file_catalog=catalog,
    )["roboticsManufacturingProcessPlan"]
    rfq = robotics.robotics_product_rfq_export(
        request_id="req-1",
        package_id="pkg-1",
        quantity=10,
        file_catalog=catalog,
        process_plan=plan,
    )["roboticsRfqExport"]
    assert validation["status"] == "pass"
    assert catalog["byKind"]["cad"]
    assert "mes.workOrder" in plan["integrationRecords"]
    assert rfq["quantity"] == 10
    assert rfq["attachments"]


def test_automotive_package_chain_reaches_quality_and_eol():
    manifest = {"files": ["vehicle.step", "vehicle-bom.csv", "control-plan.pdf"]}
    profile = robotics.automotive_package_profile(
        request_id="req-v",
        package_id="pkg-v",
        vehicle_program="program-a",
        plant_id="plant-1",
        line_id="line-1",
        package_manifest=manifest,
    )["automotiveManufacturingProfile"]
    validation = robotics.robotics_product_package_validate(
        package_id="pkg-v",
        asset_kind="autonomous_vehicle",
        package_manifest=manifest,
    )["roboticsProductPackageValidation"]
    catalog = robotics.automotive_file_catalog(
        packageId="pkg-v",
        packageManifest=manifest,
        packageValidation=validation,
    )["roboticsProductFileCatalog"]
    supply = robotics.automotive_supply_process_link(
        request_id="req-v",
        package_id="pkg-v",
        vehicle_program="program-a",
        file_catalog=catalog,
        vehicle_profile=profile,
    )["automotiveSupplyProcessGraph"]
    routing = robotics.automotive_routing_plan(
        request_id="req-v",
        package_id="pkg-v",
        vehicle_profile=profile,
        file_catalog=catalog,
    )["automotiveRoutingPlan"]
    quality = robotics.automotive_quality_gate(
        request_id="req-v",
        package_id="pkg-v",
        vehicle_program="program-a",
        evidence={"profile": profile, "catalog": catalog, "routing": routing},
    )["automotiveQualityGateResult"]
    eol = robotics.automotive_eol_plan(
        request_id="req-v",
        package_id="pkg-v",
        vehicle_profile=profile,
        file_catalog=catalog,
        routing_plan=routing,
    )["automotiveEolPlan"]
    assert profile["standards"]
    assert supply["links"]
    assert routing["operations"][-1]["id"] == "quality-gate"
    assert quality["status"] == "review"
    assert "digital product passport export" in eol["steps"]


def test_register_exposes_robotics_task_types():
    registered: list[str] = []

    class FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            assert single_value is False
            assert timeout_ms == 456
            registered.append(task_type)

            def decorator(fn):
                return fn

            return decorator

    robotics.register(FakeWorker(), timeout_ms=456)
    assert registered == [
        "robotics.process.catalog",
        "robotics.process.dependencies",
        "robotics.workflow.plan",
        "robotics.kami.scene.plan",
        "robotics.transport.plan",
        "robotics.sales.plan",
        "robotics.mission.plan",
        "robotics.telemetry.schema",
        "robotics.mission.simulate",
        "robotics.approval.record",
        "robotics.telemetry.ingest",
        "robotics.mission.status",
        "robotics.fulfillment.close",
        "robotics.product.package.validate",
        "robotics.product.file.catalog",
        "robotics.product.process.plan",
        "robotics.product.rfq.export",
        "automotive.package.profile",
        "automotive.file.catalog",
        "automotive.supply.process.link",
        "automotive.routing.plan",
        "automotive.quality.gate",
        "automotive.eol.plan",
        "robotics.ems.company.search",
        "robotics.ems.company.profile",
        "robotics.ems.supplier.shortlist",
    ]
