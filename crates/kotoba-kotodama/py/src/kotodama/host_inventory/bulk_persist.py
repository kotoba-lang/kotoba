"""Batched persistence — uses psycopg2.extras.execute_values for ~100x speedup.

Per-row `db_sync.execute()` runs at ~150ms RTT JP→Vultr-LAX. With ~2000
INSERTs per full snapshot that's 5 minutes of round-trip wait. Batching
each table into a single execute_values call drops the total to seconds.
"""

from __future__ import annotations

import socket
import uuid
from datetime import datetime, date
from typing import Any, Iterable

import psycopg2.extras
from kotodama import db_sync


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today() -> date:
    return datetime.utcnow().date()


def _bulk_insert(cur, table: str, columns: list[str], rows: list[tuple]) -> int:
    if not rows:
        return 0
    placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES %s"
    psycopg2.extras.execute_values(cur, sql, rows, template=placeholders, page_size=200)
    return len(rows)


# ── scan IDs / vertex IDs ────────────────────────────────────────────────


def _vid_scan(scan_id):       return f"network:scan:{scan_id}"
def _vid_iface(scan_id, n):   return f"network:iface:{scan_id}:{n}"
def _vid_host(scan_id, n, ip): return f"network:host:{scan_id}:{n}:{ip}"
def _vid_segment(scan_id, sn, mac): return f"network:segment:{scan_id}:{sn}:{mac or 'no-gw'}"
def _vid_device(key):         return f"device:{key or 'unknown'}"
def _vid_dsnap(scan_id, dv):  return f"device_snapshot:{scan_id}:{dv}"
def _vid_disk(scan_id, dv, bsd): return f"device_disk:{scan_id}:{dv}:{bsd}"
def _vid_battery(scan_id, dv): return f"device_battery:{scan_id}:{dv}"
def _vid_display(scan_id, dv, i): return f"device_display:{scan_id}:{dv}:{i}"
def _vid_app(bid):            return f"app:{bid}"
def _vid_appinst(scan_id, dv, bid): return f"app_install:{scan_id}:{dv}:{bid}"
def _vid_proc(scan_id, dv, pid): return f"process:{scan_id}:{dv}:{pid}"
def _vid_li(scan_id, dv, label): return f"launchitem:{scan_id}:{dv}:{label}"


def _subnet_cidr(ip: str, netmask: str) -> str:
    import ipaddress
    try:
        return str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False))
    except Exception:
        return ""


def _prefix_len(netmask: str) -> int:
    import ipaddress
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}", strict=False).prefixlen
    except Exception:
        return 0


def _is_random_mac(mac: str) -> bool:
    return bool(mac) and len(mac) >= 2 and mac[1].lower() in {"2", "6", "a", "e"}


def bulk_persist_all(
    *,
    scan_id: str,
    lan: dict,
    inventory: dict,
    owner_did: str | None = None,
    host_did: str | None = None,
) -> dict[str, Any]:
    """One-shot batched persistence of an entire snapshot. Returns counts."""
    import os
    import psycopg2 as _pg
    conn = _pg.connect(os.environ.get("RW_URL") or os.environ.get("DATABASE_URL"))
    conn.autocommit = True
    cur = conn.cursor()

    counts: dict[str, int] = {}
    today = _today()
    now = _now_iso()
    hostname = socket.gethostname()

    scans = lan.get("scans") or []
    findings = lan.get("findings") or []

    # ── vertex_network_scan ───────────────────────────────────────────
    total_hosts = sum(len(s.get("hosts", [])) for s in scans)
    segments_map: dict[tuple[str, str], dict] = {}
    for s in scans:
        ifc = s["iface"]
        subnet = _subnet_cidr(ifc.get("ip", ""), ifc.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        key = (subnet, gw_mac)
        seg = segments_map.setdefault(key, {
            "subnet_cidr": subnet,
            "gateway_mac": gw_mac,
            "gateway_ip": "",
            "gateway_oui_hint": "",
            "iface_names": set(),
            "host_count": 0,
        })
        seg["iface_names"].add(ifc["name"])
        seg["host_count"] += len(s.get("hosts", []))
        for h in s.get("hosts", []):
            if h["mac"] == gw_mac and gw_mac:
                seg["gateway_ip"] = h["ip"]
                seg["gateway_oui_hint"] = h.get("oui_hint", "")
                break

    counts["vertex_network_scan"] = _bulk_insert(cur, "vertex_network_scan",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","host_did","host_hostname","scanned_at","iface_count","total_hosts","segment_count","finding_count","findings_text","created_at"],
        [(_vid_scan(scan_id), today, 100, owner_did, scan_id, host_did, hostname, now,
          len(scans), total_hosts, len(segments_map), len(findings),
          ("\n".join(findings)[:8000] if findings else None), now)])

    seg_rows = []
    for (subnet, gw_mac), seg in segments_map.items():
        seg_rows.append((
            _vid_segment(scan_id, subnet, gw_mac), today, 100, owner_did,
            scan_id, subnet, seg.get("gateway_ip") or None, gw_mac or None,
            seg.get("gateway_oui_hint") or None,
            ",".join(sorted(seg["iface_names"])),
            seg["host_count"], now,
        ))
    counts["vertex_network_segment"] = _bulk_insert(cur, "vertex_network_segment",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","subnet_cidr","gateway_ip","gateway_mac","gateway_oui_hint","iface_names","host_count","created_at"],
        seg_rows)

    iface_rows, edge_scan_iface_rows, edge_iface_seg_rows = [], [], []
    for s in scans:
        ifc = s["iface"]
        ivid = _vid_iface(scan_id, ifc["name"])
        subnet = _subnet_cidr(ifc.get("ip", ""), ifc.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        gw_ip = next((h["ip"] for h in s.get("hosts", []) if h["mac"] == gw_mac and gw_mac), "")
        iface_rows.append((
            ivid, today, 100, owner_did,
            scan_id, ifc["name"], ifc.get("ip"), ifc.get("netmask"),
            _prefix_len(ifc.get("netmask", "")), ifc.get("mac"),
            ifc.get("medium"), bool(ifc.get("is_active", True)),
            gw_ip or None, gw_mac or None, len(s.get("hosts", [])), now,
        ))
        edge_scan_iface_rows.append((
            f"edge:scan-iface:{scan_id}:{ifc['name']}",
            _vid_scan(scan_id), ivid, today, 100, owner_did, scan_id, now,
        ))
        edge_iface_seg_rows.append((
            f"edge:iface-seg:{scan_id}:{ifc['name']}",
            ivid, _vid_segment(scan_id, subnet, gw_mac), today, 100, owner_did, scan_id, now,
        ))
    counts["vertex_network_interface"] = _bulk_insert(cur, "vertex_network_interface",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","iface_name","ip","netmask","prefix_len","mac","medium","is_active","gateway_ip","gateway_mac","host_count","created_at"],
        iface_rows)
    counts["edge_scan_observed_interface"] = _bulk_insert(cur, "edge_scan_observed_interface",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","created_at"],
        edge_scan_iface_rows)
    counts["edge_interface_in_segment"] = _bulk_insert(cur, "edge_interface_in_segment",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","created_at"],
        edge_iface_seg_rows)

    host_rows, edge_host_seg_rows, edge_seg_gw_rows = [], [], []
    seen_seg_gw: set[str] = set()
    for s in scans:
        ifc = s["iface"]
        subnet = _subnet_cidr(ifc.get("ip", ""), ifc.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        seg_vid = _vid_segment(scan_id, subnet, gw_mac)
        self_ip = ifc.get("ip", "")
        for h in s.get("hosts", []):
            hvid = _vid_host(scan_id, ifc["name"], h["ip"])
            is_gw = bool(gw_mac) and h["mac"] == gw_mac
            host_rows.append((
                hvid, today, 100, owner_did,
                scan_id, ifc["name"], h["ip"], h["mac"], h.get("oui_hint"),
                is_gw, h["ip"] == self_ip, _is_random_mac(h["mac"]), now,
            ))
            edge_host_seg_rows.append((
                f"edge:host-seg:{scan_id}:{ifc['name']}:{h['ip']}",
                hvid, seg_vid, today, 100, owner_did,
                scan_id, h["ip"], h["mac"], now,
            ))
            if is_gw and seg_vid not in seen_seg_gw:
                edge_seg_gw_rows.append((
                    f"edge:seg-gw:{scan_id}:{seg_vid[-24:]}",
                    seg_vid, hvid, today, 100, owner_did,
                    scan_id, h["ip"], h["mac"], now,
                ))
                seen_seg_gw.add(seg_vid)

    counts["vertex_network_host"] = _bulk_insert(cur, "vertex_network_host",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","iface_name","ip","mac","oui_hint","is_gateway","is_self","is_random_mac","created_at"],
        host_rows)
    counts["edge_host_in_segment"] = _bulk_insert(cur, "edge_host_in_segment",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","ip","mac","created_at"],
        edge_host_seg_rows)
    counts["edge_segment_has_gateway"] = _bulk_insert(cur, "edge_segment_has_gateway",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","gateway_ip","gateway_mac","created_at"],
        edge_seg_gw_rows)

    # ── device + snapshot ─────────────────────────────────────────────
    dev = inventory.get("device") or {}
    identity = dev.get("identity") or {}
    snapshot = dev.get("snapshot") or {}
    device_key = identity.get("hardware_uuid") or identity.get("serial_number") or identity.get("hostname") or "unknown"
    device_vid = _vid_device(device_key)

    cur.execute("DELETE FROM vertex_device WHERE vertex_id = %s", (device_vid,))
    counts["vertex_device"] = _bulk_insert(cur, "vertex_device",
        ["vertex_id","created_date","sensitivity_ord","owner_did","hardware_uuid","serial_number","hostname","device_kind","model_name","model_identifier","chip_arch","cpu_brand","cpu_cores","cpu_threads","memory_gb","storage_gb","os_name","os_version","os_build","first_seen_at","last_seen_at","created_at"],
        [(device_vid, today, 100, owner_did,
          identity.get("hardware_uuid"), identity.get("serial_number"),
          identity.get("hostname"), identity.get("device_kind"),
          identity.get("model_name"), identity.get("model_identifier"),
          identity.get("chip_arch"), identity.get("cpu_brand"),
          identity.get("cpu_cores"), identity.get("cpu_threads"),
          identity.get("memory_gb"), identity.get("storage_gb"),
          identity.get("os_name"), identity.get("os_version"), identity.get("os_build"),
          now, now, now)])

    counts["vertex_device_snapshot"] = _bulk_insert(cur, "vertex_device_snapshot",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","snapshot_at","boot_time","uptime_seconds","cpu_usage_x100","memory_used_mb","memory_free_mb","swap_used_mb","load_1m_x100","load_5m_x100","load_15m_x100","process_count","thread_count","thermal_state","created_at"],
        [(_vid_dsnap(scan_id, device_vid), today, 100, owner_did,
          scan_id, device_vid, now,
          snapshot.get("boot_time"), snapshot.get("uptime_seconds"),
          snapshot.get("cpu_usage_x100"), snapshot.get("memory_used_mb"),
          snapshot.get("memory_free_mb"), snapshot.get("swap_used_mb"),
          snapshot.get("load_1m_x100"), snapshot.get("load_5m_x100"),
          snapshot.get("load_15m_x100"),
          snapshot.get("process_count"), snapshot.get("thread_count"),
          snapshot.get("thermal_state"), now)])

    counts["edge_scan_observed_device"] = _bulk_insert(cur, "edge_scan_observed_device",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","created_at"],
        [(f"edge:scan-device:{scan_id}", _vid_scan(scan_id), device_vid,
          today, 100, owner_did, scan_id, now)])

    # ── disks + edges ─────────────────────────────────────────────────
    disk_rows, edge_dev_disk_rows = [], []
    for d in inventory.get("disks") or []:
        dvid = _vid_disk(scan_id, device_vid, d["bsd_name"])
        disk_rows.append((
            dvid, today, 100, owner_did,
            scan_id, device_vid, d["bsd_name"], d.get("mount_point"),
            d.get("fs_type"), d.get("size_gb"), d.get("used_gb"),
            d.get("available_gb"), d.get("use_pct_x100"),
            bool(d.get("is_internal")), bool(d.get("is_encrypted")),
            bool(d.get("is_removable")), now,
        ))
        edge_dev_disk_rows.append((
            f"edge:dev-disk:{scan_id}:{device_vid[-12:]}:{d['bsd_name']}",
            device_vid, dvid, today, 100, owner_did, scan_id, now,
        ))
    counts["vertex_device_disk"] = _bulk_insert(cur, "vertex_device_disk",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","bsd_name","mount_point","fs_type","size_gb","used_gb","available_gb","use_pct_x100","is_internal","is_encrypted","is_removable","created_at"],
        disk_rows)
    counts["edge_device_has_disk"] = _bulk_insert(cur, "edge_device_has_disk",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","created_at"],
        edge_dev_disk_rows)

    # ── battery ───────────────────────────────────────────────────────
    batt = inventory.get("battery")
    if batt:
        counts["vertex_device_battery"] = _bulk_insert(cur, "vertex_device_battery",
            ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","charge_pct","cycle_count","condition","is_charging","is_plugged","max_capacity_pct","design_capacity_mah","current_capacity_mah","voltage_mv","amperage_ma","created_at"],
            [(_vid_battery(scan_id, device_vid), today, 100, owner_did,
              scan_id, device_vid, batt.get("charge_pct"), batt.get("cycle_count"),
              batt.get("condition"), batt.get("is_charging"), batt.get("is_plugged"),
              batt.get("max_capacity_pct"), batt.get("design_capacity_mah"),
              batt.get("current_capacity_mah"), batt.get("voltage_mv"),
              batt.get("amperage_ma"), now)])

    # ── displays ──────────────────────────────────────────────────────
    display_rows = []
    for idx, disp in enumerate(inventory.get("displays") or []):
        display_rows.append((
            _vid_display(scan_id, device_vid, idx), today, 100, owner_did,
            scan_id, device_vid, disp.get("display_name"),
            disp.get("vendor_id"), disp.get("product_id"),
            disp.get("resolution_w"), disp.get("resolution_h"),
            disp.get("refresh_hz"), disp.get("pixel_depth_bits"),
            bool(disp.get("is_main")), bool(disp.get("is_builtin")),
            bool(disp.get("is_mirrored")), now,
        ))
    counts["vertex_device_display"] = _bulk_insert(cur, "vertex_device_display",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","display_name","vendor_id","product_id","resolution_w","resolution_h","refresh_hz","pixel_depth_bits","is_main","is_builtin","is_mirrored","created_at"],
        display_rows)

    # ── installed apps + edges (no per-row DELETE: we re-INSERT all) ─
    bundle_to_app_vid = {}
    app_installed_rows, app_install_rows, edge_dev_app_rows = [], [], []
    for a in inventory.get("installed_apps") or []:
        bid = a["bundle_id"]
        app_vid = _vid_app(bid)
        bundle_to_app_vid[bid] = app_vid
        # Note: vertex_app_installed PK uniqueness is enforced by RW.
        # Since this is identity-keyed, we don't dedup mid-batch; let RW reject
        # duplicates via the PK. But execute_values would fail the whole batch
        # on conflict, so dedup here.
    seen_apps: set[str] = set()
    for a in inventory.get("installed_apps") or []:
        bid = a["bundle_id"]
        if bid in seen_apps:
            continue
        seen_apps.add(bid)
        # Delete-then-bulk-insert pattern for upsert across runs.
        cur.execute("DELETE FROM vertex_app_installed WHERE vertex_id = %s", (_vid_app(bid),))
        app_installed_rows.append((
            _vid_app(bid), today, 100, owner_did,
            bid, a.get("app_name"), a.get("vendor"), a.get("category"),
            a.get("install_kind"), now, now,
            a.get("short_version") or a.get("version"), now,
        ))
    counts["vertex_app_installed"] = _bulk_insert(cur, "vertex_app_installed",
        ["vertex_id","created_date","sensitivity_ord","owner_did","bundle_id","app_name","vendor","category","install_kind","first_seen_at","last_seen_at","latest_version","created_at"],
        app_installed_rows)

    for a in inventory.get("installed_apps") or []:
        bid = a["bundle_id"]
        ivid = _vid_appinst(scan_id, device_vid, bid)
        app_install_rows.append((
            ivid, today, 100, owner_did,
            scan_id, device_vid, _vid_app(bid), bid, a.get("app_name"),
            a.get("version"), a.get("short_version"), a.get("app_path"),
            a.get("size_mb"), a.get("install_date"), a.get("last_modified"),
            a.get("signature_authority"), a.get("obtained_from"), now,
        ))
        edge_dev_app_rows.append((
            f"edge:dev-app:{scan_id}:{device_vid[-12:]}:{bid[:60]}",
            device_vid, _vid_app(bid), today, 100, owner_did,
            scan_id, bid, a.get("short_version") or a.get("version"), now,
        ))
    counts["vertex_app_installation"] = _bulk_insert(cur, "vertex_app_installation",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","app_vid","bundle_id","app_name","version","short_version","app_path","size_mb","install_date","last_modified","signature_authority","obtained_from","created_at"],
        app_install_rows)
    counts["edge_device_has_app_installed"] = _bulk_insert(cur, "edge_device_has_app_installed",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","bundle_id","version","created_at"],
        edge_dev_app_rows)

    # ── processes + edges ─────────────────────────────────────────────
    proc_rows, edge_dev_proc_rows, edge_proc_app_rows = [], [], []
    for p in inventory.get("processes") or []:
        pvid = _vid_proc(scan_id, device_vid, p["pid"])
        bid = p.get("bundle_id") or None
        app_vid = bundle_to_app_vid.get(bid) if bid else None
        proc_rows.append((
            pvid, today, 100, owner_did,
            scan_id, device_vid, p["pid"], p.get("ppid"),
            p.get("process_name"), p.get("command"), p.get("user_name"),
            p.get("cpu_pct_x100"), p.get("memory_pct_x100"),
            p.get("rss_kb"), p.get("vsz_kb"),
            p.get("started_at"), p.get("elapsed_seconds"),
            bid, app_vid, now,
        ))
        edge_dev_proc_rows.append((
            f"edge:dev-proc:{scan_id}:{device_vid[-12:]}:{p['pid']}",
            device_vid, pvid, today, 100, owner_did, scan_id, p["pid"], now,
        ))
        if app_vid:
            edge_proc_app_rows.append((
                f"edge:proc-app:{scan_id}:{p['pid']}",
                pvid, app_vid, today, 100, owner_did, scan_id, bid, now,
            ))
    counts["vertex_app_process"] = _bulk_insert(cur, "vertex_app_process",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","pid","ppid","process_name","command","user_name","cpu_pct_x100","memory_pct_x100","rss_kb","vsz_kb","started_at","elapsed_seconds","bundle_id","app_vid","created_at"],
        proc_rows)
    counts["edge_device_runs_process"] = _bulk_insert(cur, "edge_device_runs_process",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","pid","created_at"],
        edge_dev_proc_rows)
    counts["edge_process_is_app"] = _bulk_insert(cur, "edge_process_is_app",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","bundle_id","created_at"],
        edge_proc_app_rows)

    # ── launch items ──────────────────────────────────────────────────
    li_rows = []
    seen_labels: set[str] = set()
    for li in inventory.get("launchitems") or []:
        label = li["label"]
        if label in seen_labels:
            continue
        seen_labels.add(label)
        li_rows.append((
            _vid_li(scan_id, device_vid, label), today, 100, owner_did,
            scan_id, device_vid, label, li.get("plist_path"), li.get("program"),
            bool(li.get("is_loaded")), bool(li.get("is_user")),
            bool(li.get("run_at_load")), bool(li.get("keep_alive")), now,
        ))
    counts["vertex_app_launchitem"] = _bulk_insert(cur, "vertex_app_launchitem",
        ["vertex_id","created_date","sensitivity_ord","owner_did","scan_id","device_vid","label","plist_path","program","is_loaded","is_user","run_at_load","keep_alive","created_at"],
        li_rows)

    # ── device → interface edges ──────────────────────────────────────
    edge_dev_iface_rows = []
    for s in scans:
        ifc = s["iface"]
        edge_dev_iface_rows.append((
            f"edge:dev-iface:{scan_id}:{ifc['name']}",
            device_vid, _vid_iface(scan_id, ifc["name"]),
            today, 100, owner_did, scan_id, ifc["name"], now,
        ))
    counts["edge_device_has_interface"] = _bulk_insert(cur, "edge_device_has_interface",
        ["edge_id","src_vid","dst_vid","created_date","sensitivity_ord","owner_did","scan_id","iface_name","created_at"],
        edge_dev_iface_rows)

    cur.close()
    return {"device_vid": device_vid, "counts": counts}
