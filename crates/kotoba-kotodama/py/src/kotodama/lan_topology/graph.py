"""LangGraph workflow for LAN topology detection.

Nodes
-----
1. enumerate_interfaces  — list active IPv4 interfaces
2. scan_interfaces       — concurrent ARP sweep per IF
3. detect_split          — flag dual-router / split-L2 conditions
4. emit_visualization    — mermaid + text report

State flows linearly; failures degrade gracefully (empty hosts ≠ error).
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from .scanner import (
    Interface,
    ScanResult,
    list_interfaces,
    scan_all_async,
    scanresult_to_dict,
)
from .visualize import render_mermaid, render_text_report


class LanState(TypedDict, total=False):
    requested_ifaces: list[str]
    interfaces: list[dict[str, Any]]
    scans: list[dict[str, Any]]
    findings: list[str]
    mermaid: str
    report: str
    error: str


def enumerate_interfaces_node(state: LanState) -> dict:
    requested = state.get("requested_ifaces") or []
    ifs = list_interfaces()
    if requested:
        ifs = [i for i in ifs if i.name in requested]
    active = [i for i in ifs if i.is_active and i.ip]
    return {"interfaces": [vars(i) for i in active]}


async def scan_interfaces_node(state: LanState) -> dict:
    raws = state.get("interfaces") or []
    ifs = [Interface(**r) for r in raws]
    if not ifs:
        return {"scans": [], "error": "no active interfaces"}
    results = await scan_all_async(ifs)
    return {"scans": [scanresult_to_dict(r) for r in results]}


def detect_split_node(state: LanState) -> dict:
    scans = state.get("scans") or []
    findings: list[str] = []

    # Pairwise compare gateway MAC per identical gateway IP.
    gw_by_iface = {s["iface"]["name"]: s.get("gateway_mac", "") for s in scans}
    gw_macs = {mac for mac in gw_by_iface.values() if mac}
    if len(gw_macs) > 1:
        findings.append(
            f"Split-L2 detected: gateway has {len(gw_macs)} distinct MACs across interfaces "
            f"({', '.join(f'{k}={v}' for k, v in gw_by_iface.items() if v)}). "
            "Likely two independent routers sharing the same private subnet."
        )

    # IP collision across interfaces (same IP, different MAC).
    ip_to_macs: dict[str, set[tuple[str, str]]] = {}
    for s in scans:
        ifn = s["iface"]["name"]
        for h in s.get("hosts", []):
            ip_to_macs.setdefault(h["ip"], set()).add((ifn, h["mac"]))
    for ip, pairs in ip_to_macs.items():
        macs = {m for _, m in pairs}
        if len(macs) > 1:
            findings.append(
                f"IP collision at {ip}: " + ", ".join(f"{ifn}→{m}" for ifn, m in pairs)
            )

    # Asymmetric visibility (host count delta > 50%).
    counts = [(s["iface"]["name"], len(s.get("hosts", []))) for s in scans]
    if len(counts) >= 2:
        counts_sorted = sorted(counts, key=lambda x: x[1])
        lo_name, lo = counts_sorted[0]
        hi_name, hi = counts_sorted[-1]
        if hi > 0 and lo < hi * 0.5:
            findings.append(
                f"Asymmetric visibility: {hi_name} sees {hi} hosts, {lo_name} sees {lo} — "
                "broadcast traffic is not crossing between segments."
            )

    return {"findings": findings}


def emit_visualization_node(state: LanState) -> dict:
    scans = state.get("scans") or []
    findings = state.get("findings") or []
    topology = {"scans": scans, "findings": findings}
    return {
        "mermaid": render_mermaid(topology),
        "report": render_text_report(topology),
    }


def build_lan_topology_graph():
    g = StateGraph(LanState)
    g.add_node("enumerate_interfaces", enumerate_interfaces_node)
    g.add_node("scan_interfaces", scan_interfaces_node)
    g.add_node("detect_split", detect_split_node)
    g.add_node("emit_visualization", emit_visualization_node)
    g.set_entry_point("enumerate_interfaces")
    g.add_edge("enumerate_interfaces", "scan_interfaces")
    g.add_edge("scan_interfaces", "detect_split")
    g.add_edge("detect_split", "emit_visualization")
    g.add_edge("emit_visualization", END)
    return g.compile()


async def run_lan_topology(ifaces: list[str] | None = None) -> dict:
    """Public entrypoint. `ifaces=None` means all active IPv4 interfaces."""
    graph = build_lan_topology_graph()
    initial: LanState = {"requested_ifaces": ifaces or []}
    return await graph.ainvoke(initial)
