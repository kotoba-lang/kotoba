from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PROCESS_FORMS: list[dict[str, Any]] = [
    {"id": "robotics-sales-intake-v1", "process": "sales", "title": "Sales order / RFQ intake", "requiredFields": ["customerId", "itemOrService", "quantity", "targetDate", "commercialTerms"], "outputRecords": ["erp.salesOrder", "crm.opportunity", "requirements.rfq"]},
    {"id": "robotics-requirements-v1", "process": "requirements", "title": "Product and service requirements", "requiredFields": ["specification", "acceptanceCriteria", "regulatoryConstraints", "budget"], "outputRecords": ["requirements.acceptanceCriteria", "plm.requirementSet"]},
    {"id": "robotics-engineering-release-v1", "process": "engineering", "title": "CAD / CAE / CAM engineering release", "requiredFields": ["cadRevision", "bomRevision", "simulationResult", "machineProgram"], "outputRecords": ["cad.partModel", "plm.ebom", "cam.machineProgram", "qms.inspectionPlan"]},
    {"id": "robotics-procurement-v1", "process": "procurement", "title": "Material and vendor procurement", "requiredFields": ["materialSpec", "supplier", "leadTime", "cost", "certificateRequired"], "outputRecords": ["erp.purchaseOrder", "wms.inboundLot", "qms.materialCertificate"]},
    {"id": "robotics-production-plan-v1", "process": "production-planning", "title": "Production scheduling and capacity plan", "requiredFields": ["workOrder", "routing", "machine", "operatorOrRobot", "plannedWindow"], "outputRecords": ["mes.workOrder", "mes.operation", "cmms.assetReservation"]},
    {"id": "robotics-manufacturing-execution-v1", "process": "manufacturing", "title": "Robot work execution", "requiredFields": ["missionId", "robotAsset", "programRef", "fixture", "safetyEnvelope"], "outputRecords": ["scada.machineState", "mes.operatorEvent", "digital-twin.telemetryFrame"]},
    {"id": "robotics-quality-release-v1", "process": "quality", "title": "Inspection and quality release", "requiredFields": ["inspectionPlan", "measurementData", "nonconformance", "releaseDecision"], "outputRecords": ["qms.inspectionResult", "qms.nonconformance", "qms.qualityRelease"]},
    {"id": "robotics-warehouse-v1", "process": "warehouse", "title": "Warehouse picking and staging", "requiredFields": ["inventoryLot", "pickTask", "bin", "stagingLocation", "custodyScan"], "outputRecords": ["wms.pickTask", "wms.inventoryLot", "wms.replenishmentTask"]},
    {"id": "robotics-transport-v1", "process": "transport", "title": "Transport and route planning", "requiredFields": ["origin", "destination", "assetKind", "routeWindow", "handoff"], "outputRecords": ["tms.shipment", "tms.route", "fleet-control.dispatch", "tms.proofOfDelivery"]},
    {"id": "robotics-installation-v1", "process": "installation", "title": "Installation / commissioning", "requiredFields": ["site", "equipment", "testProtocol", "operatorApproval"], "outputRecords": ["digital-twin.stateSnapshot", "qms.acceptanceReport", "cmms.asset"]},
    {"id": "robotics-maintenance-v1", "process": "maintenance", "title": "Maintenance and reliability", "requiredFields": ["asset", "failureMode", "sparePart", "maintenanceWindow"], "outputRecords": ["cmms.workRequest", "cmms.maintenancePlan", "cmms.sparePart"]},
    {"id": "robotics-finance-v1", "process": "finance", "title": "Costing, billing, and margin close", "requiredFields": ["costRollup", "shipmentProof", "qualityRelease", "invoiceTerm"], "outputRecords": ["erp.costRollup", "erp.invoice", "erp.revenueRecognition"]},
]

PROCESS_DEPENDENCIES: list[dict[str, Any]] = [
    {"id": "dep-sales-requirements", "from": "sales", "to": "requirements", "records": ["erp.salesOrder", "crm.opportunity", "requirements.rfq"], "gate": "commercial terms and requested scope accepted"},
    {"id": "dep-requirements-engineering", "from": "requirements", "to": "engineering", "records": ["requirements.acceptanceCriteria", "plm.requirementSet"], "gate": "requirements baseline approved"},
    {"id": "dep-requirements-procurement", "from": "requirements", "to": "procurement", "records": ["materialSpec", "budget", "supplierConstraints"], "gate": "make-buy and sourcing constraints approved"},
    {"id": "dep-engineering-production", "from": "engineering", "to": "production-planning", "records": ["cad.partModel", "plm.ebom", "cam.machineProgram", "qms.inspectionPlan"], "gate": "engineering release package complete"},
    {"id": "dep-procurement-production", "from": "procurement", "to": "production-planning", "records": ["erp.purchaseOrder", "wms.inboundLot", "qms.materialCertificate"], "gate": "critical material availability confirmed"},
    {"id": "dep-production-manufacturing", "from": "production-planning", "to": "manufacturing", "records": ["mes.workOrder", "mes.operation", "cmms.assetReservation"], "gate": "work order dispatched and asset reserved"},
    {"id": "dep-manufacturing-quality", "from": "manufacturing", "to": "quality", "records": ["scada.machineState", "mes.operatorEvent", "digital-twin.telemetryFrame"], "gate": "manufacturing telemetry and traceability captured"},
    {"id": "dep-quality-warehouse", "from": "quality", "to": "warehouse", "records": ["qms.inspectionResult", "qms.qualityRelease"], "gate": "quality release approved"},
    {"id": "dep-warehouse-transport", "from": "warehouse", "to": "transport", "records": ["wms.pickTask", "wms.inventoryLot", "wms.replenishmentTask"], "gate": "picked inventory staged and custody scanned"},
    {"id": "dep-transport-installation", "from": "transport", "to": "installation", "records": ["tms.shipment", "tms.route", "tms.proofOfDelivery"], "gate": "delivery proof accepted"},
    {"id": "dep-transport-finance", "from": "transport", "to": "finance", "records": ["tms.proofOfDelivery", "erp.salesOrder"], "gate": "delivery proof and order terms matched"},
    {"id": "dep-installation-maintenance", "from": "installation", "to": "maintenance", "records": ["digital-twin.stateSnapshot", "qms.acceptanceReport", "cmms.asset"], "gate": "commissioned asset accepted into service"},
]

TELECOM_ROBOTICS_MEDIA: list[dict[str, Any]] = [
    {
        "medium": "cellular-ran",
        "roboticsScope": "cell-site survey, mast/antenna install, RAN node commissioning, KPI walk/drive test",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": ["vertex_telecom_cell_site", "vertex_telecom_ran_node", "vertex_telecom_kpi_sample"],
        "robotAssets": ["site-survey-ugv", "mast-climb-assist", "rf-test-drone"],
        "gaps": ["no gNB/eNB PHY/MAC implementation", "no SDR control loop"],
    },
    {
        "medium": "satellite-ntn",
        "roboticsScope": "earth-station inspection, antenna alignment, contact-window telemetry capture",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": ["vertex_telecom_ntn_satellite", "vertex_telecom_ntn_earth_station", "vertex_telecom_ntn_contact"],
        "robotAssets": ["dish-alignment-robot", "roof-inspection-drone"],
        "gaps": ["no modem waveform implementation", "no orbit propagation runtime in robotics primitive"],
    },
    {
        "medium": "optical-fiber",
        "roboticsScope": "fiber span inspection, ROADM rack service, OTDR evidence capture",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": ["vertex_telecom_optical_fiber_span", "vertex_telecom_optical_roadm", "vertex_telecom_optical_pm_event"],
        "robotAssets": ["rack-service-arm", "fiber-inspection-robot"],
        "gaps": [],
    },
    {
        "medium": "submarine-cable",
        "roboticsScope": "ROV survey, cable fault localization, repair-fleet dispatch package",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": [
            "vertex_telecom_submarine_cable_system",
            "vertex_telecom_submarine_landing_station",
            "vertex_telecom_submarine_repeater",
            "vertex_telecom_submarine_route_segment",
            "vertex_telecom_submarine_repair_event",
        ],
        "robotAssets": ["rov-survey", "cable-deck-handling-robot"],
        "gaps": ["no wet-plant control loop or repair-vessel runtime integration"],
    },
    {
        "medium": "wlan-passpoint",
        "roboticsScope": "venue survey, AP placement validation, roaming/session test",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": ["vertex_telecom_wlan_venue", "vertex_telecom_wlan_anqp_query", "vertex_telecom_wlan_session", "vertex_telecom_wlan_mesh_node", "vertex_telecom_wlan_mesh_link"],
        "robotAssets": ["indoor-survey-robot", "wifi-test-handset-rig"],
        "gaps": ["802.11s/HWMP radio stack is modeled, not implemented"],
    },
    {
        "medium": "bluetooth-ble",
        "roboticsScope": "short-range peripheral survey and actuator/proximity telemetry capture",
        "designCoverage": "schema",
        "implementationCoverage": "planning-runtime",
        "telecomSchemas": ["vertex_telecom_bluetooth_device", "vertex_telecom_bluetooth_mesh_node", "vertex_telecom_bluetooth_observation"],
        "robotAssets": ["ble-beacon-survey-robot"],
        "gaps": ["Bluetooth Mesh transport is modeled, not implemented"],
    },
    {
        "medium": "neutron-communication",
        "roboticsScope": "hazard-gated lab experiment placeholder only",
        "designCoverage": "out-of-scope",
        "implementationCoverage": "none",
        "telecomSchemas": [],
        "robotAssets": [],
        "gaps": ["no telecom design", "no implementation", "requires separate safety and physics ADR"],
    },
    {
        "medium": "libp2p-tailmesh",
        "roboticsScope": "robot command/control overlay and field telemetry backhaul over existing actor mesh",
        "designCoverage": "implemented-overlay",
        "implementationCoverage": "implemented-overlay",
        "telecomSchemas": [],
        "robotAssets": ["any-networked-robot"],
        "gaps": ["not a radio PHY or carrier network implementation"],
    },
]


def _selected_forms(processes: Any) -> list[dict[str, Any]]:
    if not isinstance(processes, list) or not processes:
        return PROCESS_FORMS
    selected = {str(process) for process in processes}
    return [form for form in PROCESS_FORMS if form["process"] in selected]


def _dependency_projection(processes: Any) -> dict[str, list[dict[str, Any]]]:
    forms = _selected_forms(processes)
    selected = {form["process"] for form in forms}
    return {
        "dependencies": [
            dep for dep in PROCESS_DEPENDENCIES
            if dep["from"] in selected and dep["to"] in selected
        ],
        "missingPrerequisites": [
            dep for dep in PROCESS_DEPENDENCIES
            if dep["from"] not in selected and dep["to"] in selected
        ],
    }


def _stamp() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _list_str(value: Any) -> list[str]:
    return [str(item) for item in value if item] if isinstance(value, list) else []


def robotics_transport_plan(*, asset_kind: str = "agv", origin: str = "Factory dock", destination: str = "Outbound handoff") -> dict[str, Any]:
    speed_mps = {
        "forklift": 2.5,
        "agv": 1.8,
        "conveyor": 0.8,
        "truck": 16,
        "drone": 12,
        "autonomous-vehicle": 10,
    }.get(asset_kind, 2.0)
    segments = [
        {"id": "segment-01", "from": "origin", "to": "staging", "distanceMeters": 18439, "estimatedSeconds": round(18439 / speed_mps)},
        {"id": "segment-02", "from": "staging", "to": "destination", "distanceMeters": 24331, "estimatedSeconds": round(24331 / speed_mps)},
    ]
    return {
        "roboticsTransportPlan": {
            "routeId": f"robotics-route-{_stamp()}",
            "assetKind": asset_kind,
            "mode": "air" if asset_kind == "drone" else "road" if asset_kind in {"truck", "autonomous-vehicle"} else "intra-factory",
            "waypoints": [
                {"id": "origin", "label": origin, "xMm": 0, "yMm": 0, "zMm": 0},
                {"id": "staging", "label": "Warehouse staging", "xMm": 18000, "yMm": 4000, "zMm": 0},
                {"id": "destination", "label": destination, "xMm": 42000, "yMm": 8000, "zMm": 0},
            ],
            "segments": segments,
            "handoffRecords": ["wms.pickTask", "tms.shipment", "fleet-control.dispatch", "tms.proofOfDelivery"],
            "warnings": ["requires human approval before execution"],
        }
    }


def robotics_kami_scene(*, cell_id: str = "robotics-review-cell", asset_kind: str = "agv") -> dict[str, Any]:
    transport = robotics_transport_plan(asset_kind=asset_kind)["roboticsTransportPlan"]
    nodes = [
        {"id": "engineering-station", "kind": "cnc-mill", "label": "Engineering / CAM station", "position": [-420, 0, 200], "scale": [800, 500, 400], "color": "#64748b"},
        {"id": "robot-workcell", "kind": "robot-arm", "label": "Robot workcell", "position": [0, 0, 300], "scale": [900, 900, 600], "color": "#d97706"},
        {"id": "warehouse-flow", "kind": "material-handling", "label": "Warehouse and staging flow", "position": [420, 0, 150], "scale": [1600, 500, 300], "color": "#2563eb"},
        {"id": "quality-gate", "kind": "inspection", "label": "Quality gate", "position": [840, 0, 150], "scale": [500, 500, 300], "color": "#7c3aed"},
        {"id": "safety-zone", "kind": "safety-zone", "label": "Robot safety zone", "position": [0, 0, 0], "scale": [1200, 1200, 80], "color": "#ef4444"},
    ]
    nodes.extend(
        {"id": f"route-{waypoint['id']}", "kind": "material-handling", "label": waypoint["label"], "position": [waypoint["xMm"], waypoint["yMm"], waypoint["zMm"] + 20], "scale": [180, 180, 40], "color": "#2563eb"}
        for waypoint in transport["waypoints"]
    )
    return {
        "roboticsKamiScene": {
            "cellId": cell_id,
            "sceneUnits": "millimeters",
            "sceneNodes": nodes,
            "operatorActions": ["inspect reach and clearance", "approve mission before motion", "confirm telemetry and BPMN audit trail"],
            "telemetryTopics": ["robotics.asset.pose", "robotics.work.state", "robotics.transport.handoff"],
        }
    }


def robotics_workflow_plan(*, request_id: str = "robotics-request", processes: Any = None, asset_kind: str = "agv") -> dict[str, Any]:
    forms = _selected_forms(processes)
    dependency_graph = _dependency_projection(processes)
    return {
        "roboticsWorkflowPlan": {
            "requestId": request_id,
            "forms": forms,
            "dependencies": dependency_graph["dependencies"],
            "missingPrerequisites": dependency_graph["missingPrerequisites"],
            "bpmnProcesses": [
                "00-contracts/bpmn/com/etzhayyim/robotics/planRoboticsBusinessProcess.bpmn",
                "00-contracts/bpmn/com/etzhayyim/robotics/executeRoboticsWork.bpmn",
                "00-contracts/bpmn/com/etzhayyim/robotics/planRoboticsTransportAndSales.bpmn",
            ],
            "mcpTools": [
                "robotics.process.catalog",
                "robotics.workflow.plan",
                "robotics.kami.scene.plan",
                "robotics.transport.plan",
                "robotics.sales.plan",
                "robotics.mission.plan",
                "robotics.process.dependencies",
            ],
            "kamiReview": robotics_kami_scene(asset_kind=asset_kind)["roboticsKamiScene"],
            "integrationRecords": [record for form in forms for record in form["outputRecords"]],
            "approvalGates": [
                "sales terms accepted before engineering release",
                "engineering release approved before robot work dispatch",
                "SCADA / robot safety envelope approved before motion",
                "quality release approved before shipment",
                "transport custody proof approved before invoice close",
            ],
        }
    }


def robotics_sales_plan(*, customer_id: str = "customer", item_or_service: str = "robot-enabled manufacturing service", quantity: Any = 1) -> dict[str, Any]:
    qty = quantity if isinstance(quantity, (int, float)) else 1
    return {
        "roboticsSalesPlan": {
            "customerId": customer_id,
            "itemOrService": item_or_service,
            "quantity": qty,
            "records": ["crm.opportunity", "erp.salesOrder", "requirements.rfq", "erp.invoice"],
            "approvalGates": ["commercial terms", "technical feasibility", "quality release", "delivery proof"],
        }
    }


def robotics_mission_plan(*, mission_id: str = "robotics-mission", asset_kind: str = "robot-arm", mission_type: str = "machine-tending", route_id: str = "robotics-route") -> dict[str, Any]:
    protocol = {"drone": "mavlink-json", "agv": "vda5050-json", "autonomous-vehicle": "ros2-action-json"}.get(asset_kind, "robot-waypoint-json")
    return {
        "roboticsMission": {
            "missionId": mission_id,
            "assetKind": asset_kind,
            "missionType": mission_type,
            "routeId": route_id,
            "commandProtocol": protocol,
            "commands": [
                {"id": "precheck", "command": "validate-safety-envelope", "params": {"approvalRequired": True}},
                {"id": "arm", "command": "arm-or-enable", "params": {"operatorGate": "approved"}},
                {"id": "execute", "command": "execute-route-or-waypoints", "params": {"routeId": route_id}},
                {"id": "handoff", "command": "confirm-custody-or-completion", "params": {"records": ["mes.operation", "tms.proofOfDelivery"]}},
            ],
            "telemetryTopics": ["asset.pose", "asset.health", "mission.state", "safety.event"],
            "emergencyProcedures": ["pause mission", "hold or return to safe stop", "notify operator", "write audit snapshot"],
        }
    }


def robotics_telemetry_schema(*, schema_id: str = "robotics-telemetry-v1") -> dict[str, Any]:
    return {
        "roboticsTelemetrySchema": {
            "schemaId": schema_id,
            "topics": [
                {"topic": "robotics.asset.pose", "requiredFields": ["assetId", "x", "y", "z", "yawDeg", "timestamp"], "retention": "hot-24h"},
                {"topic": "robotics.work.state", "requiredFields": ["missionId", "state", "stepId", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.safety.event", "requiredFields": ["assetId", "severity", "event", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.transport.handoff", "requiredFields": ["shipmentId", "from", "to", "custodyScan", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.quality.release", "requiredFields": ["requestId", "decision", "inspectionRef", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.network.link", "requiredFields": ["assetId", "medium", "linkId", "state", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.rf.survey", "requiredFields": ["assetId", "medium", "siteId", "measurement", "timestamp"], "retention": "audit-7y"},
                {"topic": "robotics.telecom.commissioning", "requiredFields": ["missionId", "siteId", "medium", "decision", "timestamp"], "retention": "audit-7y"},
            ],
            "stateEnums": {
                "missionState": ["planned", "simulated", "approved", "running", "paused", "completed", "failed"],
                "safetySeverity": ["info", "warning", "stop", "estop"],
                "approvalDecision": ["approve", "reject", "hold"],
            },
        }
    }


def _selected_telecom_media(media: Any) -> list[dict[str, Any]]:
    if not isinstance(media, list) or not media:
        return TELECOM_ROBOTICS_MEDIA
    selected = {str(item).strip().lower() for item in media if str(item).strip()}
    return [entry for entry in TELECOM_ROBOTICS_MEDIA if entry["medium"] in selected]


def robotics_telecom_coverage(*, media: Any = None) -> dict[str, Any]:
    entries = _selected_telecom_media(media)
    return {
        "roboticsTelecomCoverage": {
            "coverageId": f"robotics-telecom-coverage-{_stamp()}",
            "media": entries,
            "implementedOverlay": [entry["medium"] for entry in entries if entry["implementationCoverage"] == "implemented-overlay"],
            "planningRuntime": [entry["medium"] for entry in entries if entry["implementationCoverage"] == "planning-runtime"],
            "coverageGaps": [
                {"medium": entry["medium"], "gaps": entry["gaps"]}
                for entry in entries
                if entry["gaps"]
            ],
        }
    }


def robotics_network_deployment_plan(
    *,
    request_id: str = "robotics-network-request",
    site_id: str = "telecom-site",
    media: Any = None,
    robot_fleet_id: str = "network-hardware-robotics",
) -> dict[str, Any]:
    selected = _selected_telecom_media(media)
    missions = []
    for index, entry in enumerate(selected, start=1):
        missions.append({
            "id": f"{request_id}-mission-{index}",
            "medium": entry["medium"],
            "robotAssets": entry["robotAssets"],
            "scope": entry["roboticsScope"],
            "telecomSchemas": entry["telecomSchemas"],
            "commands": [
                {"id": "precheck", "command": "validate-safety-envelope", "params": {"approvalRequired": True}},
                {"id": "survey", "command": "capture-network-or-rf-evidence", "params": {"siteId": site_id, "medium": entry["medium"]}},
                {"id": "commission", "command": "record-telecom-commissioning-decision", "params": {"schemas": entry["telecomSchemas"]}},
            ],
            "status": "blocked" if entry["implementationCoverage"] == "none" else "review",
        })
    blockers = [
        f"{entry['medium']}: {gap}"
        for entry in selected
        for gap in entry["gaps"]
        if entry["designCoverage"] in {"gap", "out-of-scope"} or entry["medium"] in {"neutron-communication"}
    ]
    return {
        "roboticsNetworkDeploymentPlan": {
            "requestId": request_id,
            "siteId": site_id,
            "robotFleetId": robot_fleet_id,
            "missions": missions,
            "telemetryTopics": ["robotics.network.link", "robotics.rf.survey", "robotics.telecom.commissioning"],
            "bpmnProcesses": [
                "00-contracts/bpmn/com/etzhayyim/robotics/observeRoboticsMission.bpmn",
                "00-contracts/bpmn/com/etzhayyim/telecom/registerCellSite.bpmn",
                "00-contracts/bpmn/com/etzhayyim/telecom/registerRanNode.bpmn",
                "00-contracts/bpmn/com/etzhayyim/telecom/auditPerformanceCounters.bpmn",
            ],
            "approvalGates": [
                "human approval before robot motion",
                "RF/legal spectrum authorization attached before active emission",
                "site commissioning evidence accepted before service handoff",
            ],
            "blockers": blockers,
            "status": "blocked" if blockers else "review",
        }
    }


def robotics_mission_simulate(*, mission: Any = None, mission_id: str = "robotics-mission", asset_kind: str = "robot-arm") -> dict[str, Any]:
    mission_dict = mission if isinstance(mission, dict) else robotics_mission_plan(mission_id=mission_id, asset_kind=asset_kind)["roboticsMission"]
    commands = mission_dict.get("commands") if isinstance(mission_dict.get("commands"), list) else []
    telemetry = robotics_telemetry_schema()["roboticsTelemetrySchema"]
    scene = robotics_kami_scene(asset_kind=asset_kind)["roboticsKamiScene"]
    checks = [
        {"id": "commands-present", "status": "pass" if len(commands) >= 3 else "fail", "detail": f"{len(commands)} commands planned"},
        {"id": "safety-command", "status": "pass" if any("safety" in str(cmd.get("command", "")) or "precheck" in str(cmd.get("command", "")) for cmd in commands if isinstance(cmd, dict)) else "review", "detail": "mission should start with safety-envelope validation"},
        {"id": "telemetry-contract", "status": "pass" if len(telemetry["topics"]) >= 4 else "review", "detail": f"{len(telemetry['topics'])} telemetry topics required"},
        {"id": "kami-scene", "status": "pass" if any(node.get("kind") == "safety-zone" for node in scene["sceneNodes"]) else "review", "detail": f"{len(scene['sceneNodes'])} KAMI scene nodes checked"},
    ]
    status = "fail" if any(check["status"] == "fail" for check in checks) else "review" if any(check["status"] == "review" for check in checks) else "pass"
    return {
        "roboticsMissionSimulation": {
            "simulationId": f"robotics-sim-{_stamp()}",
            "missionId": str(mission_dict.get("missionId") or mission_id),
            "status": status,
            "checks": checks,
            "estimatedSeconds": len(commands) * 30,
            "requiresHumanApproval": status != "pass",
            "telemetrySchema": telemetry,
        }
    }


def robotics_approval_record(*, request_id: str = "robotics-request", decision: str = "hold", approver_did: str = "did:web:robotics-operator.etzhayyim.com", scope: str = "robot-motion-and-transport") -> dict[str, Any]:
    normalized = decision if decision in {"approve", "reject", "hold"} else "hold"
    return {
        "roboticsApprovalRecord": {
            "approvalId": f"robotics-approval-{_stamp()}",
            "requestId": request_id,
            "decision": normalized,
            "approverDid": approver_did,
            "approvedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope": scope,
            "requiredEvidence": [
                "mission simulation pass or reviewed",
                "safety envelope reviewed",
                "telemetry schema selected",
                "BPMN audit event emitted",
            ],
            "auditAction": f"robotics.approval.{normalized}",
        }
    }


def robotics_telemetry_ingest(*, topic: str = "robotics.work.state", payload: Any = None, frame_id: str | None = None) -> dict[str, Any]:
    schema = robotics_telemetry_schema()["roboticsTelemetrySchema"]
    payload_dict = payload if isinstance(payload, dict) else {}
    contract = next((entry for entry in schema["topics"] if entry["topic"] == topic), None)
    missing = [field for field in contract["requiredFields"] if field not in payload_dict] if contract else ["knownTopic"]
    return {
        "roboticsTelemetryFrame": {
            "frameId": frame_id or f"robotics-frame-{_stamp()}",
            "topic": topic,
            "accepted": not missing,
            "missingFields": missing,
            "payload": payload_dict,
            "receivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }


def robotics_mission_status(*, mission_id: str = "robotics-mission", simulation: Any = None, approval: Any = None, telemetry_frames: Any = None) -> dict[str, Any]:
    sim = simulation if isinstance(simulation, dict) else None
    approval_record = approval if isinstance(approval, dict) else None
    frames = telemetry_frames if isinstance(telemetry_frames, list) else []
    blockers: list[str] = []
    evidence: list[str] = []
    if sim:
        evidence.append(f"simulation:{sim.get('status')}")
        if sim.get("status") == "fail":
            blockers.append("mission simulation failed")
    else:
        blockers.append("mission simulation is missing")
    if approval_record:
        evidence.append(f"approval:{approval_record.get('decision')}")
        if approval_record.get("decision") != "approve":
            blockers.append(f"approval decision is {approval_record.get('decision')}")
    else:
        blockers.append("motion approval is missing")
    if any(isinstance(frame, dict) and frame.get("accepted") is False for frame in frames):
        blockers.append("one or more telemetry frames violate schema")
    if frames:
        evidence.append(f"telemetryFrames:{len(frames)}")
    completed = any(
        isinstance(frame, dict)
        and frame.get("topic") == "robotics.work.state"
        and isinstance(frame.get("payload"), dict)
        and frame["payload"].get("state") == "completed"
        for frame in frames
    )
    state = "blocked" if blockers else "completed" if completed else "approved" if approval_record else "simulated" if sim else "planned"
    return {
        "roboticsMissionStatus": {
            "missionId": mission_id,
            "state": state,
            "blockers": blockers,
            "evidence": evidence,
            "nextActions": ["resolve blockers", "rerun simulation", "record approval"] if blockers else ["close quality, transport, and invoice records"] if completed else ["dispatch mission", "stream telemetry", "monitor safety events"],
        }
    }


def robotics_fulfillment_close(*, request_id: str = "robotics-request", records: Any = None) -> dict[str, Any]:
    record_set = {str(record) for record in records} if isinstance(records, list) else set()
    required = ["qms.qualityRelease", "tms.proofOfDelivery", "erp.salesOrder", "erp.invoice"]
    missing = [record for record in required if record not in record_set]
    return {
        "roboticsFulfillmentClose": {
            "closeId": f"robotics-close-{_stamp()}",
            "requestId": request_id,
            "status": "blocked" if missing else "ready-to-invoice",
            "requiredRecords": required,
            "missingRecords": missing,
            "auditAction": "robotics.fulfillment.blocked" if missing else "robotics.fulfillment.readyToInvoice",
        }
    }


def _manifest_items(manifest: Any) -> list[dict[str, Any]]:
    if isinstance(manifest, dict):
        raw_items = manifest.get("files") or manifest.get("items") or manifest.get("artifacts") or []
    elif isinstance(manifest, list):
        raw_items = manifest
    else:
        raw_items = []
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items):
        item = raw if isinstance(raw, dict) else {"path": str(raw)}
        path = str(item.get("path") or item.get("name") or item.get("uri") or f"artifact-{index + 1}")
        kind = str(item.get("kind") or item.get("type") or "").lower()
        if not kind:
            suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            kind = {
                "step": "cad",
                "stp": "cad",
                "iges": "cad",
                "igs": "cad",
                "stl": "mesh",
                "obj": "mesh",
                "gcode": "cam",
                "nc": "cam",
                "csv": "bom",
                "xlsx": "bom",
                "pdf": "drawing",
                "png": "drawing",
            }.get(suffix, "artifact")
        items.append({**item, "path": path, "kind": kind})
    return items


def robotics_product_package_validate(
    *,
    request_id: str = "robotics-request",
    package_id: str = "robotics-package",
    asset_kind: str = "robotics-product",
    package_manifest: Any = None,
) -> dict[str, Any]:
    items = _manifest_items(package_manifest)
    kinds = {item["kind"] for item in items}
    required = {"cad", "bom"}
    missing = sorted(required - kinds)
    warnings = []
    if "drawing" not in kinds:
        warnings.append("drawing or inspection reference not present")
    if "cam" not in kinds and "mesh" not in kinds:
        warnings.append("manufacturing program or mesh not present")
    return {
        "roboticsProductPackageValidation": {
            "validationId": f"product-package-validation-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "assetKind": asset_kind,
            "status": "blocked" if missing else "pass",
            "requiredKinds": sorted(required),
            "presentKinds": sorted(kinds),
            "missingKinds": missing,
            "warnings": warnings,
            "fileCount": len(items),
        }
    }


def robotics_product_file_catalog(
    *,
    package_id: str = "robotics-package",
    package_manifest: Any = None,
    package_validation: Any = None,
) -> dict[str, Any]:
    items = _manifest_items(package_manifest)
    catalog_items = [
        {
            "fileId": str(item.get("id") or f"{package_id}-file-{index + 1}"),
            "path": item["path"],
            "kind": item["kind"],
            "sha256": item.get("sha256"),
            "revision": str(item.get("revision") or item.get("rev") or "A"),
            "manufacturingUse": {
                "cad": "engineering-release",
                "mesh": "additive-or-fixture-review",
                "cam": "machine-program",
                "bom": "material-and-procurement",
                "drawing": "inspection-and-quality",
            }.get(item["kind"], "supporting-evidence"),
        }
        for index, item in enumerate(items)
    ]
    validation = package_validation if isinstance(package_validation, dict) else {}
    return {
        "roboticsProductFileCatalog": {
            "catalogId": f"product-file-catalog-{_stamp()}",
            "packageId": package_id,
            "validationStatus": validation.get("status"),
            "files": catalog_items,
            "byKind": {
                kind: [item["fileId"] for item in catalog_items if item["kind"] == kind]
                for kind in sorted({item["kind"] for item in catalog_items})
            },
        }
    }


def robotics_product_process_plan(
    *,
    request_id: str = "robotics-request",
    package_id: str = "robotics-package",
    asset_kind: str = "robotics-product",
    file_catalog: Any = None,
) -> dict[str, Any]:
    catalog = file_catalog if isinstance(file_catalog, dict) else {}
    files = catalog.get("files") if isinstance(catalog.get("files"), list) else []
    kinds = {str(item.get("kind")) for item in files if isinstance(item, dict)}
    steps = [
        {"id": "engineering-release", "records": ["cad.partModel", "plm.ebom"], "requiredKinds": ["cad", "bom"]},
        {"id": "dfm-review", "records": ["supplier.dfmFeedback", "qms.riskReview"], "requiredKinds": ["cad", "drawing"]},
        {"id": "procurement", "records": ["erp.purchaseOrder", "qms.materialCertificate"], "requiredKinds": ["bom"]},
        {"id": "manufacturing", "records": ["mes.workOrder", "scada.machineState"], "requiredKinds": ["cam", "mesh"]},
        {"id": "quality-release", "records": ["qms.inspectionResult", "qms.qualityRelease"], "requiredKinds": ["drawing"]},
    ]
    for step in steps:
        required = set(step["requiredKinds"])
        step["status"] = "ready" if required & kinds or required <= kinds else "review"
    return {
        "roboticsManufacturingProcessPlan": {
            "planId": f"manufacturing-process-plan-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "assetKind": asset_kind,
            "steps": steps,
            "approvalGates": ["engineering release", "DFM accepted", "materials available", "quality plan approved"],
            "integrationRecords": [record for step in steps for record in step["records"]],
        }
    }


def robotics_product_rfq_export(
    *,
    request_id: str = "robotics-request",
    package_id: str = "robotics-package",
    quantity: Any = 1,
    target_unit_cost: Any = None,
    incoterms: str = "EXW",
    supplier_region: str = "global",
    file_catalog: Any = None,
    process_plan: Any = None,
) -> dict[str, Any]:
    qty = quantity if isinstance(quantity, int) and quantity > 0 else 1
    catalog = file_catalog if isinstance(file_catalog, dict) else {}
    plan = process_plan if isinstance(process_plan, dict) else {}
    files = catalog.get("files") if isinstance(catalog.get("files"), list) else []
    return {
        "roboticsRfqExport": {
            "rfqId": f"robotics-rfq-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "quantity": qty,
            "targetUnitCost": target_unit_cost,
            "incoterms": incoterms or "EXW",
            "preferredRegion": supplier_region or "global",
            "attachments": [
                {"fileId": item.get("fileId"), "path": item.get("path"), "kind": item.get("kind")}
                for item in files if isinstance(item, dict)
            ],
            "processSteps": [step.get("id") for step in plan.get("steps", []) if isinstance(step, dict)],
            "requiredSupplierEvidence": ["DFM feedback", "sample quote", "lead time", "quality plan", "certifications"],
            "status": "ready-for-review",
        }
    }


def automotive_package_profile(
    *,
    request_id: str = "vehicle-request",
    package_id: str = "vehicle-package",
    vehicle_program: str = "vehicle-program",
    model_code: str = "",
    plant_id: str = "",
    line_id: str = "",
    vehicle_kind: str = "autonomous_vehicle",
    package_manifest: Any = None,
) -> dict[str, Any]:
    items = _manifest_items(package_manifest)
    return {
        "automotiveManufacturingProfile": {
            "profileId": f"automotive-profile-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "vehicleProgram": vehicle_program,
            "modelCode": model_code,
            "plantId": plant_id,
            "lineId": line_id,
            "vehicleKind": vehicle_kind,
            "artifactKinds": sorted({item["kind"] for item in items}),
            "standards": ["IATF16949", "ISO26262-review", "APQP", "PPAP"],
        }
    }


def automotive_file_catalog(**kwargs: Any) -> dict[str, Any]:
    out = robotics_product_file_catalog(
        package_id=str(kwargs.get("package_id") or kwargs.get("packageId") or "vehicle-package"),
        package_manifest=kwargs.get("package_manifest") or kwargs.get("packageManifest"),
        package_validation=kwargs.get("package_validation") or kwargs.get("packageValidation"),
    )
    return out


def automotive_supply_process_link(
    *,
    request_id: str = "vehicle-request",
    package_id: str = "vehicle-package",
    vehicle_program: str = "vehicle-program",
    file_catalog: Any = None,
    vehicle_profile: Any = None,
    links: Any = None,
) -> dict[str, Any]:
    supplied_links = links if isinstance(links, list) else []
    default_links = [
        {"from": "materials", "to": "suppliers", "record": "erp.supplierMaterialApproval"},
        {"from": "suppliers", "to": "intermediate-process", "record": "mes.routingOperation"},
        {"from": "intermediate-process", "to": "people", "record": "training.skillMatrix"},
        {"from": "patents", "to": "engineering", "record": "plm.ipClearance"},
    ]
    return {
        "automotiveSupplyProcessGraph": {
            "graphId": f"automotive-supply-process-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "vehicleProgram": vehicle_program,
            "vehicleProfile": vehicle_profile if isinstance(vehicle_profile, dict) else {},
            "fileCatalogId": file_catalog.get("catalogId") if isinstance(file_catalog, dict) else None,
            "links": supplied_links or default_links,
        }
    }


def automotive_routing_plan(
    *,
    request_id: str = "vehicle-request",
    package_id: str = "vehicle-package",
    vehicle_profile: Any = None,
    file_catalog: Any = None,
) -> dict[str, Any]:
    profile = vehicle_profile if isinstance(vehicle_profile, dict) else {}
    return {
        "automotiveRoutingPlan": {
            "routingId": f"automotive-routing-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "plantId": profile.get("plantId"),
            "lineId": profile.get("lineId"),
            "operations": [
                {"id": "mbom-release", "station": "manufacturing-engineering", "records": ["plm.mbom"]},
                {"id": "body-or-module-build", "station": "line-assembly", "records": ["mes.operation"]},
                {"id": "software-flash", "station": "eol", "records": ["eol.flashRecord"]},
                {"id": "quality-gate", "station": "qms", "records": ["qms.inspectionResult"]},
            ],
            "lineBalance": {"status": "review", "bottleneckOperation": "quality-gate"},
            "fileCatalogId": file_catalog.get("catalogId") if isinstance(file_catalog, dict) else None,
        }
    }


def automotive_quality_gate(
    *,
    request_id: str = "vehicle-request",
    package_id: str = "vehicle-package",
    vehicle_program: str = "vehicle-program",
    quality_gate: Any = None,
    evidence: Any = None,
) -> dict[str, Any]:
    gate = quality_gate if isinstance(quality_gate, dict) else {}
    required = _list_str(gate.get("requiredEvidence")) or ["profile", "catalog", "routing"]
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    missing = [key for key in required if not evidence_dict.get(key)]
    return {
        "automotiveQualityGateResult": {
            "qualityGateId": f"automotive-quality-gate-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "vehicleProgram": vehicle_program,
            "status": "block" if missing else "review",
            "missingEvidence": missing,
            "requiredEvidence": required,
            "nextActions": ["attach missing evidence", "run APQP review"] if missing else ["human quality review", "PPAP readiness check"],
        }
    }


def automotive_eol_plan(
    *,
    request_id: str = "vehicle-request",
    package_id: str = "vehicle-package",
    vehicle_profile: Any = None,
    file_catalog: Any = None,
    routing_plan: Any = None,
) -> dict[str, Any]:
    return {
        "automotiveEolPlan": {
            "eolPlanId": f"automotive-eol-{_stamp()}",
            "requestId": request_id,
            "packageId": package_id,
            "vehicleProfileId": vehicle_profile.get("profileId") if isinstance(vehicle_profile, dict) else None,
            "routingId": routing_plan.get("routingId") if isinstance(routing_plan, dict) else None,
            "steps": ["software flashing", "diagnostics", "ADAS calibration", "digital product passport export"],
            "rfqExports": ["tooling", "test-fixture", "contract-manufacturing"],
            "fileCatalogId": file_catalog.get("catalogId") if isinstance(file_catalog, dict) else None,
        }
    }


def robotics_ems_company_search(*, query: str = "robotics EMS contract manufacturer", regions: Any = None, capabilities: Any = None, certifications: Any = None) -> dict[str, Any]:
    region_list = _list_str(regions) or ["CN", "JP", "TW", "VN"]
    required_capabilities = _list_str(capabilities) or ["PCBA", "box-build", "CNC", "3D-print", "final-assembly"]
    required_certifications = _list_str(certifications) or ["ISO9001"]
    return {
        "roboticsEmsCompanySearch": {
            "searchId": f"ems-search-{_stamp()}",
            "query": query,
            "regions": region_list,
            "requiredCapabilities": required_capabilities,
            "requiredCertifications": required_certifications,
            "candidates": [
                {
                    "companyId": f"ems-{region.lower()}-{index + 1}",
                    "name": f"{region} robotics EMS candidate {index + 1}",
                    "region": region,
                    "capabilities": required_capabilities,
                    "certifications": required_certifications,
                    "evidence": [
                        {"kind": "supplier-profile", "source": "operator-provided-or-public-search", "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                        {"kind": "rfq-keywords", "value": query},
                    ],
                    "riskFlags": ["requires supplier evidence review", "verify export-control and compliance scope"],
                }
                for index, region in enumerate(region_list[:8])
            ],
            "nextActions": ["request NDA/RFQ", "verify certifications", "collect factory audit evidence"],
        }
    }


def robotics_ems_company_profile(*, companies: Any = None, source: str = "operator-provided-or-public-search", as_of_date: str | None = None) -> dict[str, Any]:
    company_list = companies if isinstance(companies, list) else []
    profiles = []
    for index, company in enumerate(company_list):
        item = company if isinstance(company, dict) else {"name": str(company)}
        capabilities = _list_str(item.get("capabilities")) or ["PCBA", "box-build"]
        certifications = _list_str(item.get("certifications")) or ["ISO9001"]
        profiles.append({
            "companyId": str(item.get("companyId") or f"ems-company-{index + 1}"),
            "name": str(item.get("name") or f"EMS company {index + 1}"),
            "region": str(item.get("region") or item.get("country") or "unknown"),
            "capabilities": capabilities,
            "certifications": certifications,
            "moq": item.get("moq") if isinstance(item.get("moq"), int) else None,
            "leadTimeDays": item.get("leadTimeDays") if isinstance(item.get("leadTimeDays"), int) else None,
            "qualitySystems": [cert for cert in certifications if cert.upper().startswith(("ISO", "IATF", "IPC"))],
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [{"kind": "company-profile", "source": source, "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}],
            "riskFlags": _list_str(item.get("riskFlags")) or ["requires capability and certification evidence"],
            "normalizedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return {
        "roboticsEmsCompanyProfiles": {
            "profileBatchId": f"ems-profile-{_stamp()}",
            "source": source,
            "asOfDate": as_of_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "companyProfiles": profiles,
        }
    }


def robotics_ems_supplier_shortlist(*, request_id: str = "robotics-rfq", rfq: Any = None, company_profiles: Any = None, required_capabilities: Any = None) -> dict[str, Any]:
    profiles = company_profiles if isinstance(company_profiles, list) else []
    required = set(_list_str(required_capabilities) or ["PCBA", "box-build"])
    rfq_dict = rfq if isinstance(rfq, dict) else {}
    scored = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        caps = set(_list_str(profile.get("capabilities")))
        certs = set(_list_str(profile.get("certifications")))
        missing = sorted(required - caps)
        score = 100 - (len(missing) * 25)
        if "ISO9001" in certs:
            score += 5
        if str(profile.get("region") or "") == str(rfq_dict.get("preferredRegion") or ""):
            score += 5
        scored.append({
            "companyId": profile.get("companyId"),
            "name": profile.get("name"),
            "region": profile.get("region"),
            "score": max(0, min(100, score)),
            "matchedCapabilities": sorted(caps & required),
            "missingCapabilities": missing,
            "certifications": sorted(certs),
            "decision": "shortlist" if not missing and score >= 80 else "review" if score >= 50 else "reject",
            "nextEvidence": ["factory audit", "sample quote", "DFM feedback", "quality plan"],
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "roboticsEmsSupplierShortlist": {
            "shortlistId": f"ems-shortlist-{_stamp()}",
            "requestId": request_id,
            "requiredCapabilities": sorted(required),
            "supplierCandidates": scored,
            "recommendedSupplierIds": [item["companyId"] for item in scored if item["decision"] == "shortlist"][:5],
        }
    }


def task_process_catalog(**kwargs: Any) -> dict[str, Any]:
    dependency_graph = _dependency_projection(kwargs.get("processes"))
    return {
        "roboticsProcessCatalog": {
            "forms": _selected_forms(kwargs.get("processes")),
            "dependencies": dependency_graph["dependencies"],
            "missingPrerequisites": dependency_graph["missingPrerequisites"],
        }
    }


def task_process_dependencies(**kwargs: Any) -> dict[str, Any]:
    return {"roboticsProcessDependencies": _dependency_projection(kwargs.get("processes"))}


def task_workflow_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_workflow_plan(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        processes=kwargs.get("processes"),
        asset_kind=str(kwargs.get("assetKind") or "agv"),
    )


def task_kami_scene_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_kami_scene(cell_id=str(kwargs.get("cellId") or "robotics-review-cell"), asset_kind=str(kwargs.get("assetKind") or "agv"))


def task_transport_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_transport_plan(
        asset_kind=str(kwargs.get("assetKind") or "agv"),
        origin=str(kwargs.get("origin") or "Factory dock"),
        destination=str(kwargs.get("destination") or "Outbound handoff"),
    )


def task_sales_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_sales_plan(
        customer_id=str(kwargs.get("customerId") or "customer"),
        item_or_service=str(kwargs.get("itemOrService") or "robot-enabled manufacturing service"),
        quantity=kwargs.get("quantity", 1),
    )


def task_mission_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_mission_plan(
        mission_id=str(kwargs.get("missionId") or "robotics-mission"),
        asset_kind=str(kwargs.get("assetKind") or "robot-arm"),
        mission_type=str(kwargs.get("missionType") or "machine-tending"),
        route_id=str(kwargs.get("routeId") or "robotics-route"),
    )


def task_telemetry_schema(**kwargs: Any) -> dict[str, Any]:
    return robotics_telemetry_schema(schema_id=str(kwargs.get("schemaId") or "robotics-telemetry-v1"))


def task_telecom_coverage(**kwargs: Any) -> dict[str, Any]:
    return robotics_telecom_coverage(media=kwargs.get("media"))


def task_network_deployment_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_network_deployment_plan(
        request_id=str(kwargs.get("requestId") or "robotics-network-request"),
        site_id=str(kwargs.get("siteId") or "telecom-site"),
        media=kwargs.get("media"),
        robot_fleet_id=str(kwargs.get("robotFleetId") or "network-hardware-robotics"),
    )


def task_mission_simulate(**kwargs: Any) -> dict[str, Any]:
    return robotics_mission_simulate(
        mission=kwargs.get("roboticsMission") or kwargs.get("mission"),
        mission_id=str(kwargs.get("missionId") or "robotics-mission"),
        asset_kind=str(kwargs.get("assetKind") or "robot-arm"),
    )


def task_approval_record(**kwargs: Any) -> dict[str, Any]:
    return robotics_approval_record(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        decision=str(kwargs.get("decision") or kwargs.get("approvalDecision") or "hold"),
        approver_did=str(kwargs.get("approverDid") or "did:web:robotics-operator.etzhayyim.com"),
        scope=str(kwargs.get("scope") or "robot-motion-and-transport"),
    )


def task_telemetry_ingest(**kwargs: Any) -> dict[str, Any]:
    return robotics_telemetry_ingest(
        topic=str(kwargs.get("topic") or "robotics.work.state"),
        payload=kwargs.get("payload"),
        frame_id=str(kwargs.get("frameId")) if kwargs.get("frameId") else None,
    )


def task_mission_status(**kwargs: Any) -> dict[str, Any]:
    return robotics_mission_status(
        mission_id=str(kwargs.get("missionId") or "robotics-mission"),
        simulation=kwargs.get("roboticsMissionSimulation") or kwargs.get("simulation"),
        approval=kwargs.get("roboticsApprovalRecord") or kwargs.get("approval"),
        telemetry_frames=kwargs.get("telemetryFrames") or kwargs.get("roboticsTelemetryFrames"),
    )


def task_fulfillment_close(**kwargs: Any) -> dict[str, Any]:
    return robotics_fulfillment_close(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        records=kwargs.get("records"),
    )


def task_product_package_validate(**kwargs: Any) -> dict[str, Any]:
    return robotics_product_package_validate(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        package_id=str(kwargs.get("packageId") or "robotics-package"),
        asset_kind=str(kwargs.get("assetKind") or "robotics-product"),
        package_manifest=kwargs.get("packageManifest"),
    )


def task_product_file_catalog(**kwargs: Any) -> dict[str, Any]:
    return robotics_product_file_catalog(
        package_id=str(kwargs.get("packageId") or "robotics-package"),
        package_manifest=kwargs.get("packageManifest"),
        package_validation=kwargs.get("packageValidation"),
    )


def task_product_process_plan(**kwargs: Any) -> dict[str, Any]:
    return robotics_product_process_plan(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        package_id=str(kwargs.get("packageId") or "robotics-package"),
        asset_kind=str(kwargs.get("assetKind") or "robotics-product"),
        file_catalog=kwargs.get("fileCatalog"),
    )


def task_product_rfq_export(**kwargs: Any) -> dict[str, Any]:
    return robotics_product_rfq_export(
        request_id=str(kwargs.get("requestId") or "robotics-request"),
        package_id=str(kwargs.get("packageId") or "robotics-package"),
        quantity=kwargs.get("quantity") or 1,
        target_unit_cost=kwargs.get("targetUnitCost"),
        incoterms=str(kwargs.get("incoterms") or "EXW"),
        supplier_region=str(kwargs.get("supplierRegion") or "global"),
        file_catalog=kwargs.get("fileCatalog"),
        process_plan=kwargs.get("processPlan"),
    )


def task_automotive_package_profile(**kwargs: Any) -> dict[str, Any]:
    return automotive_package_profile(
        request_id=str(kwargs.get("requestId") or "vehicle-request"),
        package_id=str(kwargs.get("packageId") or "vehicle-package"),
        vehicle_program=str(kwargs.get("vehicleProgram") or "vehicle-program"),
        model_code=str(kwargs.get("modelCode") or ""),
        plant_id=str(kwargs.get("plantId") or ""),
        line_id=str(kwargs.get("lineId") or ""),
        vehicle_kind=str(kwargs.get("vehicleKind") or "autonomous_vehicle"),
        package_manifest=kwargs.get("packageManifest"),
    )


def task_automotive_file_catalog(**kwargs: Any) -> dict[str, Any]:
    return automotive_file_catalog(
        packageId=kwargs.get("packageId"),
        packageManifest=kwargs.get("packageManifest"),
        packageValidation=kwargs.get("packageValidation"),
    )


def task_automotive_supply_process_link(**kwargs: Any) -> dict[str, Any]:
    return automotive_supply_process_link(
        request_id=str(kwargs.get("requestId") or "vehicle-request"),
        package_id=str(kwargs.get("packageId") or "vehicle-package"),
        vehicle_program=str(kwargs.get("vehicleProgram") or "vehicle-program"),
        file_catalog=kwargs.get("fileCatalog"),
        vehicle_profile=kwargs.get("vehicleProfile"),
        links=kwargs.get("links"),
    )


def task_automotive_routing_plan(**kwargs: Any) -> dict[str, Any]:
    return automotive_routing_plan(
        request_id=str(kwargs.get("requestId") or "vehicle-request"),
        package_id=str(kwargs.get("packageId") or "vehicle-package"),
        vehicle_profile=kwargs.get("vehicleProfile"),
        file_catalog=kwargs.get("fileCatalog"),
    )


def task_automotive_quality_gate(**kwargs: Any) -> dict[str, Any]:
    return automotive_quality_gate(
        request_id=str(kwargs.get("requestId") or "vehicle-request"),
        package_id=str(kwargs.get("packageId") or "vehicle-package"),
        vehicle_program=str(kwargs.get("vehicleProgram") or "vehicle-program"),
        quality_gate=kwargs.get("qualityGate"),
        evidence=kwargs.get("evidence"),
    )


def task_automotive_eol_plan(**kwargs: Any) -> dict[str, Any]:
    return automotive_eol_plan(
        request_id=str(kwargs.get("requestId") or "vehicle-request"),
        package_id=str(kwargs.get("packageId") or "vehicle-package"),
        vehicle_profile=kwargs.get("vehicleProfile"),
        file_catalog=kwargs.get("fileCatalog"),
        routing_plan=kwargs.get("routingPlan"),
    )


def task_ems_company_search(**kwargs: Any) -> dict[str, Any]:
    return robotics_ems_company_search(
        query=str(kwargs.get("query") or "robotics EMS contract manufacturer"),
        regions=kwargs.get("regions"),
        capabilities=kwargs.get("capabilities"),
        certifications=kwargs.get("certifications"),
    )


def task_ems_company_profile(**kwargs: Any) -> dict[str, Any]:
    return robotics_ems_company_profile(
        companies=kwargs.get("companies") or kwargs.get("candidates"),
        source=str(kwargs.get("source") or "operator-provided-or-public-search"),
        as_of_date=str(kwargs.get("asOfDate")) if kwargs.get("asOfDate") else None,
    )


def task_ems_supplier_shortlist(**kwargs: Any) -> dict[str, Any]:
    return robotics_ems_supplier_shortlist(
        request_id=str(kwargs.get("requestId") or "robotics-rfq"),
        rfq=kwargs.get("rfq"),
        company_profiles=kwargs.get("companyProfiles"),
        required_capabilities=kwargs.get("requiredCapabilities") or kwargs.get("capabilities"),
    )


def register(worker: Any, timeout_ms: int = 180_000) -> None:
    worker.task(task_type="robotics.process.catalog", single_value=False, timeout_ms=timeout_ms)(task_process_catalog)
    worker.task(task_type="robotics.process.dependencies", single_value=False, timeout_ms=timeout_ms)(task_process_dependencies)
    worker.task(task_type="robotics.workflow.plan", single_value=False, timeout_ms=timeout_ms)(task_workflow_plan)
    worker.task(task_type="robotics.kami.scene.plan", single_value=False, timeout_ms=timeout_ms)(task_kami_scene_plan)
    worker.task(task_type="robotics.transport.plan", single_value=False, timeout_ms=timeout_ms)(task_transport_plan)
    worker.task(task_type="robotics.sales.plan", single_value=False, timeout_ms=timeout_ms)(task_sales_plan)
    worker.task(task_type="robotics.mission.plan", single_value=False, timeout_ms=timeout_ms)(task_mission_plan)
    worker.task(task_type="robotics.telemetry.schema", single_value=False, timeout_ms=timeout_ms)(task_telemetry_schema)
    worker.task(task_type="robotics.telecom.coverage", single_value=False, timeout_ms=timeout_ms)(task_telecom_coverage)
    worker.task(task_type="robotics.network.deployment.plan", single_value=False, timeout_ms=timeout_ms)(task_network_deployment_plan)
    worker.task(task_type="robotics.mission.simulate", single_value=False, timeout_ms=timeout_ms)(task_mission_simulate)
    worker.task(task_type="robotics.approval.record", single_value=False, timeout_ms=timeout_ms)(task_approval_record)
    worker.task(task_type="robotics.telemetry.ingest", single_value=False, timeout_ms=timeout_ms)(task_telemetry_ingest)
    worker.task(task_type="robotics.mission.status", single_value=False, timeout_ms=timeout_ms)(task_mission_status)
    worker.task(task_type="robotics.fulfillment.close", single_value=False, timeout_ms=timeout_ms)(task_fulfillment_close)
    worker.task(task_type="robotics.product.package.validate", single_value=False, timeout_ms=timeout_ms)(task_product_package_validate)
    worker.task(task_type="robotics.product.file.catalog", single_value=False, timeout_ms=timeout_ms)(task_product_file_catalog)
    worker.task(task_type="robotics.product.process.plan", single_value=False, timeout_ms=timeout_ms)(task_product_process_plan)
    worker.task(task_type="robotics.product.rfq.export", single_value=False, timeout_ms=timeout_ms)(task_product_rfq_export)
    worker.task(task_type="automotive.package.profile", single_value=False, timeout_ms=timeout_ms)(task_automotive_package_profile)
    worker.task(task_type="automotive.file.catalog", single_value=False, timeout_ms=timeout_ms)(task_automotive_file_catalog)
    worker.task(task_type="automotive.supply.process.link", single_value=False, timeout_ms=timeout_ms)(task_automotive_supply_process_link)
    worker.task(task_type="automotive.routing.plan", single_value=False, timeout_ms=timeout_ms)(task_automotive_routing_plan)
    worker.task(task_type="automotive.quality.gate", single_value=False, timeout_ms=timeout_ms)(task_automotive_quality_gate)
    worker.task(task_type="automotive.eol.plan", single_value=False, timeout_ms=timeout_ms)(task_automotive_eol_plan)
    worker.task(task_type="robotics.ems.company.search", single_value=False, timeout_ms=timeout_ms)(task_ems_company_search)
    worker.task(task_type="robotics.ems.company.profile", single_value=False, timeout_ms=timeout_ms)(task_ems_company_profile)
    worker.task(task_type="robotics.ems.supplier.shortlist", single_value=False, timeout_ms=timeout_ms)(task_ems_supplier_shortlist)
