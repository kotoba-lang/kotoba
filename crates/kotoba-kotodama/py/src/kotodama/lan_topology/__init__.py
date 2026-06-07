"""lan_topology — local LAN scanner + langgraph workflow + visualizer.

Detects multi-router / split-L2 topologies by sweeping each active interface
independently and comparing ARP responses. Output is a mermaid diagram + a
structured topology dict suitable for further analysis.

Motivation
----------
Home / SOHO setups frequently have two boxes both NATing `192.168.1.0/24` (a
modem-router upstream and a Wi-Fi mesh node downstream wired as a separate
router instead of bridge). Symptoms — ShareMouse / mDNS / Bonjour failing
across wired ↔ Wi-Fi despite "same subnet" — look like a firewall issue but
are actually a broadcast-domain split.

Entry points
------------
- `run_lan_topology(ifaces=None)` — async langgraph entrypoint (full pipeline)
- `scan_once(iface)` — single-interface ARP sweep (sync)
- `render_mermaid(topology)` — diagram from topology dict
"""

from .scanner import scan_once, list_interfaces
from .graph import run_lan_topology, build_lan_topology_graph
from .visualize import render_mermaid, render_text_report
from .persist import persist_topology, run_and_persist

__all__ = [
    "scan_once",
    "list_interfaces",
    "run_lan_topology",
    "build_lan_topology_graph",
    "render_mermaid",
    "render_text_report",
    "persist_topology",
    "run_and_persist",
]
