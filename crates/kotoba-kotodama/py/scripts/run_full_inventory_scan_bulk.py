"""Bulk-insert driver. ~100x faster than the per-row script."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kotodama.lan_topology import run_lan_topology
from kotodama.host_inventory.graph import run_host_inventory
from kotodama.host_inventory.bulk_persist import bulk_persist_all
from kotodama.host_inventory.sharemouse import (
    persist_sharemouse_config,
    persist_sharemouse_screenshots,
)


async def main() -> int:
    scan_id = os.environ.get("SCAN_ID") or uuid.uuid4().hex
    owner_did = os.environ.get("OWNER_DID") or None

    t0 = time.time()
    print(f"scan_id      = {scan_id}", flush=True)

    print("→ LAN scan...", flush=True)
    lan = await run_lan_topology()
    print(f"  interfaces={len(lan['scans'])} findings={len(lan.get('findings') or [])} t={time.time()-t0:.1f}s", flush=True)
    for f in lan.get("findings") or []:
        print(f"    • {f}", flush=True)

    print("→ host inventory...", flush=True)
    inv = await run_host_inventory()
    print(f"  disks={len(inv.get('disks') or [])} apps={len(inv.get('installed_apps') or [])} procs={len(inv.get('processes') or [])} launchitems={len(inv.get('launchitems') or [])} t={time.time()-t0:.1f}s", flush=True)

    print("→ bulk persist...", flush=True)
    res = bulk_persist_all(scan_id=scan_id, lan=lan, inventory=inv, owner_did=owner_did)
    device_vid = res["device_vid"]
    print(f"  device_vid = {device_vid}", flush=True)
    for table, n in res["counts"].items():
        if n:
            print(f"  {table:<35} {n:>5}", flush=True)
    print(f"  bulk persist done t={time.time()-t0:.1f}s", flush=True)

    print("→ ShareMouse config + screenshots...", flush=True)
    cfg = persist_sharemouse_config(scan_id=scan_id, device_vid=device_vid, owner_did=owner_did)
    print(f"  app_vid={cfg['app_vid']}", flush=True)
    print(f"  snapshot_vid={cfg['snapshot_vid']}", flush=True)
    screens = persist_sharemouse_screenshots(
        scan_id=scan_id, device_vid=device_vid, app_vid=cfg["app_vid"],
        owner_did=owner_did,
    )
    for s in screens:
        print(f"  screenshot {s['screenshot_vid']} cid={s['cid']}", flush=True)

    print(f"\n=== complete in {time.time()-t0:.1f}s ===", flush=True)
    print(f"scan_id    = {scan_id}", flush=True)
    print(f"device_vid = {device_vid}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
