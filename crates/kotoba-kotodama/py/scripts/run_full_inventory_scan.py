"""End-to-end driver: LAN scan + host inventory + ShareMouse config/screenshots → RW.

Usage:
    export DATABASE_URL="$(security find-generic-password -s etzhayyim.rw -a ROOT_URL -w)"
    python scripts/run_full_inventory_scan.py [--network-png PATH] [--clients-png PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kotodama.lan_topology import run_lan_topology, persist_topology
from kotodama.host_inventory import (
    run_host_inventory,
    persist_host_inventory,
    persist_sharemouse_config,
    persist_sharemouse_screenshots,
)
from kotodama.host_inventory.run import _link_device_to_interfaces


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--network-png", help="Local path to ShareMouse Preferences > Network tab screenshot")
    p.add_argument("--clients-png", help="Local path to ShareMouse Preferences > Clients tab screenshot")
    p.add_argument("--owner-did", default=None, help="owner_did for RLS")
    p.add_argument("--no-sharemouse", action="store_true", help="Skip ShareMouse-specific persistence")
    p.add_argument("--scan-id", default=None, help="Reuse a specific scan_id (default: generate UUID)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    scan_id = args.scan_id or uuid.uuid4().hex
    owner_did = args.owner_did

    print(f"scan_id      = {scan_id}")
    print(f"owner_did    = {owner_did}")

    print("→ running LAN topology scan...")
    lan = await run_lan_topology()
    findings = lan.get("findings") or []
    print(f"  interfaces={len(lan['scans'])}  findings={len(findings)}")
    for f in findings:
        print(f"    • {f}")

    print("→ running host inventory...")
    inv = await run_host_inventory()
    print(
        f"  disks={len(inv.get('disks') or [])} "
        f"displays={len(inv.get('displays') or [])} "
        f"battery={bool(inv.get('battery'))} "
        f"apps={len(inv.get('installed_apps') or [])} "
        f"procs={len(inv.get('processes') or [])} "
        f"launchitems={len(inv.get('launchitems') or [])}"
    )

    print("→ persisting LAN topology...")
    persist_topology(lan, scan_id=scan_id, owner_did=owner_did)

    print("→ persisting host inventory...")
    device_vid = persist_host_inventory(inv, scan_id=scan_id, owner_did=owner_did)
    print(f"  device_vid = {device_vid}")

    print("→ linking device → interfaces...")
    _link_device_to_interfaces(scan_id, device_vid, lan, owner_did=owner_did)

    sharemouse_results = None
    if not args.no_sharemouse:
        print("→ persisting ShareMouse config (preferences-pane screenshots)...")
        cfg = persist_sharemouse_config(
            scan_id=scan_id, device_vid=device_vid, owner_did=owner_did
        )
        print(f"  app_vid      = {cfg['app_vid']}")
        print(f"  snapshot_vid = {cfg['snapshot_vid']}")

        screenshots = persist_sharemouse_screenshots(
            scan_id=scan_id,
            device_vid=device_vid,
            app_vid=cfg["app_vid"],
            network_image_path=args.network_png,
            clients_image_path=args.clients_png,
            owner_did=owner_did,
        )
        sharemouse_results = {"config": cfg, "screenshots": screenshots}
        for s in screenshots:
            print(f"  screenshot   {s['screenshot_vid']}  cid={s['cid']}")

    print()
    print("=== persist complete ===")
    print(f"scan_id      = {scan_id}")
    print(f"device_vid   = {device_vid}")
    if sharemouse_results:
        print(f"sharemouse   = {sharemouse_results['config']['app_vid']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
