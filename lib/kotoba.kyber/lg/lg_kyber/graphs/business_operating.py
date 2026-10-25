"""kyber business_operating graph — deterministic business analysis orchestration.

Product-agnostic multi-analysis engine adapted for kyber (GL/AP/AR + HR + 在庫 ERP SaaS).
Mirrors yatabase's business_operating graph topology but with kyber-specific
BMC block keys and revenue model (Free/¥3,800/¥12,000/¥38,000/Enterprise).

State machine (linear):
    intake → bmc_topology → planner → kpi_causal → financial_flow
          → resource_allocation → scheduling → scenario_simulation
          → market_game → risk_constraint → synthesis → report → END

All nodes are pure functions (no I/O). Callers provide state via ainvoke().
"""

from __future__ import annotations

import heapq
import math
import time
from collections import defaultdict
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

AnalysisKind = Literal[
    "bmc",
    "kpi_causal",
    "financial_flow",
    "resource_allocation",
    "scheduling",
    "scenario_simulation",
    "market_game",
]

BMC_BLOCKS = [
    "customer_segments",
    "value_propositions",
    "channels",
    "customer_relationships",
    "revenue_streams",
    "key_resources",
    "key_activities",
    "key_partners",
    "cost_structure",
]

BMC_EDGES = [
    ("customer_segments", "value_propositions", "needs"),
    ("value_propositions", "channels", "delivered_by"),
    ("channels", "customer_relationships", "supports"),
    ("channels", "revenue_streams", "drives"),
    ("customer_relationships", "revenue_streams", "retains"),
    ("key_activities", "value_propositions", "produces"),
    ("key_resources", "key_activities", "enables"),
    ("key_partners", "key_activities", "supports"),
    ("cost_structure", "key_activities", "constrains"),
    ("revenue_streams", "key_resources", "funds"),
]


class BusinessOperatingState(TypedDict, total=False):
    company_profile: dict[str, Any]
    bmc: dict[str, Any]
    kpis: dict[str, Any]
    financials: dict[str, Any]
    constraints: dict[str, Any]
    market_signals: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    competitors: list[dict[str, Any]]
    requested_analyses: list[AnalysisKind]
    metrics_before: dict[str, Any]
    metrics_after: dict[str, Any]
    lift_evaluation: dict[str, Any]

    run_id: str
    started_at_ms: int
    bmc_graph: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    analysis_results: dict[str, Any]
    decisions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    report: dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _analysis_enabled(state: BusinessOperatingState, kind: AnalysisKind) -> bool:
    requested = state.get("requested_analyses") or []
    return not requested or kind in requested


def _append_result(state: BusinessOperatingState, key: str, value: dict[str, Any]) -> BusinessOperatingState:
    results = dict(state.get("analysis_results") or {})
    results[key] = value
    return {"analysis_results": results}  # type: ignore[return-value]


def intake(state: BusinessOperatingState) -> BusinessOperatingState:
    profile = state.get("company_profile") or {}
    if not profile.get("product"):
        profile = {
            **profile,
            "product": "kyber",
            "description": "GL/AP/AR + HR + 在庫 SaaS — 脱出できる ERP (AT Protocol data portability)",
            "revenue_model": "Free/¥3,800/¥12,000/¥38,000/Enterprise",
            "target_market": "Japan SMB, startups, manufacturing, farming co-ops, lawfirms",
        }
    return {
        "run_id": state.get("run_id") or f"kyber-bo-{_now_ms()}",
        "started_at_ms": state.get("started_at_ms") or _now_ms(),
        "company_profile": profile,
        "bmc": state.get("bmc") or {},
        "kpis": state.get("kpis") or {},
        "financials": state.get("financials") or {},
        "constraints": state.get("constraints") or {},
        "market_signals": state.get("market_signals") or [],
        "projects": state.get("projects") or [],
        "resources": state.get("resources") or [],
        "tasks": state.get("tasks") or [],
        "competitors": state.get("competitors") or [],
        "metrics_before": state.get("metrics_before") or {},
        "metrics_after": state.get("metrics_after") or {},
        "lift_evaluation": state.get("lift_evaluation") or {},
        "analysis_results": state.get("analysis_results") or {},
        "hypotheses": state.get("hypotheses") or [],
        "decisions": state.get("decisions") or [],
        "actions": state.get("actions") or [],
        "risks": state.get("risks") or [],
    }


def bmc_topology_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "bmc"):
        return {}
    canvas = state.get("bmc") or {}
    nodes: list[dict[str, Any]] = []
    for block in BMC_BLOCKS:
        content = canvas.get(block)
        weight = len(content) if isinstance(content, (list, dict)) else (1 if content else 0)
        nodes.append({"id": block, "kind": "bmc_block", "weight": weight, "filled": weight > 0})
    edges = [{"source": s, "target": t, "relation": r} for s, t, r in BMC_EDGES]
    missing = [n["id"] for n in nodes if not n["filled"]]
    centrality = _degree_centrality([n["id"] for n in nodes], [(e["source"], e["target"]) for e in edges])
    graph = {"nodes": nodes, "edges": edges, "missing_blocks": missing, "centrality": centrality}
    return {"bmc_graph": graph, **_append_result(state, "bmc", graph)}


def planner_agent_node(state: BusinessOperatingState) -> BusinessOperatingState:
    hypotheses = list(state.get("hypotheses") or [])
    bmc_graph = state.get("bmc_graph") or {}
    missing = bmc_graph.get("missing_blocks") or []
    kpis = state.get("kpis") or {}
    financials = state.get("financials") or {}

    if missing:
        hypotheses.append({
            "id": f"bmc-fill-{missing[0]}",
            "kind": "bmc",
            "statement": f"{missing[0]} is under-specified.",
            "confidence": 0.7,
        })

    retention = _safe_float(kpis.get("retention_30d"), math.nan)
    activation = _safe_float(kpis.get("activation_rate"), math.nan)
    if not math.isnan(retention) and not math.isnan(activation) and activation > retention:
        hypotheses.append({
            "id": "activation-retention-gap",
            "kind": "kpi_causal",
            "statement": "OSS→Cloud activation is not converting into 30-day retention.",
            "confidence": 0.64,
        })

    runway = _safe_float(financials.get("runway_months"), 999.0)
    if runway < 6:
        hypotheses.append({
            "id": "runway-pressure",
            "kind": "resource_allocation",
            "statement": "Runway below 6 months — prioritize Cloud MRR growth.",
            "confidence": 0.78,
        })

    return {"hypotheses": hypotheses}


def kpi_causal_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "kpi_causal"):
        return {}
    kpis = state.get("kpis") or {}
    signals = state.get("market_signals") or []
    candidates: list[dict[str, Any]] = []
    for name, value in kpis.items():
        current = _safe_float(value.get("current") if isinstance(value, dict) else value)
        target = _safe_float(value.get("target") if isinstance(value, dict) else current, current)
        gap = target - current
        if abs(gap) > 0:
            candidates.append({
                "effect": name,
                "gap": gap,
                "direction": "increase" if gap > 0 else "decrease",
                "candidate_causes": _candidate_causes(name, signals),
            })
    return _append_result(state, "kpi_causal", {"candidates": candidates})


def financial_flow_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "financial_flow"):
        return {}
    f = state.get("financials") or {}
    cash = _safe_float(f.get("cash"))
    monthly_revenue = _safe_float(f.get("monthly_revenue"))
    monthly_cost = _safe_float(f.get("monthly_cost"))
    burn = monthly_cost - monthly_revenue
    runway = cash / burn if burn > 0 else math.inf
    result = {
        "cash": cash,
        "monthly_revenue": monthly_revenue,
        "monthly_cost": monthly_cost,
        "burn": burn,
        "runway_months": runway if math.isfinite(runway) else None,
        "bottleneck": "cash" if burn > 0 and runway < 6 else "growth" if monthly_revenue <= 0 else "none",
    }
    return _append_result(state, "financial_flow", result)


def resource_allocation_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "resource_allocation"):
        return {}
    budget = _safe_float((state.get("constraints") or {}).get("budget"))
    projects = list(state.get("projects") or [])
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    total_cost = 0.0
    total_ev = 0.0
    ranked = sorted(projects, key=lambda p: (-_safe_float(p.get("expected_value")), _safe_float(p.get("cost"))))
    for p in ranked:
        cost = _safe_float(p.get("cost"))
        ev = _safe_float(p.get("expected_value"))
        pid = p.get("id") or p.get("name")
        if ev <= cost:
            rejected.append({"id": pid, "reason": "non_positive_net_value"})
            continue
        if budget > 0 and total_cost + cost <= budget:
            selected.append({"id": pid, "cost": cost, "expected_value": ev, "expected_net_value": ev - cost})
            total_cost += cost
            total_ev += ev
        else:
            rejected.append({"id": pid, "reason": "budget_exceeded" if budget > 0 else "no_budget"})
    result = {
        "selected": selected, "rejected": rejected,
        "total_cost": total_cost, "total_expected_value": total_ev,
        "expected_net_value": total_ev - total_cost,
    }
    return _append_result(state, "resource_allocation", result)


def scheduling_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "scheduling"):
        return {}
    tasks = list(state.get("tasks") or [])
    task_by_id = {str(t.get("id")): t for t in tasks if t.get("id") is not None}
    order, cycles = _topological_order(task_by_id)
    start = 0.0
    schedule: list[dict[str, Any]] = []
    for task_id in order:
        task = task_by_id[task_id]
        duration = max(_safe_float(task.get("duration_days"), 1.0), 0.0)
        schedule.append({"id": task_id, "start_day": start, "end_day": start + duration})
        start += duration
    return _append_result(state, "scheduling", {"schedule": schedule, "cycles": cycles, "makespan_days": start})


def scenario_simulation_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "scenario_simulation"):
        return {}
    f = state.get("financials") or {}
    revenue = _safe_float(f.get("monthly_revenue"))
    cost = _safe_float(f.get("monthly_cost"))
    scenarios = []
    for name, growth, cost_delta in [("base", 0.03, 0.00), ("upside", 0.08, 0.03), ("downside", -0.03, -0.02)]:
        rev = revenue
        cash_delta = 0.0
        for _ in range(12):
            rev *= 1 + growth
            cash_delta += rev - (cost * (1 + cost_delta))
        scenarios.append({"name": name, "revenue_month_12": rev, "cash_delta_12m": cash_delta})
    return _append_result(state, "scenario_simulation", {"scenarios": scenarios})


def market_game_node(state: BusinessOperatingState) -> BusinessOperatingState:
    if not _analysis_enabled(state, "market_game"):
        return {}
    competitors = state.get("competitors") or []
    own_price = _safe_float((state.get("financials") or {}).get("price"))
    comp_prices = [_safe_float(c.get("price")) for c in competitors if c.get("price") is not None]
    median = sorted(comp_prices)[len(comp_prices) // 2] if comp_prices else None
    if median is None or own_price <= 0:
        posture = "unknown"
    elif own_price < median * 0.8:
        posture = "undercut"
    elif own_price > median * 1.2:
        posture = "premium"
    else:
        posture = "parity"
    return _append_result(state, "market_game", {"posture": posture, "own_price": own_price or None, "median_competitor_price": median})


def risk_constraint_node(state: BusinessOperatingState) -> BusinessOperatingState:
    risks = list(state.get("risks") or [])
    results = state.get("analysis_results") or {}
    financial = results.get("financial_flow") or {}
    if (rw := financial.get("runway_months")) is not None and rw < 6:
        risks.append({"id": "short-runway", "severity": "high", "summary": "Runway below 6 months."})
    if (results.get("scheduling") or {}).get("cycles"):
        risks.append({"id": "dependency-cycle", "severity": "high", "summary": "Task dependency cycle."})
    if len((results.get("bmc") or {}).get("missing_blocks") or []) >= 3:
        risks.append({"id": "bmc-under-specified", "severity": "medium", "summary": "3+ BMC blocks empty."})
    return {"risks": risks}


def synthesis_agent_node(state: BusinessOperatingState) -> BusinessOperatingState:
    results = state.get("analysis_results") or {}
    decisions = list(state.get("decisions") or [])
    actions = list(state.get("actions") or [])
    allocation = results.get("resource_allocation") or {}
    selected = allocation.get("selected") or []
    if selected:
        decisions.append({
            "id": "fund-selected-projects", "type": "resource_allocation",
            "recommendation": "Fund selected projects within budget.",
            "project_ids": [p["id"] for p in selected],
        })
        actions.extend({"kind": "project_funding", "project_id": p["id"], "cost": p["cost"], "requires_human_approval": True} for p in selected)
    for candidate in (results.get("kpi_causal") or {}).get("candidates") or []:
        if abs(_safe_float(candidate.get("gap"))) > 0:
            actions.append({"kind": "causal_validation", "target_kpi": candidate["effect"], "requires_human_approval": False})
    if not decisions:
        decisions.append({"id": "continue-measurement", "type": "operating_cadence", "recommendation": "Continue measurement."})
    return {"decisions": decisions, "actions": actions}


def report_node(state: BusinessOperatingState) -> BusinessOperatingState:
    report = {
        "run_id": state.get("run_id"),
        "duration_ms": _now_ms() - int(state.get("started_at_ms") or _now_ms()),
        "product": (state.get("company_profile") or {}).get("product", "kyber"),
        "summary": {
            "hypotheses": len(state.get("hypotheses") or []),
            "analyses": sorted((state.get("analysis_results") or {}).keys()),
            "decisions": len(state.get("decisions") or []),
            "actions": len(state.get("actions") or []),
            "risks": len(state.get("risks") or []),
        },
        "decisions": state.get("decisions") or [],
        "actions": state.get("actions") or [],
        "risks": state.get("risks") or [],
    }
    return {"report": report}


def _degree_centrality(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, float]:
    if not nodes:
        return {}
    degree = {n: 0 for n in nodes}
    for s, t in edges:
        degree[s] = degree.get(s, 0) + 1
        degree[t] = degree.get(t, 0) + 1
    denom = max(len(nodes) - 1, 1)
    return {n: v / denom for n, v in degree.items()}


def _candidate_causes(kpi_name: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    causes = []
    name = kpi_name.lower()
    for signal in signals:
        text = f"{signal.get('name', '')} {signal.get('summary', '')}".lower()
        overlap = sum(1 for token in name.split("_") if token and token in text)
        if overlap:
            causes.append({"signal": signal.get("id") or signal.get("name"), "confidence": min(0.5 + overlap * 0.15, 0.9)})
    if not causes:
        causes.append({"signal": "needs_instrumentation", "confidence": 0.3})
    return causes


def _topological_order(task_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    indegree: dict[str, int] = {tid: 0 for tid in task_by_id}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for task_id, task in task_by_id.items():
        for dep in task.get("depends_on") or []:
            dep_id = str(dep)
            if dep_id in task_by_id:
                outgoing[dep_id].append(task_id)
                indegree[task_id] += 1
    ready = [tid for tid, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        tid = heapq.heappop(ready)
        order.append(tid)
        for nxt in outgoing[tid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, nxt)
    cycles = sorted(tid for tid, count in indegree.items() if count > 0)
    return order, cycles


def _build() -> Any:
    sg = StateGraph(BusinessOperatingState)
    sg.add_node("intake", intake)
    sg.add_node("bmc_topology", bmc_topology_node)
    sg.add_node("planner", planner_agent_node)
    sg.add_node("kpi_causal", kpi_causal_node)
    sg.add_node("financial_flow", financial_flow_node)
    sg.add_node("resource_allocation", resource_allocation_node)
    sg.add_node("scheduling", scheduling_node)
    sg.add_node("scenario_simulation", scenario_simulation_node)
    sg.add_node("market_game", market_game_node)
    sg.add_node("risk_constraint", risk_constraint_node)
    sg.add_node("synthesis", synthesis_agent_node)
    sg.add_node("report", report_node)
    sg.add_edge(START, "intake")
    sg.add_edge("intake", "bmc_topology")
    sg.add_edge("bmc_topology", "planner")
    sg.add_edge("planner", "kpi_causal")
    sg.add_edge("kpi_causal", "financial_flow")
    sg.add_edge("financial_flow", "resource_allocation")
    sg.add_edge("resource_allocation", "scheduling")
    sg.add_edge("scheduling", "scenario_simulation")
    sg.add_edge("scenario_simulation", "market_game")
    sg.add_edge("market_game", "risk_constraint")
    sg.add_edge("risk_constraint", "synthesis")
    sg.add_edge("synthesis", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
