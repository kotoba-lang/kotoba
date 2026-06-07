"""
yardOps.* — LangServer handlers for yard / dock-door coordination.

Task types:
  yardOps.slot.allocate
  yardOps.trailer.persist
  yardOps.dockDoor.select
  yardOps.dockJob.persist
  loadingRobot.mission.dispatch     (downstream trigger)
  yardOps.dockJob.complete
  yardOps.dockSchedule.read

Cost-compression role: dockDoor.select is the dwell-time minimizer.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("yard_ops.primitive")

_YARD_DID = "did:web:yard-ops.etzhayyim.com"
_ROBOT_DID = "did:web:robot.etzhayyim.com:loading-robot"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")


def _vid(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{_YARD_DID}/com.etzhayyim.apps.yardOps.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


# ── Trailer check-in ────────────────────────────────────────────────────────

async def task_yard_ops_slot_allocate(
    trailerPlate: str = "",
    carrierDid: str = "",
    appointmentId: str = "",
) -> dict:
    suffix = uuid.uuid4().hex[:3].upper()
    return {"ok": True, "yardSlotCode": f"YS-{suffix}"}


async def task_yard_ops_trailer_persist(
    trailerPlate: str = "",
    carrierDid: str = "",
    yardSlotCode: str = "",
) -> dict:
    if not trailerPlate:
        return {"ok": False, "error": "trailerPlate required"}
    vid = _vid("trailer")
    payload_dict = {
        "trailerPlate": trailerPlate, "carrierDid": carrierDid,
        "yardSlotCode": yardSlotCode, "checkedInAt": _now_iso(),
    }
    row_data = {
        "vertex_id": vid,
        "vertex_key": trailerPlate,
        "label": "yardOps.trailer",
        "status": "in_yard",
        "value_json": json.dumps(payload_dict),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "owner_did": _YARD_DID,
        "actor_did": _YARD_DID,
        "sensitivity_ord": 2,
    }
    try:
        get_kotoba_client().insert_row("vertex_yard_ops_trailer", row_data)
        ok = True
    except Exception as exc:
        LOG.warning("yard_ops trailer persist failed: %s", exc)
        ok = False
    return {"ok": ok, "vertexId": vid, "trailerVertexId": vid,
            "yardSlotCode": yardSlotCode}


# ── Dock door + dock job ────────────────────────────────────────────────────

async def task_yard_ops_dock_door_select(
    trailerVertexId: str = "",
    direction: str = "inbound",
) -> dict:
    """Pick a dock door. Delegates to the LangGraph optimizer (reads
    mv_dock_dwell_minutes_15m); falls back to rotating-suffix if unavailable."""
    try:
        from kotodama.langgraph_graphs.warehouse_yard_optimizer import (
            recommend_dock_door,
        )
        rec = recommend_dock_door(trailerVertexId or "", direction or "inbound")
        if rec.get("ok") and rec.get("dock_door_code"):
            return {"ok": True, "dockDoorCode": rec["dock_door_code"]}
    except Exception as exc:
        LOG.info("optimizer fallback (dock_door): %s", exc)
    suffix = uuid.uuid4().hex[:2].upper()
    return {"ok": True, "dockDoorCode": f"DOOR-{direction[:2].upper()}-{suffix}"}


async def task_yard_ops_dock_job_persist(
    trailerVertexId: str = "",
    dockDoorCode: str = "",
    direction: str = "inbound",
    loadPlanRef: str = "",
) -> dict:
    if not trailerVertexId or not dockDoorCode:
        return {"ok": False, "error": "trailerVertexId + dockDoorCode required"}
    vid = _vid("dockJob")
    payload_dict = {
        "trailerVertexId": trailerVertexId,
        "dockDoorCode": dockDoorCode,
        "direction": direction,
        "loadPlanRef": loadPlanRef,
        "openedAt": _now_iso(),
    }
    vertex_row_data = {
        "vertex_id": vid,
        "vertex_key": f"{dockDoorCode}:{trailerVertexId}",
        "label": "yardOps.dockJob",
        "status": "open",
        "value_json": json.dumps(payload_dict),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "owner_did": _YARD_DID,
        "actor_did": _YARD_DID,
        "sensitivity_ord": 2,
    }
    try:
        get_kotoba_client().insert_row("vertex_yard_ops_dock_job", vertex_row_data)
        ok = True
    except Exception as exc:
        LOG.warning("yard_ops dock job persist failed (vertex): %s", exc)
        ok = False
    # edge: trailer → dock_job
    if ok:
        edge_vid = _vid("edge.trailerDockJob")
        edge_row_data = {
            "edge_id": edge_vid,
            "edge_key": f"{trailerVertexId}->{vid}",
            "src_vid": trailerVertexId,
            "dst_vid": vid,
            "relation": "assigned_to",
            "value_json": json.dumps({"direction": direction}),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "owner_did": _YARD_DID,
            "sensitivity_ord": 2,
        }
        try:
            get_kotoba_client().insert_row("edge_yard_ops_trailer_dock_job", edge_row_data)
        except Exception as exc:
            LOG.warning("yard_ops dock job persist failed (edge): %s", exc)
    return {"ok": ok, "vertexId": vid, "dockJobVertexId": vid,
            "dockDoorCode": dockDoorCode}


# ── Loading-robot mission dispatch ──────────────────────────────────────────

async def task_loading_robot_mission_dispatch(
    dockJobVertexId: str = "",
    loadingRobotLoadPlan: str = "",
    loadingRobotCellDesign: str = "",
) -> dict:
    """Persist an edge dock_job → loading_mission and return a mission id.
    The actual robot execution is owned by the existing loading-robot
    BPMN (executeLoadingMission); this dispatch just marks the link."""
    if not dockJobVertexId:
        return {"ok": False, "error": "dockJobVertexId required"}
    mission_id = f"mission-{_dt.datetime.now(tz=_dt.UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    edge_vid = _vid("edge.dockJobMission")
    edge_row_data = {
        "edge_id": edge_vid,
        "edge_key": f"{dockJobVertexId}->{mission_id}",
        "src_vid": dockJobVertexId,
        "dst_vid": f"at://{_ROBOT_DID}/loadingRobot.mission/{mission_id}",
        "relation": "dispatches",
        "value_json": json.dumps({
            "loadPlan": loadingRobotLoadPlan,
            "cellDesign": loadingRobotCellDesign,
        }),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "owner_did": _YARD_DID,
        "sensitivity_ord": 2,
    }
    try:
        get_kotoba_client().insert_row("edge_yard_ops_dock_job_loading_mission", edge_row_data)
        ok = True
    except Exception as exc:
        LOG.warning("yard_ops mission dispatch failed: %s", exc)
        ok = False
    return {"ok": ok, "loadingRobotMissionId": mission_id}


# ── Dock job completion ─────────────────────────────────────────────────────

async def task_yard_ops_dock_job_complete(
    dockJobVertexId: str = "",
    actualDurationMin: int = 0,
    exceptions: list | None = None,
) -> dict:
    if not dockJobVertexId:
        return {"ok": False, "error": "dockJobVertexId required"}
    vid = _vid("dockCompletion")
    payload_dict = {
        "dockJobVertexId": dockJobVertexId,
        "actualDurationMin": int(actualDurationMin or 0),
        "exceptions": exceptions or [],
        "closedAt": _now_iso(),
    }
    vertex_completion_row_data = {
        "vertex_id": vid,
        "vertex_key": dockJobVertexId,
        "label": "yardOps.dockCompletion",
        "status": "closed",
        "value_json": json.dumps(payload_dict),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "owner_did": _YARD_DID,
        "actor_did": _YARD_DID,
        "sensitivity_ord": 2,
    }
    try:
        get_kotoba_client().insert_row("vertex_yard_ops_dock_completion", vertex_completion_row_data)
        ok = True
    except Exception as exc:
        LOG.warning("yard_ops dock completion failed (vertex): %s", exc)
        ok = False
    if ok:
        edge_vid = _vid("edge.dockJobCompletion")
        edge_completion_row_data = {
            "edge_id": edge_vid,
            "edge_key": f"{dockJobVertexId}->{vid}",
            "src_vid": dockJobVertexId,
            "dst_vid": vid,
            "relation": "closed_by",
            "value_json": json.dumps({"durationMin": int(actualDurationMin or 0)}),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "owner_did": _YARD_DID,
            "sensitivity_ord": 2,
        }
        try:
            get_kotoba_client().insert_row("edge_yard_ops_dock_job_completion", edge_completion_row_data)
        except Exception as exc:
            LOG.warning("yard_ops dock completion failed (edge): %s", exc)
        # mark dock job as closed
        dock_job_update_data = {
            "vertex_id": dockJobVertexId,
            "status": "closed",
            "updated_at": _now_iso(),
        }
        try:
            get_kotoba_client().insert_row("vertex_yard_ops_dock_job", dock_job_update_data) # insert_row acts as upsert
        except Exception as exc:
            LOG.warning("yard_ops dock job status update failed: %s", exc)
    return {"ok": ok, "vertexId": vid, "completionVertexId": vid}


# ── Dock schedule query ─────────────────────────────────────────────────────

async def task_yard_ops_dock_schedule_read(
    fromTs: str = "",
    toTs: str = "",
) -> dict:
    query_edn = """
    [:find (pull ?e [:vertex/id :vertex/value_json :vertex/status :vertex/created_at])
     :where
     [?e :vertex/label "yardOps.dockJob"]
     [?e :vertex/created_at ?created_at]
     [(>= ?created_at $from_ts)]
     [(<= ?created_at $to_ts)]
     :limit 200
     :order [?created_at :asc]]
    """
    try:
        rows_raw = get_kotoba_client().q(
            query_edn,
            {"$from_ts": fromTs or "1970-01-01 00:00:00",
             "$to_ts": toTs or "2999-12-31 23:59:59"},
        )
        # q returns a list of lists, where each inner list contains the pulled map
        rows = [item[0] for item in rows_raw]
    except Exception as exc:
        LOG.warning("yard_ops dock schedule read failed: %s", exc)
        rows = []
    schedule: list[dict] = []
    for row_dict in rows: # row is now a dictionary
        try:
            # Assuming value_json is already a string
            v = json.loads(row_dict.get(":vertex/value_json", "{}"))
        except Exception:
            v = {}
        schedule.append({
            "dockJobVertexId": row_dict.get(":vertex/id", ""),
            "dockDoorCode": v.get("dockDoorCode", ""),
            "trailerPlate": v.get("trailerPlate", ""),
            "direction": v.get("direction", ""),
            "etaTs": row_dict.get(":vertex/created_at", ""),
            "status": row_dict.get(":vertex/status", ""),
        })
    return {"ok": True, "schedule": schedule}


# ── Registration ────────────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="yardOps.slot.allocate", timeout_ms=timeout_ms)
    async def _slot(trailerPlate: str = "", carrierDid: str = "",
                    appointmentId: str = "") -> dict:
        return await task_yard_ops_slot_allocate(
            trailerPlate=trailerPlate, carrierDid=carrierDid,
            appointmentId=appointmentId)

    @app.task(task_type="yardOps.trailer.persist", timeout_ms=timeout_ms)
    async def _trailer(trailerPlate: str = "", carrierDid: str = "",
                       yardSlotCode: str = "") -> dict:
        return await task_yard_ops_trailer_persist(
            trailerPlate=trailerPlate, carrierDid=carrierDid,
            yardSlotCode=yardSlotCode)

    @app.task(task_type="yardOps.dockDoor.select", timeout_ms=timeout_ms)
    async def _door(trailerVertexId: str = "", direction: str = "inbound") -> dict:
        return await task_yard_ops_dock_door_select(
            trailerVertexId=trailerVertexId, direction=direction)

    @app.task(task_type="yardOps.dockJob.persist", timeout_ms=timeout_ms)
    async def _job(trailerVertexId: str = "", dockDoorCode: str = "",
                   direction: str = "inbound", loadPlanRef: str = "") -> dict:
        return await task_yard_ops_dock_job_persist(
            trailerVertexId=trailerVertexId, dockDoorCode=dockDoorCode,
            direction=direction, loadPlanRef=loadPlanRef)

    @app.task(task_type="loadingRobot.mission.dispatch", timeout_ms=timeout_ms)
    async def _mission(dockJobVertexId: str = "",
                       loadingRobotLoadPlan: str = "",
                       loadingRobotCellDesign: str = "") -> dict:
        return await task_loading_robot_mission_dispatch(
            dockJobVertexId=dockJobVertexId,
            loadingRobotLoadPlan=loadingRobotLoadPlan,
            loadingRobotCellDesign=loadingRobotCellDesign)

    @app.task(task_type="yardOps.dockJob.complete", timeout_ms=timeout_ms)
    async def _complete(dockJobVertexId: str = "",
                        actualDurationMin: int = 0,
                        exceptions=None) -> dict:
        return await task_yard_ops_dock_job_complete(
            dockJobVertexId=dockJobVertexId,
            actualDurationMin=actualDurationMin,
            exceptions=exceptions)

    @app.task(task_type="yardOps.dockSchedule.read", timeout_ms=timeout_ms)
    async def _schedule(fromTs: str = "", toTs: str = "") -> dict:
        return await task_yard_ops_dock_schedule_read(fromTs=fromTs, toTs=toTs)

    LOG.info("Registered yardOps.* tasks (slot.allocate, trailer.persist, "
             "dockDoor.select, dockJob.{persist,complete}, dockSchedule.read) "
             "+ loadingRobot.mission.dispatch")
