"""Jukyu global equilibrium resident agent loop — Pregel superstep implementation.

DAG:
  init_run → read_balance → read_chain → read_transport_context → propagate ←──┐
                                                                  │            │
                                                             should_continue   │
                                                                yes ───────────┘
                                                                no
                                                                  ↓
                                                             write_signals → read_outbox

Pregel superstep propagates supply shortage pressure upstream through
edge_jukyu_supply_dependency edges and vessel/transport context (damping=0.70). Halts when
max Δscore < 0.03 or iter ≥ 8.

Score formula:
  base = 0.30×supply + 0.20×demand + 0.20×price + 0.20×downstream + 0.10×structural
  final = min(0.95, base + 0.10×transport)
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import json
import time
import uuid
from typing import Any, TypedDict


# ─── Pregel constants ────────────────────────────────────────────────────────
_MAX_ITER = 8
_HALT_DELTA = 0.03
_DAMPING = 0.70
_CRITICAL_NODE_KINDS = frozenset({
    "refinery", "steam_cracker", "petrochemical_plant", "splitter",
    "LNG_terminal", "lng_terminal", "oil_field", "oil_terminal",
    "export_terminal", "import_terminal", "port_terminal",
})
_RISKY_TRANSPORT_STATUSES = frozenset({
    "delayed", "diverted", "rerouted", "dark_ais", "sanction_screening",
    "blocked", "congested", "disrupted",
})


# ─── State ───────────────────────────────────────────────────────────────────

class JukyuState(TypedDict, total=False):
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
    transportRows: list[dict[str, Any]]
    exposureRows: list[dict[str, Any]]
    signalRows: list[dict[str, Any]]
    signalsInserted: int
    outboxRows: list[dict[str, Any]]
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
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql, params)
            names = [desc[0] for desc in [] or []]
            return [dict(zip(names, row, strict=False)) for row in (_res or [])]
    except Exception:
        return []


def _exec(sql: str, params: tuple[Any, ...] = ()) -> bool:
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql, params)
        return True
    except Exception:
        return False


def _insert_run(state: JukyuState, status: str, summary: dict[str, Any] | None = None) -> None:
    run_id = state.get("runId") or f"jukyu.global.{int(time.time())}"
    vertex_id = f"jukyu-run:{run_id}"
    _exec("DELETE FROM vertex_jukyu_pregel_run WHERE vertex_id = %s", (vertex_id,))
    _exec(
        """
        INSERT INTO vertex_jukyu_pregel_run
          (vertex_id, created_date, owner_did, repo, run_id, graph_name,
           domain, seed_country_code, scenario_type, shock_json,
           max_iterations, started_at, completed_at, status, summary_json,
           collection, actor_did, org_did)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            vertex_id,
            _now_iso()[:10],
            "did:web:jukyu.etzhayyim.com",
            "did:web:jukyu.etzhayyim.com",
            run_id,
            "jukyu_global_equilibrium_v1",
            state.get("domain"),
            state.get("seedCountry"),
            "resident_equilibrium",
            "{}",
            _MAX_ITER,
            state.get("startedAt") or _now_iso(),
            _now_iso() if status != "running" else None,
            status,
            json.dumps(summary or {}, ensure_ascii=False, sort_keys=True),
            "com.etzhayyim.apps.jukyu.pregelRun",
            "did:web:jukyu.etzhayyim.com",
            "did:web:etzhayyim.com",
        ),
    )


# ─── Pregel pure helpers ──────────────────────────────────────────────────────

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
    """One Pregel superstep: propagate supply shortage pressure upstream.

    Edge src→dst means src supplies dst.  When dst has a shortage (positive
    pressure) we propagate upstream to src weighted by dependency_weight.
    """
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
    transport_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compute company-level risk scores from Pregel node pressures.

    Score:
      base = 0.30×supply + 0.20×demand + 0.20×price + 0.20×downstream + 0.10×structural
      final = min(0.95, base + 0.10×transport)
    """
    company_supply_vids: dict[str, list[str]] = {}
    company_demand_vids: dict[str, list[str]] = {}
    company_transport_vids: dict[str, list[str]] = {}
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
                "name": str(edge.get("src_operator_name") or edge.get("src_name") or src_op),
            })
        if dst_op and dst_vid:
            company_demand_vids.setdefault(dst_op, []).append(dst_vid)
            company_meta.setdefault(dst_op, {
                "domain": domain,
                "country": str(edge.get("dst_country_code") or "ZZ"),
                "product_code": product_code,
                "product_family": product_family,
                "name": str(edge.get("dst_operator_name") or edge.get("dst_name") or dst_op),
            })

    transport_pressure_by_node = _transport_pressure_by_node(transport_rows or [])
    transport_pressure_by_company: dict[str, float] = {}
    transport_evidence_by_company: dict[str, list[dict[str, Any]]] = {}
    for row in transport_rows or []:
        dst_vid = str(row.get("dst_vid") or row.get("destination_node_vid") or "")
        domain = str(row.get("domain") or "")
        product_code = str(row.get("product_code") or "")
        product_family = str(row.get("product_family") or "")
        country = _country_from_node(chain_rows, dst_vid) or "ZZ"
        pressure = _transport_row_pressure(row)
        for role_key, role_label, name_key in [
            ("carrier_did", "carrier", "carrier_name"),
            ("shipowner_did", "shipowner", "shipowner_name"),
            ("operator_did", "vessel_operator", "operator_name"),
            ("charterer_did", "charterer", "charterer_name"),
        ]:
            company_did = str(row.get(role_key) or "")
            if not company_did:
                continue
            if dst_vid:
                company_transport_vids.setdefault(company_did, []).append(dst_vid)
            transport_pressure_by_company[company_did] = max(
                transport_pressure_by_company.get(company_did, 0.0),
                pressure,
            )
            company_meta.setdefault(company_did, {
                "domain": domain,
                "country": country,
                "product_code": product_code,
                "product_family": product_family,
                "name": str(row.get(name_key) or company_did),
                "transport_role": role_label,
            })
            transport_evidence_by_company.setdefault(company_did, []).append({
                "source": "mv_jukyu_transport_context",
                "role": role_label,
                "legId": row.get("leg_id"),
                "vesselImo": row.get("vessel_imo"),
                "vesselName": row.get("vessel_name"),
                "origin": row.get("origin_locode"),
                "destination": row.get("destination_locode"),
                "status": row.get("status"),
                "routeRiskScore": row.get("route_risk_score"),
                "etaDelayHours": row.get("eta_delay_hours"),
            })

    # Country-level price pressure proxy (balance deficit ratio)
    price_pressure_map: dict[str, float] = {}
    for row in balance_rows:
        domain = str(row.get("domain") or "")
        country = str(row.get("country_code") or "ZZ")
        balance = float(row.get("balance_quantity") or 0.0)
        demand = float(row.get("demand_quantity") or 1.0)
        if balance < 0:
            price_pressure_map[f"{domain}:{country}"] = min(1.0, abs(balance) / max(abs(demand), 1.0) * 0.8)

    exposures: list[dict[str, Any]] = []
    for company_did in set(company_supply_vids) | set(company_demand_vids) | set(company_transport_vids):
        supply_vids = list(set(company_supply_vids.get(company_did, [])))
        demand_vids = list(set(company_demand_vids.get(company_did, [])))
        transport_vids = list(set(company_transport_vids.get(company_did, [])))
        all_vids = list(set(supply_vids + demand_vids + transport_vids))
        if not all_vids:
            continue

        meta = company_meta.get(company_did, {})
        domain = meta.get("domain", "")
        country = meta.get("country", "ZZ")

        supply_ps = [node_pressures.get(v, 0.0) for v in supply_vids]
        demand_ps = [node_pressures.get(v, 0.0) for v in demand_vids]
        all_ps = [
            max(node_pressures.get(v, 0.0), transport_pressure_by_node.get(v, 0.0))
            for v in all_vids
        ]

        supply_pressure = max(supply_ps) if supply_ps else 0.0
        demand_pressure = sum(demand_ps) / len(demand_ps) if demand_ps else 0.0
        downstream_pressure = sum(all_ps) / len(all_ps) if all_ps else 0.0
        transport_pressure = transport_pressure_by_company.get(company_did, 0.0)
        critical_count = sum(1 for v in all_vids if node_kind_map.get(v, "") in _CRITICAL_NODE_KINDS)
        structural_pressure = min(1.0, critical_count / max(len(all_vids), 1))
        price_pressure = price_pressure_map.get(f"{domain}:{country}", 0.0)

        base_risk = (
            0.30 * supply_pressure
            + 0.20 * demand_pressure
            + 0.20 * price_pressure
            + 0.20 * downstream_pressure
            + 0.10 * structural_pressure
        )
        risk_score = min(0.95, base_risk + 0.10 * transport_pressure)

        connectivity = min(1.0, len(all_vids) / 10.0)
        confidence = min(1.0,
            0.30 * 0.70      # freshness proxy (resident 15-min loop)
            + 0.25 * 0.72    # reliability from adapter source
            + 0.20 * connectivity
            + 0.15 * 0.50    # cargo observation proxy
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
            "evidence_json": json.dumps(
                transport_evidence_by_company.get(company_did, [{"source": "pregel_propagation"}])[:8],
                ensure_ascii=False,
            ),
        })

    return exposures


def _country_from_node(chain_rows: list[dict[str, Any]], node_vid: str) -> str:
    for edge in chain_rows:
        if str(edge.get("src_vid") or "") == node_vid:
            return str(edge.get("src_country_code") or "")
        if str(edge.get("dst_vid") or "") == node_vid:
            return str(edge.get("dst_country_code") or "")
    return ""


def _transport_row_pressure(row: dict[str, Any]) -> float:
    route_risk = float(row.get("route_risk_score") or 0.0)
    delay_hours = max(0.0, float(row.get("eta_delay_hours") or 0.0))
    delay_pressure = min(1.0, delay_hours / 72.0)
    status = str(row.get("status") or "").lower()
    status_pressure = 0.75 if status in _RISKY_TRANSPORT_STATUSES else 0.0
    return min(1.0, max(route_risk, delay_pressure, status_pressure))


def _transport_pressure_by_node(transport_rows: list[dict[str, Any]]) -> dict[str, float]:
    pressure: dict[str, float] = {}
    for row in transport_rows:
        p = _transport_row_pressure(row)
        for key in ("src_vid", "dst_vid", "origin_node_vid", "destination_node_vid"):
            vid = str(row.get(key) or "")
            if vid:
                pressure[vid] = max(pressure.get(vid, 0.0), p)
    return pressure


def _upsert_company_exposures(exposures: list[dict[str, Any]], run_id: str) -> int:
    """Persist Pregel-computed company exposures (delete-then-insert per CLAUDE.md)."""
    pregel_run_id = f"pregel:{run_id}"
    _exec("DELETE FROM vertex_jukyu_company_exposure WHERE run_id = %s", (pregel_run_id,))

    inserted = 0
    for row in exposures:
        company_did = str(row.get("company_did") or "")
        if not company_did:
            continue
        domain = str(row.get("domain") or "unknown")
        country = str(row.get("country_code") or "ZZ")
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{pregel_run_id}:{domain}:{country}:{company_did}")
        vertex_id = f"jukyu-exposure:pregel:{uid}"
        exposure_id = f"pregel:{run_id}:{domain}:{company_did}:{country}".replace(" ", "_")

        ok = _exec(
            """
            INSERT INTO vertex_jukyu_company_exposure
              (vertex_id, created_date, sensitivity_ord, owner_did, repo,
               exposure_id, run_id, company_did, company_name, domain, country_code,
               product_code, product_family, supply_pressure, demand_pressure, price_pressure,
               downstream_pressure, structural_pressure, risk_score, confidence,
               evidence_json, recommended_action, status, collection, actor_did, org_did)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                vertex_id, _now_iso()[:10], 1,
                "did:web:jukyu.etzhayyim.com", "did:web:jukyu.etzhayyim.com",
                exposure_id, pregel_run_id, company_did,
                str(row.get("company_name") or company_did),
                domain, country,
                str(row.get("product_code") or ""),
                str(row.get("product_family") or ""),
                float(row.get("supply_pressure") or 0.0),
                float(row.get("demand_pressure") or 0.0),
                float(row.get("price_pressure") or 0.0),
                float(row.get("downstream_pressure") or 0.0),
                float(row.get("structural_pressure") or 0.0),
                float(row.get("risk_score") or 0.0),
                float(row.get("confidence") or 0.0),
                row.get("evidence_json") or json.dumps([{"source": "pregel_propagation", "runId": run_id}], ensure_ascii=False),
                "Review alternate supply routes, term coverage, and inventory buffer.",
                "active",
                "com.etzhayyim.apps.jukyu.companyExposure",
                "did:web:jukyu.etzhayyim.com",
                "did:web:etzhayyim.com",
            ),
        )
        if ok:
            inserted += 1

    return inserted


# ─── Graph nodes ──────────────────────────────────────────────────────────────

def init_run(state: JukyuState) -> dict[str, Any]:
    run_id = state.get("runId") or (
        f"jukyu.global.{_now_iso().replace(':', '').replace('-', '')}.{uuid.uuid4().hex[:8]}"
    )
    out: dict[str, Any] = {
        "runId": run_id,
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
    out["domain"] = state.get("domain")
    out["seedCountry"] = state.get("seedCountry")
    _insert_run({**state, **out}, "running", {"phase": "started"})
    return out


def read_balance(state: JukyuState) -> dict[str, Any]:
    domain = state.get("domain")
    country = state.get("seedCountry")
    limit = int(state.get("maxBalanceRows") or 100)
    where, params = [], []
    if domain:
        where.append("domain = %s")
        params.append(domain)
    if country:
        where.append("country_code = %s")
        params.append(country)
    sql = "SELECT * FROM mv_jukyu_global_balance"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY ABS(balance_quantity) DESC LIMIT {limit}"
    return {"balanceRows": _rows(sql, tuple(params))}


def read_chain(state: JukyuState) -> dict[str, Any]:
    domain = state.get("domain")
    country = state.get("seedCountry")
    limit = int(state.get("maxChainRows") or 500)
    where, params = [], []
    if domain:
        where.append("domain = %s")
        params.append(domain)
    if country:
        where.append("(src_country_code = %s OR dst_country_code = %s)")
        params.extend([country, country])
    sql = "SELECT * FROM mv_jukyu_supply_chain_trace"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY COALESCE(dependency_weight, 0.0) DESC LIMIT {limit}"
    return {"chainRows": _rows(sql, tuple(params))}


def read_transport_context(state: JukyuState) -> dict[str, Any]:
    domain = state.get("domain")
    country = state.get("seedCountry")
    limit = int(state.get("maxChainRows") or 500)
    where, params = [], []
    if domain:
        where.append("domain = %s")
        params.append(domain)
    if country:
        where.append(
            "(src_vid IN (SELECT vertex_id FROM vertex_jukyu_supply_node WHERE country_code = %s) "
            "OR dst_vid IN (SELECT vertex_id FROM vertex_jukyu_supply_node WHERE country_code = %s))"
        )
        params.extend([country, country])
    sql = "SELECT * FROM mv_jukyu_transport_context"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY COALESCE(route_risk_score, 0.0) DESC, COALESCE(eta_delay_hours, 0.0) DESC LIMIT {limit}"
    return {"transportRows": _rows(sql, tuple(params))}


def propagate(state: JukyuState) -> dict[str, Any]:
    """One Pregel superstep: propagate pressure, recompute company exposures."""
    chain_rows = state.get("chainRows") or []
    transport_rows = state.get("transportRows") or []
    balance_rows = state.get("balanceRows") or []
    iter_num = int(state.get("pregelIter") or 0)
    supersteps = list(state.get("pregelSupersteps") or [])

    node_pressures = dict(state.get("nodePressures") or {})
    if not node_pressures:
        node_pressures = _init_pressures_from_balance(balance_rows, chain_rows)

    node_pressures, max_delta = _propagate_pressure_step(node_pressures, chain_rows)
    iter_num += 1

    exposure_rows = _compute_company_exposures(node_pressures, chain_rows, balance_rows, transport_rows)
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


def should_continue(state: JukyuState) -> str:
    """Conditional edge: continue propagating or move to write_signals."""
    if int(state.get("pregelIter") or 0) >= _MAX_ITER:
        return "write_signals"
    if float(state.get("pregelMaxDelta") or 1.0) < _HALT_DELTA:
        return "write_signals"
    return "propagate"


def write_signals(state: JukyuState) -> dict[str, Any]:
    run_id = state.get("runId") or f"jukyu.global.{int(time.time())}"
    threshold = float(state.get("riskThreshold") or 0.55)
    all_exposures = state.get("exposureRows") or []

    # Persist final Pregel exposures to DB
    _upsert_company_exposures(all_exposures, run_id)

    # Filter by threshold for signal emission
    exposures = [r for r in all_exposures if float(r.get("risk_score") or 0.0) >= threshold]

    inserted = 0
    signal_rows: list[dict[str, Any]] = []
    for row in exposures:
        company_did = str(row.get("company_did") or "").strip()
        if not company_did:
            continue
        risk = float(row.get("risk_score") or 0.0)
        severity = "critical" if risk >= 0.8 else "high" if risk >= 0.65 else "medium"
        domain = str(row.get("domain") or state.get("domain") or "unknown")
        country_code = str(row.get("country_code") or "ZZ")
        product_code = str(row.get("product_code") or row.get("product_family") or "unknown")
        signal_id = f"jukyu:{run_id}:{domain}:{country_code}:{product_code}:{company_did}".replace(" ", "_")
        vertex_id = f"jukyu-signal:{uuid.uuid5(uuid.NAMESPACE_URL, signal_id)}"
        title = f"Jukyu {severity} supply-demand signal: {domain}"
        body = (
            f"Risk score {risk:.2f} for {row.get('company_name') or company_did}; "
            f"product={row.get('product_code') or row.get('product_family') or 'unknown'}."
        )
        _exec("DELETE FROM vertex_jukyu_notification_signal WHERE vertex_id = %s", (vertex_id,))
        ok = _exec(
            """
            INSERT INTO vertex_jukyu_notification_signal
              (vertex_id, created_date, sensitivity_ord, owner_did, repo,
               signal_id, run_id, target_company_did, target_channel, domain, country_code,
               product_code, product_family, severity, risk_score, confidence,
               title, body, evidence_json, recommended_action, notification_status,
               emitted_at, collection, actor_did, org_did)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                vertex_id, _now_iso()[:10], 1,
                "did:web:jukyu.etzhayyim.com", "did:web:jukyu.etzhayyim.com",
                signal_id, run_id,
                company_did, "mcp",
                domain, row.get("country_code"),
                row.get("product_code"), row.get("product_family"),
                severity, risk,
                float(row.get("confidence") or 0.0),
                title, body,
                row.get("evidence_json") or "[]",
                row.get("recommended_action") or "Review alternate supply paths and inventory buffer.",
                "pending",
                _now_iso(),
                "com.etzhayyim.apps.jukyu.notificationSignal",
                "did:web:jukyu.etzhayyim.com",
                "did:web:etzhayyim.com",
            ),
        )
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


def read_outbox(state: JukyuState) -> dict[str, Any]:
    rows = _rows(
        "SELECT * FROM mv_jukyu_notification_outbox ORDER BY risk_score DESC LIMIT 250"
    )
    summary = {
        "balanceRows": len(state.get("balanceRows") or []),
        "chainRows": len(state.get("chainRows") or []),
        "transportRows": len(state.get("transportRows") or []),
        "exposureRows": len(state.get("exposureRows") or []),
        "signalsInserted": int(state.get("signalsInserted") or 0),
        "outboxRows": len(rows),
        "pregelIter": int(state.get("pregelIter") or 0),
        "pregelMaxDelta": round(float(state.get("pregelMaxDelta") or 0.0), 6),
        "pregelSupersteps": state.get("pregelSupersteps") or [],
    }
    _insert_run(state, "completed", summary)
    return {"outboxRows": rows, "ok": True, "error": None}


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(JukyuState)
    builder.add_node("init_run", init_run)
    builder.add_node("read_balance", read_balance)
    builder.add_node("read_chain", read_chain)
    builder.add_node("read_transport_context", read_transport_context)
    builder.add_node("propagate", propagate)
    builder.add_node("write_signals", write_signals)
    builder.add_node("read_outbox", read_outbox)

    builder.set_entry_point("init_run")
    builder.add_edge("init_run", "read_balance")
    builder.add_edge("read_balance", "read_chain")
    builder.add_edge("read_chain", "read_transport_context")
    builder.add_edge("read_transport_context", "propagate")
    builder.add_conditional_edges(
        "propagate",
        should_continue,
        {"propagate": "propagate", "write_signals": "write_signals"},
    )
    builder.add_edge("write_signals", "read_outbox")
    builder.add_edge("read_outbox", END)
    return builder.compile()
