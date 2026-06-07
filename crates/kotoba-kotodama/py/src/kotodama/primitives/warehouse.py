"""
warehouse.* — LangServer handlers for WMS service tasks.

Task types:
  warehouse.sku.register
  warehouse.putaway.planBin
  warehouse.putaway.persist
  warehouse.pick.allocate
  warehouse.pick.persist
  warehouse.inventory.read

ADR-2605262130, ADR-2605312345 (kotoba Datom log = canonical state).
Cost-compression role: bin allocation + pick allocation are the
hook points for cost-aware optimization (LangGraph optimizer).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("warehouse.primitive")

_WAREHOUSE_DID = "did:web:warehouse.etzhayyim.com"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")


def _vid(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{_WAREHOUSE_DID}/com.etzhayyim.apps.warehouse.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"



# ── SKU master ───────────────────────────────────────────────────────────────

async def task_warehouse_sku_register(
    skuCode: str = "",
    description: str = "",
    unitOfMeasure: str = "EA",
    weightKg: str = "",
) -> dict:
    if not skuCode:
        return {"ok": False, "error": "skuCode required"}
    vid = _vid("sku")
    payload = {
        "skuCode": skuCode, "description": description,
        "unitOfMeasure": unitOfMeasure, "weightKg": weightKg,
    }
    client = get_kotoba_client()
    ok = False
    try:
        client.insert_row(
            "vertex_warehouse_sku",
            {
                "vertex_id": vid,
                "vertex_key": skuCode,
                "label": "warehouse.sku",
                "status": "active",
                "value_json": payload,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "owner_did": _WAREHOUSE_DID,
                "actor_did": _WAREHOUSE_DID,
                "sensitivity_ord": 2
            }
        )
        ok = True
    except Exception as exc:
        LOG.warning("warehouse.sku.register failed: %s", exc)
    return {"ok": ok, "vertexId": vid, "skuVertexId": vid}


# ── Putaway ─────────────────────────────────────────────────────────────────

async def task_warehouse_putaway_plan_bin(
    skuCode: str = "",
    quantity: int = 0,
    binCode: str = "",
) -> dict:
    """Pick a bin code. If client supplied one, honor it; else use a
    deterministic fallback. The LangGraph optimizer overrides this in
    production for cost-aware allocation."""
    if binCode:
        return {"ok": True, "assignedBinCode": binCode}
    try:
        from kotodama.langgraph_graphs.warehouse_yard_optimizer import (
            recommend_putaway_bin,
        )
        rec = recommend_putaway_bin(skuCode or "", int(quantity or 0))
        if rec.get("ok") and rec.get("bin_code"):
            return {"ok": True, "assignedBinCode": rec["bin_code"]}
    except Exception as exc:
        LOG.info("optimizer fallback (putaway_bin): %s", exc)
    suffix = uuid.uuid4().hex[:4].upper()
    return {"ok": True, "assignedBinCode": f"BIN-{skuCode[:6] or 'NEW'}-{suffix}"}


async def task_warehouse_putaway_persist(
    skuCode: str = "",
    quantity: int = 0,
    assignedBinCode: str = "",
    receivedAt: str = "",
) -> dict:
    if not skuCode or not assignedBinCode:
        return {"ok": False, "error": "skuCode + assignedBinCode required"}
    vid = _vid("putaway")
    payload = {
        "skuCode": skuCode, "quantity": int(quantity or 0),
        "binCode": assignedBinCode, "receivedAt": receivedAt or _now_iso(),
    }
    client = get_kotoba_client()
    ok = False
    try:
        client.insert_row(
            "vertex_warehouse_putaway",
            {
                "vertex_id": vid,
                "vertex_key": f"{skuCode}:{assignedBinCode}",
                "label": "warehouse.putaway",
                "status": "active",
                "value_json": payload,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "owner_did": _WAREHOUSE_DID,
                "actor_did": _WAREHOUSE_DID,
                "sensitivity_ord": 2
            }
        )
        ok = True
    except Exception as exc:
        LOG.warning("warehouse.putaway.persist failed: %s", exc)
    return {"ok": ok, "vertexId": vid, "putawayVertexId": vid,
            "assignedBinCode": assignedBinCode}


# ── Pick ────────────────────────────────────────────────────────────────────

async def task_warehouse_pick_allocate(
    orderId: str = "",
    skuCode: str = "",
    quantity: int = 0,
) -> dict:
    """Allocate stock from one or more bins. Naive FIFO: read putaway rows
    for skuCode, take bins until quantity satisfied. Optimizer can replace
    with travel-distance-aware allocation."""
    client = get_kotoba_client()
    query_edn = """
    [:find (pull ?e [:value_json])
     :where
     [?e :vertex/id _]
     [?e :label "warehouse.putaway"]
     [?e :status "active"]
     :order-by [?e :created_at :asc]
     :limit 50]
    """
    try:
        results = client.q(query_edn)
    except Exception as exc:
        LOG.warning("warehouse.pick.allocate query failed: %s", exc)
        results = []

    rows = [r[0] for r in results] # results from q are list[list], so extract the dict
    bins: list[str] = []
    remaining = int(quantity or 0)
    for row in rows:
        v = row.get("value_json", {})
        if v.get("skuCode") != skuCode:
            continue
        bins.append(v.get("binCode", ""))
        remaining -= int(v.get("quantity", 0) or 0)
        if remaining <= 0:
            break
    return {"ok": bool(bins), "pickedFromBins": bins}


async def task_warehouse_pick_persist(
    orderId: str = "",
    skuCode: str = "",
    quantity: int = 0,
    pickedFromBins: list | None = None,
) -> dict:
    if not orderId or not skuCode:
        return {"ok": False, "error": "orderId + skuCode required"}
    bins = pickedFromBins or []
    vid = _vid("pick")
    payload = {
        "orderId": orderId, "skuCode": skuCode,
        "quantity": int(quantity or 0), "bins": bins,
    }
    client = get_kotoba_client()
    ok = False
    try:
        client.insert_row(
            "vertex_warehouse_pick",
            {
                "vertex_id": vid,
                "vertex_key": f"{orderId}:{skuCode}",
                "label": "warehouse.pick",
                "status": "active",
                "value_json": payload,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "owner_did": _WAREHOUSE_DID,
                "actor_did": _WAREHOUSE_DID,
                "sensitivity_ord": 2
            }
        )
        ok = True
    except Exception as exc:
        LOG.warning("warehouse.pick.persist failed: %s", exc)
    return {"ok": ok, "vertexId": vid, "pickVertexId": vid,
            "pickedFromBins": bins}


# ── Inventory query ─────────────────────────────────────────────────────────

async def task_warehouse_inventory_read(skuCode: str = "") -> dict:
    if not skuCode:
        return {"ok": False, "onHandQty": 0, "bins": [], "error": "skuCode required"}
    client = get_kotoba_client()
    try:
        rows = client.select_where(
            "vertex_warehouse_putaway", "status", "active", columns=["value_json"]
        )
    except Exception as exc:
        LOG.warning("warehouse.inventory.read query failed: %s", exc)
        rows = []
    by_bin: dict[str, int] = {}
    for row in rows:
        v = row.get("value_json", {})
        if v.get("skuCode") != skuCode:
            continue
        bin_code = v.get("binCode", "")
        by_bin[bin_code] = by_bin.get(bin_code, 0) + int(v.get("quantity", 0) or 0)
    bins = [{"binCode": b, "qty": q} for b, q in by_bin.items()]
    on_hand = sum(by_bin.values())
    return {"ok": True, "skuCode": skuCode, "onHandQty": on_hand, "bins": bins}


# ── Registration ────────────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="warehouse.sku.register", timeout_ms=timeout_ms)
    async def _sku_register(skuCode: str = "", description: str = "",
                            unitOfMeasure: str = "EA", weightKg: str = "") -> dict:
        return await task_warehouse_sku_register(
            skuCode=skuCode, description=description,
            unitOfMeasure=unitOfMeasure, weightKg=weightKg)

    @app.task(task_type="warehouse.putaway.planBin", timeout_ms=timeout_ms)
    async def _putaway_plan(skuCode: str = "", quantity: int = 0,
                            binCode: str = "") -> dict:
        return await task_warehouse_putaway_plan_bin(
            skuCode=skuCode, quantity=quantity, binCode=binCode)

    @app.task(task_type="warehouse.putaway.persist", timeout_ms=timeout_ms)
    async def _putaway_persist(skuCode: str = "", quantity: int = 0,
                               assignedBinCode: str = "", receivedAt: str = "") -> dict:
        return await task_warehouse_putaway_persist(
            skuCode=skuCode, quantity=quantity,
            assignedBinCode=assignedBinCode, receivedAt=receivedAt)

    @app.task(task_type="warehouse.pick.allocate", timeout_ms=timeout_ms)
    async def _pick_allocate(orderId: str = "", skuCode: str = "",
                             quantity: int = 0) -> dict:
        return await task_warehouse_pick_allocate(
            orderId=orderId, skuCode=skuCode, quantity=quantity)

    @app.task(task_type="warehouse.pick.persist", timeout_ms=timeout_ms)
    async def _pick_persist(orderId: str = "", skuCode: str = "",
                            quantity: int = 0, pickedFromBins=None) -> dict:
        return await task_warehouse_pick_persist(
            orderId=orderId, skuCode=skuCode, quantity=quantity,
            pickedFromBins=pickedFromBins)

    @app.task(task_type="warehouse.inventory.read", timeout_ms=timeout_ms)
    async def _inventory_read(skuCode: str = "") -> dict:
        return await task_warehouse_inventory_read(skuCode=skuCode)

    LOG.info("Registered warehouse.* tasks (sku.register, putaway.{planBin,persist}, "
             "pick.{allocate,persist}, inventory.read)")
