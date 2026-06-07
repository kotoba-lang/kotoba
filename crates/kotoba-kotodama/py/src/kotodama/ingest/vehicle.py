"""Vehicle Manufacturing Graph handlers for BPMN + Zeebe."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

OWNER_DID = "did:web:vehicle.etzhayyim.com"
NANOID = "v3h1cl01"

PACKAGE_BPMN = "00-contracts/bpmn/com/etzhayyim/robotics/manufactureVehicleProductPackage.bpmn"
GRAPH_MIGRATION = "30-graph/graph-schema/migrations/20260426123000_automotive_manufacturing_supply_process_edges.ts"
GRAPH_SEED = "80-data/schemas/automotive-manufacturing-graph-seed.json"

VERTEX_TYPES = [
    "vertex_automotive_material_requirement",
    "vertex_automotive_intermediate_part",
    "vertex_automotive_responsibility_assignment",
    "vertex_legal_entity",
    "vertex_business_person",
    "vertex_natural_person",
    "vertex_patent",
]

EDGE_TYPES = [
    "edge_automotive_package_requires_material",
    "edge_automotive_material_supplied_by",
    "edge_automotive_process_uses_material",
    "edge_automotive_process_produces_intermediate",
    "edge_automotive_intermediate_feeds_process",
    "edge_automotive_responsible_party",
    "edge_automotive_process_performed_by",
    "edge_automotive_package_references_patent",
]

FILE_FORMATS = {
    "cadPlm": ["STEP AP242", "JT", "native CAD export", "PLM JSON", "PLM CSV"],
    "drawingsGdt": ["PDF", "DXF", "DWG", "QIF", "STEP PMI"],
    "camTooling": ["G-code", "robot program archive", "fixture setup sheet", "die/mold CAD"],
    "bomRouting": ["EBOM CSV", "MBOM CSV", "routing JSON", "MES export", "B2MML"],
    "pcbHarness": ["IPC-2581", "Gerber X2/X3", "ODB++", "IPC-D-356", "KBL", "harness XML"],
    "softwareCalibration": ["AUTOSAR ARXML", "A2L", "DBC", "ODX", "CDD", "SREC", "HEX", "CycloneDX", "SPDX"],
    "processQuality": ["BPMN", "APQP", "PPAP", "DFMEA", "PFMEA", "control plan", "MSA", "SPC", "8D"],
    "eolCompliance": ["measurement CSV", "QIF", "EOL JSON", "homologation PDF", "DPP JSON-LD"],
}

NEXT_EDGES = [
    "edge_automotive_package_requires_material",
    "edge_automotive_material_supplied_by",
    "edge_automotive_process_uses_material",
    "edge_automotive_process_produces_intermediate",
    "edge_automotive_responsible_party",
    "edge_automotive_package_references_patent",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def health(**_: Any) -> dict[str, Any]:
    return {"status": "healthy", "nanoid": NANOID, "did": OWNER_DID, "now": now_iso()}


def describe(**_: Any) -> dict[str, Any]:
    return {
        "app": "Vehicle Manufacturing Graph",
        "nanoid": NANOID,
        "did": OWNER_DID,
        "bpmn": PACKAGE_BPMN,
        "graphMigration": GRAPH_MIGRATION,
        "graphSeed": GRAPH_SEED,
        "vertexTypes": VERTEX_TYPES,
        "edgeTypes": EDGE_TYPES,
        "updatedAt": now_iso(),
    }


def file_formats(**_: Any) -> dict[str, list[str]]:
    return FILE_FORMATS


def plan_supply_process(**kwargs: Any) -> dict[str, Any]:
    process_id = _s(kwargs.get("processId") or kwargs.get("id") or uuid4())
    return {
        "accepted": True,
        "processId": process_id,
        "materialVertex": "vertex_automotive_material_requirement",
        "intermediateVertex": "vertex_automotive_intermediate_part",
        "responsibilityVertex": "vertex_automotive_responsibility_assignment",
        "nextEdges": NEXT_EDGES,
        "note": "Persist the concrete vertices and edges through the automotive manufacturing graph migration and seed loader.",
    }
