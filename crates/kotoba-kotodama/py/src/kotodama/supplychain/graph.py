"""Supplychain resident agent — Pregel superstep implementation.

Reads cleaning-robot manufacturing supply graph from jukyu SoS tables
(domain='cleaning_robot') and propagates material shortage pressure
upstream through the supplier → material → assembly hierarchy.

DAG:
  init_run → read_balance → read_chain → propagate ←──┐
                                         │              │
                                    should_continue     │
                                       yes ─────────────┘
                                       no
                                         ↓
                                    write_signals → read_summary

Pregel constants:
  _MAX_ITER=8, _HALT_DELTA=0.03, _DAMPING=0.70
Score: 0.30×supply + 0.20×demand + 0.20×price + 0.20×downstream + 0.10×structural
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client

# ─── Constants ───────────────────────────────────────────────────────────────
_MAX_ITER = 8
_HALT_DELTA = 0.03
_DAMPING = 0.70
_ACTOR_DID = "did:web:supplychain.etzhayyim.com"
_GRAPH_NAME = "supplychain_cleaning_robot_v1"
_DEFAULT_DOMAIN = "cleaning_robot"

_CRITICAL_NODE_KINDS = frozenset({
    "assembly",
    "supplier",
    "material",
    "cleaning_robot_assembly",
    "cleaning_robot_material",
    "cleaning_robot_supplier",
})


# ─── State ───────────────────────────────────────────────────────────────────

class SupplychainState(TypedDict, total=False):
    runId: str
    domain: str | None
    seedCountry: str | None
    riskThreshold: float
    maxBalanceRows: int
    maxChainRows: int
    maxExposureRows: int
    startedAt: str
    # Data rows
    balanceRows: list[dict[str, Any]]
    chainRows: list[dict[str, Any]]
    exposureRows: list[dict[str, Any]]
    signalRows: list[dict[str, Any]]
    signalsInserted: int
    summaryRows: list[dict[str, Any]]
    # Pregel state
    pregelIter: int
    pregelMaxDelta: float
    nodePressures: dict[str, float]
    pregelSupersteps: list[dict[str, Any]]
    # Status
    ok: bool
    error: str | None


# ─── DB helpers ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    # R0: using q() escape hatch for arbitrary SQL select queries
    try:
        return get_kotoba_client().q(query_edn=sql, args=params)
    except Exception:
        return []


def _exec(sql: str, params: tuple[Any, ...] = ()) -> bool:
    # This function is now a no-op as DML operations are handled by kotoba_datomic.insert_row
    # and explicit DELETEs before INSERTs are no longer needed.
    return True


def _insert_run(state: SupplychainState, status: str, summary: dict[str, Any] | None = None) -> None:
    run_id = state.get("runId") or f"supplychain.{int(time.time())}"
    vertex_id = f"jukyu-run:{run_id}"
    row_dict = {
        "vertex_id": vertex_id,
        "created_date": _now_iso()[:10],
        "owner_did": _ACTOR_DID,
        "repo": _ACTOR_DID,
        "run_id": run_id,
        "graph_name": _GRAPH_NAME,
        "domain": state.get("domain") or _DEFAULT_DOMAIN,
        "seed_country_code": state.get("seedCountry"),
        "scenario_type": "resident_manufacturing",
        "shock_json": "{}",
        "max_iterations": _MAX_ITER,
        "started_at": state.get("startedAt") or _now_iso(),
        "completed_at": _now_iso() if status != "running" else None,
        "status": status,
        "summary_json": json.dumps(summary or {}, ensure_ascii=False, sort_keys=True),
        "collection": "com.etzhayyim.apps.supplychain.pregelRun",
        "actor_did": _ACTOR_DID,
        "org_did": "did:web:etzhayyim.com",
    }
    get_kotoba_client().insert_row("vertex_jukyu_pregel_run", row_dict)


# ─── Pregel pure helpers (same algorithm as jukyu) ───────────────────────────

def _init_pressures_from_balance(
    balance_rows: list[dict[str, Any]],
    chain_rows: list[dict[str, Any]],
) -> dict[str, float]:
    """Map country-level balance deficit to individual supply nodes (superstep 0)."""
    country_pressure: dict[str, float] = {}
    for row in balance_rows:
        domain = str(row.get("domain") or "")
        country = str(row.get("country_code") or "ZZ")
        balance = float(row.get("balance_quantity") or 0.0)
        demand = float(row.get("demand_quantity") or 1.0)
        pressure = min(1.0, abs(balance) / max(abs(demand), 1.0)) if balance < 0 else 0.0
        key = f"{domain}:{country}"
        country_pressure[key] = max(country_pressure.get(key, 0.0), pressure)

    node_pressures: dict[str, float] = {}
    for edge in chain_rows:
        for vid, dc in [
            (edge.get("src_vid"), (edge.get("domain"), edge.get("src_country_code"))),
            (edge.get("dst_vid"), (edge.get("domain"), edge.get("dst_country_code"))),
        ]:
            if not vid:
                continue
            domain, country = dc
            if not domain:
                continue
            p = country_pressure.get(f"{domain}:{country or 'ZZ'}", 0.0)
            vid_str = str(vid)
            node_pressures[vid_str] = max(node_pressures.get(vid_str, 0.0), p)

    return node_pressures


def _propagate_pressure_step(
    node_pressures: dict[str, float],
    chain_rows: list[dict[str, Any]],
) -> tuple[dict[str, float], float]:
    """One Pregel superstep: propagate supply shortage pressure upstream."""
    new_pressures = dict(node_pressures)

    for edge in chain_rows:
        src_vid = str(edge.get("src_vid") or "")
        dst_vid = str(edge.get("dst_vid") or "")
        weight = float(edge.get("dependency_weight") or 0.0)
        if not src_vid or not dst_vid or weight <= 0:
            continue
        dst_p = node_pressures.get(dst_vid, 0.0)
        if dst_p > 0:
            new_pressures[src_vid] = min(
                1.0,
                new_pressures.get(src_vid, 0.0) + weight * dst_p * _DAMPING,
            )

    all_vids = set(new_pressures) | set(node_pressures)
    max_delta = max(
        (abs(new_pressures.get(v, 0.0) - node_pressures.get(v, 0.0)) for v in all_vids),
        default=0.0,
    )
    return new_pressures, max_delta


def _compute_company_exposures(
    node_pressures: dict[str, float],
    chain_rows: list[dict[str, Any]],
    balance_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute supplier-level risk scores from Pregel node pressures."""
    company_supply_vids: dict[str, list[str]] = {}
    company_demand_vids: dict[str, list[str]] = {}
    company_meta: dict[str, dict[str, Any]] = {}
    node_kind_map: dict[str, str] = {}

    for edge in chain_rows:
        src_vid = str(edge.get("src_vid") or "")
        dst_vid = str(edge.get("dst_vid") or "")
        src_op = str(edge.get("src_operator_did") or "")
        dst_op = str(edge.get("dst_operator_did") or "")
        domain = str(edge.get("domain") or "")
        product_code = str(edge.get("product_code") or "")
        product_family = str(edge.get("product_family") or "")

        if src_vid:
            node_kind_map[src_vid] = str(edge.get("src_node_kind") or "")
        if dst_vid:
            node_kind_map[dst_vid] = str(edge.get("dst_node_kind") or "")

        if src_op and src_vid:
            company_supply_vids.setdefault(src_op, []).append(src_vid)
            company_meta.setdefault(src_op, {
                "domain": domain,
                "country": str(edge.get("src_country_code") or "ZZ"),
                "product_code": product_code,
                "product_family": product_family,
                "name": str(edge.get("src_name") or src_op),
            })
        if dst_op and dst_vid:
            company_demand_vids.setdefault(dst_op, []).append(dst_vid)
            company_meta.setdefault(dst_op, {
                "domain": domain,
                "country": str(edge.get("dst_country_code") or "ZZ"),
                "product_code": product_code,
                "product_family": product_family,
                "name": str(edge.get("dst_name") or dst_op),
            })

    price_pressure_map: dict[str, float] = {}
    for row in balance_rows:
        domain = str(row.get("domain") or "")
        country = str(row.get("country_code") or "ZZ")
        balance = float(row.get("balance_quantity") or 0.0)
        demand = float(row.get("demand_quantity") or 1.0)
        if balance < 0:
            price_pressure_map[f"{domain}:{country}"] = min(
                1.0, abs(balance) / max(abs(demand), 1.0) * 0.8
            )

    exposures: list[dict[str, Any]] = []
    for company_did in set(company_supply_vids) | set(company_demand_vids):
        supply_vids = list(set(company_supply_vids.get(company_did, [])))
        demand_vids = list(set(company_demand_vids.get(company_did, [])))
        all_vids = list(set(supply_vids + demand_vids))
        if not all_vids:
            continue

        meta = company_meta.get(company_did, {})
        domain = meta.get("domain", "")
        country = meta.get("country", "ZZ")

        supply_ps = [node_pressures.get(v, 0.0) for v in supply_vids]
        demand_ps = [node_pressures.get(v, 0.0) for v in demand_vids]
        all_ps = [node_pressures.get(v, 0.0) for v in all_vids]

        supply_pressure = max(supply_ps) if supply_ps else 0.0
        demand_pressure = sum(demand_ps) / len(demand_ps) if demand_ps else 0.0
        downstream_pressure = sum(all_ps) / len(all_ps) if all_ps else 0.0
        critical_count = sum(
            1 for v in all_vids if node_kind_map.get(v, "") in _CRITICAL_NODE_KINDS
        )
        structural_pressure = min(1.0, critical_count / max(len(all_vids), 1))
        price_pressure = price_pressure_map.get(f"{domain}:{country}", 0.0)

        risk_score = min(0.95, (
            0.30 * supply_pressure
            + 0.20 * demand_pressure
            + 0.20 * price_pressure
            + 0.20 * downstream_pressure
            + 0.10 * structural_pressure
        ))

        connectivity = min(1.0, len(all_vids) / 10.0)
        confidence = min(1.0,
            0.30 * 0.65      # freshness proxy (resident 15-min loop)
            + 0.25 * 0.70    # reliability from adapter source
            + 0.20 * connectivity
            + 0.15 * 0.50    # supplier qualification proxy
            + 0.10 * 0.50    # corroboration proxy
        )

        exposures.append({
            "company_did": company_did,
            "company_name": meta.get("name", company_did),
            "domain": domain,
            "country_code": country,
            "product_code": meta.get("product_code", ""),
            "product_family": meta.get("product_family", ""),
            "supply_pressure": supply_pressure,
            "demand_pressure": demand_pressure,
            "price_pressure": price_pressure,
            "downstream_pressure": downstream_pressure,
            "structural_pressure": structural_pressure,
            "risk_score": risk_score,
            "confidence": confidence,
        })

    return exposures


def _upsert_company_exposures(exposures: list[dict[str, Any]], run_id: str) -> int:
    pregel_run_id = f"pregel:{run_id}"

    inserted = 0
    for row in exposures:
        company_did = str(row.get("company_did") or "")
        if not company_did:
            continue
        domain = str(row.get("domain") or _DEFAULT_DOMAIN)
        country = str(row.get("country_code") or "ZZ")
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{pregel_run_id}:{domain}:{country}:{company_did}")
        vertex_id = f"jukyu-exposure:pregel:{uid}"
        exposure_id = f"pregel:{run_id}:{domain}:{company_did}:{country}".replace(" ", "_")

        row_dict = {
            "vertex_id": vertex_id,
            "created_date": _now_iso()[:10],
            "sensitivity_ord": 1,
            "owner_did": _ACTOR_DID,
            "repo": _ACTOR_DID,
            "exposure_id": exposure_id,
            "run_id": pregel_run_id,
            "company_did": company_did,
            "company_name": str(row.get("company_name") or company_did),
            "domain": domain,
            "country_code": country,
            "product_code": str(row.get("product_code") or ""),
            "product_family": str(row.get("product_family") or ""),
            "supply_pressure": float(row.get("supply_pressure") or 0.0),
            "demand_pressure": float(row.get("demand_pressure") or 0.0),
            "price_pressure": float(row.get("price_pressure") or 0.0),
            "downstream_pressure": float(row.get("downstream_pressure") or 0.0),
            "structural_pressure": float(row.get("structural_pressure") or 0.0),
            "risk_score": float(row.get("risk_score") or 0.0),
            "confidence": float(row.get("confidence") or 0.0),
            "evidence_json": json.dumps([{"source": "pregel_propagation", "runId": run_id}], ensure_ascii=False),
            "recommended_action": "Review alternate material suppliers and qualification pipeline.",
            "status": "active",
            "collection": "com.etzhayyim.apps.supplychain.companyExposure",
            "actor_did": _ACTOR_DID,
            "org_did": "did:web:etzhayyim.com",
        }
        ok = get_kotoba_client().insert_row("vertex_jukyu_company_exposure", row_dict)
        if ok:
            inserted += 1

    return inserted


# ─── Graph nodes ──────────────────────────────────────────────────────────────

def init_run(state: SupplychainState) -> dict[str, Any]:
    run_id = state.get("runId") or (
        f"supplychain.{_now_iso().replace(':', '').replace('-', '')}.{uuid.uuid4().hex[:8]}"
    )
    out: dict[str, Any] = {
        "runId": run_id,
        "domain": state.get("domain") or _DEFAULT_DOMAIN,
        "riskThreshold": float(state.get("riskThreshold") or 0.55),
        "maxBalanceRows": int(state.get("maxBalanceRows") or 100),
        "maxChainRows": int(state.get("maxChainRows") or 500),
        "maxExposureRows": int(state.get("maxExposureRows") or 250),
        "startedAt": _now_iso(),
        "ok": True,
        "error": None,
        "pregelIter": 0,
        "pregelMaxDelta": 1.0,
        "nodePressures": {},
        "pregelSupersteps": [],
    }
    out["seedCountry"] = state.get("seedCountry")
    _insert_run({**state, **out}, "running", {"phase": "started"})
    return out


def read_balance(state: SupplychainState) -> dict[str, Any]:
    domain = state.get("domain") or _DEFAULT_DOMAIN
    country = state.get("seedCountry")
    limit = int(state.get("maxBalanceRows") or 100)
    where = ["domain = %s"]
    params: list[Any] = [domain]
    if country:
        where.append("country_code = %s")
        params.append(country)
    sql = "SELECT * FROM mv_jukyu_global_balance WHERE " + " AND ".join(where)
    sql += f" ORDER BY ABS(balance_quantity) DESC LIMIT {limit}"
    return {"balanceRows": _rows(sql, tuple(params))}


def read_chain(state: SupplychainState) -> dict[str, Any]:
    domain = state.get("domain") or _DEFAULT_DOMAIN
    country = state.get("seedCountry")
    limit = int(state.get("maxChainRows") or 500)
    where = ["domain = %s"]
    params: list[Any] = [domain]
    if country:
        where.append("(src_country_code = %s OR dst_country_code = %s)")
        params.extend([country, country])
    sql = "SELECT * FROM mv_jukyu_supply_chain_trace WHERE " + " AND ".join(where)
    sql += f" ORDER BY COALESCE(dependency_weight, 0.0) DESC LIMIT {limit}"
    return {"chainRows": _rows(sql, tuple(params))}


def propagate(state: SupplychainState) -> dict[str, Any]:
    """One Pregel superstep: propagate material shortage pressure upstream."""
    chain_rows = state.get("chainRows") or []
    balance_rows = state.get("balanceRows") or []
    iter_num = int(state.get("pregelIter") or 0)
    supersteps = list(state.get("pregelSupersteps") or [])

    node_pressures = dict(state.get("nodePressures") or {})
    if not node_pressures:
        node_pressures = _init_pressures_from_balance(balance_rows, chain_rows)

    node_pressures, max_delta = _propagate_pressure_step(node_pressures, chain_rows)
    iter_num += 1

    exposure_rows = _compute_company_exposures(node_pressures, chain_rows, balance_rows)
    supersteps.append({
        "iter": iter_num,
        "maxDelta": round(max_delta, 6),
        "exposures": len(exposure_rows),
    })

    return {
        "pregelIter": iter_num,
        "pregelMaxDelta": max_delta,
        "nodePressures": node_pressures,
        "pregelSupersteps": supersteps,
        "exposureRows": exposure_rows,
    }


def should_continue(state: SupplychainState) -> str:
    """Conditional edge: continue propagating or move to write_signals."""
    if int(state.get("pregelIter") or 0) >= _MAX_ITER:
        return "write_signals"
    if float(state.get("pregelMaxDelta") or 1.0) < _HALT_DELTA:
        return "write_signals"
    return "propagate"


def write_signals(state: SupplychainState) -> dict[str, Any]:
    run_id = state.get("runId") or f"supplychain.{int(time.time())}"
    threshold = float(state.get("riskThreshold") or 0.55)
    all_exposures = state.get("exposureRows") or []
    domain = state.get("domain") or _DEFAULT_DOMAIN

    _upsert_company_exposures(all_exposures, run_id)

    exposures = [r for r in all_exposures if float(r.get("risk_score") or 0.0) >= threshold]

    inserted = 0
    signal_rows: list[dict[str, Any]] = []
    for row in exposures:
        company_did = str(row.get("company_did") or "").strip()
        if not company_did:
            continue
        risk = float(row.get("risk_score") or 0.0)
        severity = "critical" if risk >= 0.8 else "high" if risk >= 0.65 else "medium"
        country_code = str(row.get("country_code") or "ZZ")
        product_code = str(row.get("product_code") or row.get("product_family") or "unknown")
        signal_id = (
            f"supplychain:{run_id}:{domain}:{country_code}:{product_code}:{company_did}"
            .replace(" ", "_")
        )
        vertex_id = f"jukyu-signal:{uuid.uuid5(uuid.NAMESPACE_URL, signal_id)}"

        title = f"Supplychain {severity} material shortage: {domain}"
        body = (
            f"Risk score {risk:.2f} for {row.get('company_name') or company_did}; "
            f"material={product_code}."
        )
        row_dict = {
            "vertex_id": vertex_id,
            "created_date": _now_iso()[:10],
            "sensitivity_ord": 1,
            "owner_did": _ACTOR_DID,
            "repo": _ACTOR_DID,
            "signal_id": signal_id,
            "run_id": run_id,
            "target_company_did": company_did,
            "target_channel": "mcp",
            "domain": domain,
            "country_code": country_code,
            "product_code": row.get("product_code"),
            "product_family": row.get("product_family"),
            "severity": severity,
            "risk_score": risk,
            "confidence": float(row.get("confidence") or 0.0),
            "title": title,
            "body": body,
            "evidence_json": json.dumps([{"source": "pregel_propagation", "runId": run_id}], ensure_ascii=False),
            "recommended_action": "Qualify additional material suppliers and increase safety stock.",
            "notification_status": "pending",
            "emitted_at": _now_iso(),
            "collection": "com.etzhayyim.apps.supplychain.notificationSignal",
            "actor_did": _ACTOR_DID,
            "org_did": "did:web:etzhayyim.com",
        }
        ok = get_kotoba_client().insert_row("vertex_jukyu_notification_signal", row_dict)
        if ok:
            inserted += 1
            signal_rows.append({
                "signalId": signal_id,
                "targetCompanyDid": company_did,
                "countryCode": country_code,
                "productCode": product_code,
                "severity": severity,
                "riskScore": risk,
            })

    return {"signalsInserted": inserted, "signalRows": signal_rows}


def read_summary(state: SupplychainState) -> dict[str, Any]:
    domain = state.get("domain") or _DEFAULT_DOMAIN
    rows = _rows(
        """
        SELECT * FROM mv_jukyu_notification_outbox
        WHERE domain = %s
        ORDER BY risk_score DESC LIMIT 100
        """,
        (domain,),
    )
    summary = {
        "balanceRows": len(state.get("balanceRows") or []),
        "chainRows": len(state.get("chainRows") or []),
        "exposureRows": len(state.get("exposureRows") or []),
        "signalsInserted": int(state.get("signalsInserted") or 0),
        "summaryRows": len(rows),
        "pregelIter": int(state.get("pregelIter") or 0),
        "pregelMaxDelta": round(float(state.get("pregelMaxDelta") or 0.0), 6),
        "pregelSupersteps": state.get("pregelSupersteps") or [],
    }
    _insert_run(state, "completed", summary)
    return {"summaryRows": rows, "ok": True, "error": None}


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(SupplychainState)
    builder.add_node("init_run", init_run)
    builder.add_node("read_balance", read_balance)
    builder.add_node("read_chain", read_chain)
    builder.add_node("propagate", propagate)
    builder.add_node("write_signals", write_signals)
    builder.add_node("read_summary", read_summary)

    builder.set_entry_point("init_run")
    builder.add_edge("init_run", "read_balance")
    builder.add_edge("read_balance", "read_chain")
    builder.add_edge("read_chain", "propagate")
    builder.add_conditional_edges(
        "propagate",
        should_continue,
        {"propagate": "propagate", "write_signals": "write_signals"},
    )
    builder.add_edge("write_signals", "read_summary")
    builder.add_edge("read_summary", END)
    return builder.compile()
