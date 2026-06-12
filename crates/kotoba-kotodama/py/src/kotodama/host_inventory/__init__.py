"""host_inventory — macOS device + app inventory collectors.

Companion to `kotodama.lan_topology`. Shares the `scan_id` so a single
scan produces a unified (network + device + app) snapshot.

Entry points
------------
- `collect_device()` — hardware + OS + per-snapshot state
- `collect_disks()` — `df -k` output normalized to disks
- `collect_battery()` — `pmset -g batt` parser (laptops only)
- `collect_displays()` — `system_profiler SPDisplaysDataType -json`
- `collect_installed_apps()` — scan /Applications + read Info.plist
- `collect_processes()` — `ps -axo ...` parsed
- `collect_launchitems()` — LaunchAgents + LaunchDaemons (loaded + on-disk)
- `run_host_inventory(scan_id)` — orchestrator returning everything
"""

from .device import (
    collect_device,
    collect_disks,
    collect_battery,
    collect_displays,
)
from .apps import (
    collect_installed_apps,
    collect_processes,
    collect_launchitems,
)
from .graph import run_host_inventory, build_host_inventory_graph
from .persist import persist_host_inventory
from .run import run_and_persist_all
from .blob import (
    compute_cidv1_raw_sha256,
    blob_from_path,
    blob_from_bytes,
    placeholder_blob_for,
    upsert_blob,
)
from .sharemouse import (
    persist_sharemouse_config,
    persist_sharemouse_screenshots,
    SHAREMOUSE_BUNDLE_ID,
    SHAREMOUSE_SETTINGS_v7_0_15,
    SHAREMOUSE_ACCEPTED_PEERS_v7_0_15,
)

__all__ = [
    "persist_host_inventory",
    "run_and_persist_all",
    "compute_cidv1_raw_sha256",
    "blob_from_path",
    "blob_from_bytes",
    "placeholder_blob_for",
    "upsert_blob",
    "persist_sharemouse_config",
    "persist_sharemouse_screenshots",
    "SHAREMOUSE_BUNDLE_ID",
    "SHAREMOUSE_SETTINGS_v7_0_15",
    "SHAREMOUSE_ACCEPTED_PEERS_v7_0_15",
    "collect_device",
    "collect_disks",
    "collect_battery",
    "collect_displays",
    "collect_installed_apps",
    "collect_processes",
    "collect_launchitems",
    "run_host_inventory",
    "build_host_inventory_graph",
]
