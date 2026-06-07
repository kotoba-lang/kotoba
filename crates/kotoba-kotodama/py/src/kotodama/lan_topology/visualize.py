"""Topology → Mermaid + text report.

Mermaid output groups hosts by the (interface, gateway_mac) tuple so that
two routers sharing the same gateway IP render as distinct clusters.
"""

from __future__ import annotations

from typing import Any


def render_mermaid(topology: dict[str, Any]) -> str:
    lines = ["graph TD", "  classDef router fill:#fde,stroke:#c33,stroke-width:2px;",
             "  classDef self fill:#def,stroke:#36c,stroke-width:2px;",
             "  classDef host fill:#fff,stroke:#999;"]
    cluster_ids: dict[tuple[str, str], str] = {}
    for idx, scan in enumerate(topology.get("scans", [])):
        iface = scan["iface"]
        gw_mac = scan.get("gateway_mac") or "no-gw"
        cluster_key = (iface["name"], gw_mac)
        cluster_id = f"seg{idx}"
        cluster_ids[cluster_key] = cluster_id
        medium = iface.get("medium", "?")
        label = f"{iface['name']} ({medium})<br/>self={iface['ip']}<br/>gw_mac={gw_mac[:17] or 'none'}"
        lines.append(f"  subgraph {cluster_id}[\"{label}\"]")
        self_id = f"{cluster_id}_self"
        lines.append(f"    {self_id}([\"self {iface['ip']}\"])")
        lines.append(f"    class {self_id} self")
        for h_idx, h in enumerate(scan.get("hosts", [])):
            if h["ip"] == iface["ip"]:
                continue
            hid = f"{cluster_id}_h{h_idx}"
            node_label = f"{h['ip']}<br/>{h['mac']}<br/>{h.get('oui_hint','')}"
            lines.append(f"    {hid}[\"{node_label}\"]")
            if h["mac"] == scan.get("gateway_mac"):
                lines.append(f"    class {hid} router")
            else:
                lines.append(f"    class {hid} host")
        lines.append("  end")
    for finding in topology.get("findings", []):
        # mermaid line break-safe
        f = finding.replace('"', "'").replace("\n", " ")
        lines.append(f"  %% finding: {f}")
    return "\n".join(lines)


def render_text_report(topology: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("=== LAN Topology Report ===")
    for scan in topology.get("scans", []):
        iface = scan["iface"]
        out.append("")
        out.append(
            f"[{iface['name']}] medium={iface.get('medium','?')} "
            f"ip={iface['ip']}/{iface['netmask']} mac={iface['mac']} "
            f"gw_mac={scan.get('gateway_mac','-')}"
        )
        hosts = scan.get("hosts", [])
        out.append(f"  {len(hosts)} host(s) visible:")
        for h in sorted(hosts, key=lambda x: tuple(int(p) for p in x["ip"].split("."))):
            out.append(f"    {h['ip']:<16} {h['mac']:<18} {h.get('oui_hint','')}")
    out.append("")
    out.append("=== Findings ===")
    findings = topology.get("findings") or []
    if not findings:
        out.append("  (none — network looks healthy / single L2)")
    for f in findings:
        out.append(f"  • {f}")
    return "\n".join(out)
