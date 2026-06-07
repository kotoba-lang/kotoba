"""KAMI Engineering Workbench handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:eng-kami.etzhayyim.com"
COLLECTION_TABLES = {
    "com.etzhayyim.apps.kami.eda.schematic": "vertex_kami_eng_eda_schematic",
    "com.etzhayyim.apps.kami.cad.model": "vertex_kami_eng_cad_model",
    "com.etzhayyim.apps.kami.cad.featureTree": "vertex_kami_eng_cad_feature",
    "com.etzhayyim.apps.kami.cam.job": "vertex_kami_eng_cam_job",
    "com.etzhayyim.apps.kami.rtl.moduleRef": "vertex_kami_eng_rtl_module_ref",
    "com.etzhayyim.apps.kami.rtl.simulation": "vertex_kami_eng_rtl_simulation",
    "com.etzhayyim.apps.kami.cae.analysis": "vertex_kami_eng_cae_analysis",
}


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _vertex_id(collection: str, record_id: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{record_id}"


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid5(NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _label(kind: str, payload: dict[str, Any]) -> str:
    return _s(payload.get("name") or payload.get("featureType") or payload.get("analysisType") or payload.get("moduleId") or kind)


def _typed_values(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "eda_schematic":
        return {"name": _s(payload.get("name")), "sheet_size": _s(payload.get("sheetSize")), "grid_spacing": _s(payload.get("gridSpacing"))}
    if kind == "cad_model":
        return {"name": _s(payload.get("name")), "model_type": _s(payload.get("type")), "unit": _s(payload.get("unit"))}
    if kind == "cad_feature":
        return {"model_id": _s(payload.get("modelId")), "feature_type": _s(payload.get("featureType")), "feature_order": _num(payload.get("order"))}
    if kind == "cam_job":
        return {"model_id": _s(payload.get("modelId")), "machine": _s(payload.get("machine"))}
    if kind == "rtl_module_ref":
        return {"module_id": _s(payload.get("moduleId"))}
    if kind == "rtl_simulation":
        return {"module_id": _s(payload.get("moduleId")), "duration": _s(payload.get("duration"))}
    if kind == "cae_analysis":
        return {"model_id": _s(payload.get("modelId")), "analysis_type": _s(payload.get("analysisType"))}
    return {}


def _write_edge(table: str, src: str, dst: str, relation: str, payload: dict[str, Any], created_at: str) -> None:
    client = get_kotoba_client()
    edge_row = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": created_at,
        "owner_did": OWNER_DID,
        "sensitivity_ord": 2,
    }
    client.insert_row(table, edge_row)


def _write_related_edges(collection: str, kind: str, record_id: str, payload: dict[str, Any], created_at: str) -> None:
    src = _vertex_id(collection, record_id)
    model_id = _s(payload.get("modelId"))
    if kind == "cad_feature" and model_id:
        _write_edge("edge_kami_eng_cad_model_feature", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "has_feature", payload, created_at)
    elif kind == "cam_job" and model_id:
        _write_edge("edge_kami_eng_cad_model_cam_job", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "manufactured_by_job", payload, created_at)
    elif kind == "rtl_simulation":
        module_id = _s(payload.get("moduleId"))
        if module_id:
            _record("com.etzhayyim.apps.kami.rtl.moduleRef", "rtl_module_ref", {"moduleId": module_id, "createdAt": created_at}, module_id)
            _write_edge("edge_kami_eng_rtl_module_simulation", _vertex_id("com.etzhayyim.apps.kami.rtl.moduleRef", module_id), src, "simulated_by", payload, created_at)
    elif kind == "cae_analysis" and model_id:
        _write_edge("edge_kami_eng_cad_model_cae_analysis", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "analyzed_by", payload, created_at)


from datetime import datetime, timezone
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:eng-kami.etzhayyim.com"
COLLECTION_TABLES = {
    "com.etzhayyim.apps.kami.eda.schematic": "vertex_kami_eng_eda_schematic",
    "com.etzhayyim.apps.kami.cad.model": "vertex_kami_eng_cad_model",
    "com.etzhayyim.apps.kami.cad.featureTree": "vertex_kami_eng_cad_feature",
    "com.etzhayyim.apps.kami.cam.job": "vertex_kami_eng_cam_job",
    "com.etzhayyim.apps.kami.rtl.moduleRef": "vertex_kami_eng_rtl_module_ref",
    "com.etzhayyim.apps.kami.rtl.simulation": "vertex_kami_eng_rtl_simulation",
    "com.etzhayyim.apps.kami.cae.analysis": "vertex_kami_eng_cae_analysis",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _vertex_id(collection: str, record_id: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{record_id}"


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid5(NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _label(kind: str, payload: dict[str, Any]) -> str:
    return _s(payload.get("name") or payload.get("featureType") or payload.get("analysisType") or payload.get("moduleId") or kind)


def _typed_values(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "eda_schematic":
        return {"name": _s(payload.get("name")), "sheet_size": _s(payload.get("sheetSize")), "grid_spacing": _s(payload.get("gridSpacing"))}
    if kind == "cad_model":
        return {"name": _s(payload.get("name")), "model_type": _s(payload.get("type")), "unit": _s(payload.get("unit"))}
    if kind == "cad_feature":
        return {"model_id": _s(payload.get("modelId")), "feature_type": _s(payload.get("featureType")), "feature_order": _num(payload.get("order"))}
    if kind == "cam_job":
        return {"model_id": _s(payload.get("modelId")), "machine": _s(payload.get("machine"))}
    if kind == "rtl_module_ref":
        return {"module_id": _s(payload.get("moduleId"))}
    if kind == "rtl_simulation":
        return {"module_id": _s(payload.get("moduleId")), "duration": _s(payload.get("duration"))}
    if kind == "cae_analysis":
        return {"model_id": _s(payload.get("modelId")), "analysis_type": _s(payload.get("analysisType"))}
    return {}


def _write_edge(table: str, src: str, dst: str, relation: str, payload: dict[str, Any], created_at: str) -> None:
    client = get_kotoba_client()
    edge_row = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": created_at,
        "owner_did": OWNER_DID,
        "sensitivity_ord": 2,
    }
    client.insert_row(table, edge_row)


def _write_related_edges(collection: str, kind: str, record_id: str, payload: dict[str, Any], created_at: str) -> None:
    src = _vertex_id(collection, record_id)
    model_id = _s(payload.get("modelId"))
    if kind == "cad_feature" and model_id:
        _write_edge("edge_kami_eng_cad_model_feature", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "has_feature", payload, created_at)
    elif kind == "cam_job" and model_id:
        _write_edge("edge_kami_eng_cad_model_cam_job", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "manufactured_by_job", payload, created_at)
    elif kind == "rtl_simulation":
        module_id = _s(payload.get("moduleId"))
        if module_id:
            _record("com.etzhayyim.apps.kami.rtl.moduleRef", "rtl_module_ref", {"moduleId": module_id, "createdAt": created_at}, module_id)
            _write_edge("edge_kami_eng_rtl_module_simulation", _vertex_id("com.etzhayyim.apps.kami.rtl.moduleRef", module_id), src, "simulated_by", payload, created_at)
    elif kind == "cae_analysis" and model_id:
        _write_edge("edge_kami_eng_cad_model_cae_analysis", _vertex_id("com.etzhayyim.apps.kami.cad.model", model_id), src, "analyzed_by", payload, created_at)


def _record(collection: str, kind: str, payload: dict[str, Any], record_id: str | None = None) -> str:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        raise ValueError(f"unsupported kami engineering collection: {collection}")
    record_id = record_id or _id(kind)
    rec = {**payload, "createdAt": payload.get("createdAt") or now_iso()}
    typed = _typed_values(kind, rec)
    values = {
        "vertex_id": _vertex_id(collection, record_id),
        "record_id": record_id,
        "owner_did": OWNER_DID,
        "label": _label(kind, rec),
        "status": _s(rec.get("status")),
        "value_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
        "created_at": rec["createdAt"],
        "updated_at": _s(rec.get("updatedAt"), rec["createdAt"]),
        "sensitivity_ord": 2,
        **typed,
    }
    client = get_kotoba_client()
    client.insert_row(table, values)
    _write_related_edges(collection, kind, record_id, rec, rec["createdAt"])
    return record_id


def eda_create_schematic(name: Any = None, sheetSize: Any = None, gridSpacing: Any = None, **_: Any) -> dict[str, Any]:
    schematic_id = _record(
        "com.etzhayyim.apps.kami.eda.schematic",
        "eda_schematic",
        {"name": name, "sheetSize": sheetSize, "gridSpacing": gridSpacing, "symbols": [], "wires": []},
    )
    return {"ok": True, "name": name, "schematicId": schematic_id}


def eda_run_erc(**_: Any) -> dict[str, Any]:
    return {"violations": [], "errorCount": 0, "warningCount": 0}


def eda_export_gerber(**_: Any) -> dict[str, Any]:
    return {"ok": True, "format": "RS-274X", "layers": []}


def cad_create_model(name: Any = None, type: Any = None, unit: Any = None, **_: Any) -> dict[str, Any]:
    model_id = _record(
        "com.etzhayyim.apps.kami.cad.model",
        "cad_model",
        {"name": name, "type": type, "unit": unit, "featureTree": []},
    )
    return {"ok": True, "name": name, "modelId": model_id}


def cad_add_feature(modelId: Any = None, featureType: Any = None, params: Any = None, order: Any = None, **_: Any) -> dict[str, Any]:
    _record(
        "com.etzhayyim.apps.kami.cad.featureTree",
        "cad_feature",
        {"modelId": modelId, "featureType": featureType, "params": params or {}, "order": order},
    )
    return {"ok": True, "featureType": featureType}


def cad_export_step(**_: Any) -> dict[str, Any]:
    return {"ok": True, "format": "STEP AP214"}


def cam_create_job(modelId: Any = None, material: Any = None, operations: Any = None, machine: Any = None, **_: Any) -> dict[str, Any]:
    _record(
        "com.etzhayyim.apps.kami.cam.job",
        "cam_job",
        {"modelId": modelId, "material": material or {}, "operations": operations, "machine": machine, "status": "pending"},
    )
    return {"ok": True}


def cam_generate_gcode(**_: Any) -> dict[str, Any]:
    return {"ok": True, "format": "Fanuc", "lineCount": 0}


def rtl_parse_hdl(language: Any = None, **_: Any) -> dict[str, Any]:
    return {"ok": True, "language": language, "moduleCount": 0}


def rtl_simulate(moduleId: Any = None, duration: Any = None, **_: Any) -> dict[str, Any]:
    _record(
        "com.etzhayyim.apps.kami.rtl.simulation",
        "rtl_simulation",
        {"moduleId": moduleId, "duration": duration, "status": "running"},
    )
    return {"ok": True}


def rtl_synthesize(target: Any = None, **_: Any) -> dict[str, Any]:
    return {"ok": True, "target": target}


def cae_generate_mesh(elementSize: Any = None, **_: Any) -> dict[str, Any]:
    return {"ok": True, "elementSize": elementSize}


def cae_run_analysis(modelId: Any = None, analysisType: Any = None, **_: Any) -> dict[str, Any]:
    _record(
        "com.etzhayyim.apps.kami.cae.analysis",
        "cae_analysis",
        {"modelId": modelId, "analysisType": analysisType, "status": "running"},
    )
    return {"ok": True, "analysisType": analysisType}


def cae_get_results(analysisId: Any = None, **_: Any) -> dict[str, Any]:
    return {"ok": True, "analysisId": analysisId}
