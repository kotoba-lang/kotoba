"""End-to-end orchestrator: LAN topology + host inventory under one scan_id."""

from __future__ import annotations

import socket
import uuid
from datetime import datetime
from typing import Any

from kotodama import db_sync


async def run_and_persist_all(
    *,
    owner_did: str | None = None,
    host_did: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Run network scan + host inventory together, persist both.

    Returns dict with `scan_id`, `lan`, `inventory`, `device_vid`.
    """
    from kotodama.lan_topology import run_lan_topology
    from kotodama.lan_topology.persist import persist_topology
    from kotodama.host_inventory.graph import run_host_inventory
    from kotodama.host_inventory.persist import persist_host_inventory

    scan_id = uuid.uuid4().hex
    lan = await run_lan_topology()
    inv = await run_host_inventory()

    device_vid = None
    if persist:
        persist_topology(
            lan,
            scan_id=scan_id,
            owner_did=owner_did,
            host_did=host_did,
            host_hostname=socket.gethostname(),
        )
        device_vid = persist_host_inventory(
            inv, scan_id=scan_id, owner_did=owner_did
        )
        _link_device_to_interfaces(scan_id, device_vid, lan, owner_did=owner_did)

    return {
        "scan_id": scan_id,
        "device_vid": device_vid,
        "lan": lan,
        "inventory_counts": {
            "disks": len(inv.get("disks") or []),
            "displays": len(inv.get("displays") or []),
            "installed_apps": len(inv.get("installed_apps") or []),
            "processes": len(inv.get("processes") or []),
            "launchitems": len(inv.get("launchitems") or []),
            "has_battery": inv.get("battery") is not None,
        },
    }


def _link_device_to_interfaces(
    scan_id: str,
    device_vid: str,
    lan: dict[str, Any],
    *,
    owner_did: str | None,
) -> None:
    today = datetime.utcnow().date()
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for s in lan.get("scans") or []:
        iface = s["iface"]
        iface_vid = f"network:iface:{scan_id}:{iface['name']}"
        db_sync.execute(
            """
            INSERT INTO edge_device_has_interface (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, iface_name, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                f"edge:dev-iface:{scan_id}:{iface['name']}",
                device_vid, iface_vid, today, 100, owner_did,
                scan_id, iface["name"], created_at,
            ),
        )
