"""Persist host_inventory result into RisingWave."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Any

from kotodama import db_sync


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today() -> date:
    return datetime.utcnow().date()


def _vid_device(uuid_or_serial: str) -> str:
    return f"device:{uuid_or_serial or 'unknown'}"


def _vid_snapshot(scan_id: str, device_vid: str) -> str:
    return f"device_snapshot:{scan_id}:{device_vid}"


def _vid_disk(scan_id: str, device_vid: str, bsd: str) -> str:
    return f"device_disk:{scan_id}:{device_vid}:{bsd}"


def _vid_battery(scan_id: str, device_vid: str) -> str:
    return f"device_battery:{scan_id}:{device_vid}"


def _vid_display(scan_id: str, device_vid: str, idx: int) -> str:
    return f"device_display:{scan_id}:{device_vid}:{idx}"


def _vid_app(bundle_id: str) -> str:
    return f"app:{bundle_id}"


def _vid_app_install(scan_id: str, device_vid: str, bundle_id: str) -> str:
    return f"app_install:{scan_id}:{device_vid}:{bundle_id}"


def _vid_process(scan_id: str, device_vid: str, pid: int) -> str:
    return f"process:{scan_id}:{device_vid}:{pid}"


def _vid_launchitem(scan_id: str, device_vid: str, label: str) -> str:
    return f"launchitem:{scan_id}:{device_vid}:{label}"


def _eid(*parts: str) -> str:
    return "edge:" + ":".join(parts)


def persist_host_inventory(
    inv: dict[str, Any],
    *,
    scan_id: str,
    owner_did: str | None = None,
) -> str:
    """Write a host_inventory result tied to `scan_id`. Returns device_vid."""
    created_at = _now_iso()
    today = _today()
    dev = inv.get("device") or {}
    identity = dev.get("identity") or {}
    snapshot = dev.get("snapshot") or {}

    device_key = identity.get("hardware_uuid") or identity.get("serial_number") or identity.get("hostname") or "unknown"
    device_vid = _vid_device(device_key)

    # ── vertex_device (UPSERT-by-DELETE-then-INSERT — RW lacks ON CONFLICT) ──
    db_sync.execute("DELETE FROM vertex_device WHERE vertex_id = %s", (device_vid,))
    db_sync.execute(
        """
        INSERT INTO vertex_device (
          vertex_id, created_date, sensitivity_ord, owner_did,
          hardware_uuid, serial_number, hostname, device_kind,
          model_name, model_identifier, chip_arch, cpu_brand,
          cpu_cores, cpu_threads, memory_gb, storage_gb,
          os_name, os_version, os_build,
          first_seen_at, last_seen_at, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            device_vid, today, 100, owner_did,
            identity.get("hardware_uuid"), identity.get("serial_number"),
            identity.get("hostname"), identity.get("device_kind"),
            identity.get("model_name"), identity.get("model_identifier"),
            identity.get("chip_arch"), identity.get("cpu_brand"),
            identity.get("cpu_cores"), identity.get("cpu_threads"),
            identity.get("memory_gb"), identity.get("storage_gb"),
            identity.get("os_name"), identity.get("os_version"), identity.get("os_build"),
            created_at, created_at, created_at,
        ),
    )

    # ── vertex_device_snapshot ───────────────────────────────────────
    snap_vid = _vid_snapshot(scan_id, device_vid)
    db_sync.execute(
        """
        INSERT INTO vertex_device_snapshot (
          vertex_id, created_date, sensitivity_ord, owner_did,
          scan_id, device_vid, snapshot_at,
          boot_time, uptime_seconds,
          cpu_usage_x100, memory_used_mb, memory_free_mb, swap_used_mb,
          load_1m_x100, load_5m_x100, load_15m_x100,
          process_count, thread_count, thermal_state, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            snap_vid, today, 100, owner_did,
            scan_id, device_vid, created_at,
            snapshot.get("boot_time"), snapshot.get("uptime_seconds"),
            snapshot.get("cpu_usage_x100"), snapshot.get("memory_used_mb"),
            snapshot.get("memory_free_mb"), snapshot.get("swap_used_mb"),
            snapshot.get("load_1m_x100"), snapshot.get("load_5m_x100"),
            snapshot.get("load_15m_x100"),
            snapshot.get("process_count"), snapshot.get("thread_count"),
            snapshot.get("thermal_state"), created_at,
        ),
    )

    # edge_scan_observed_device
    db_sync.execute(
        """
        INSERT INTO edge_scan_observed_device (
          edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
          owner_did, scan_id, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            _eid("scan-device", scan_id, device_vid),
            f"network:scan:{scan_id}", device_vid, today, 100, owner_did,
            scan_id, created_at,
        ),
    )

    # ── disks ─────────────────────────────────────────────────────────
    for d in inv.get("disks") or []:
        disk_vid = _vid_disk(scan_id, device_vid, d["bsd_name"])
        db_sync.execute(
            """
            INSERT INTO vertex_device_disk (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, bsd_name, mount_point, fs_type,
              size_gb, used_gb, available_gb, use_pct_x100,
              is_internal, is_encrypted, is_removable, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                disk_vid, today, 100, owner_did,
                scan_id, device_vid, d["bsd_name"], d.get("mount_point"),
                d.get("fs_type"), d.get("size_gb"), d.get("used_gb"),
                d.get("available_gb"), d.get("use_pct_x100"),
                bool(d.get("is_internal")), bool(d.get("is_encrypted")),
                bool(d.get("is_removable")), created_at,
            ),
        )
        db_sync.execute(
            """
            INSERT INTO edge_device_has_disk (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _eid("dev-disk", scan_id, device_vid, d["bsd_name"]),
                device_vid, disk_vid, today, 100, owner_did, scan_id, created_at,
            ),
        )

    # ── battery (laptops only) ───────────────────────────────────────
    batt = inv.get("battery")
    if batt:
        db_sync.execute(
            """
            INSERT INTO vertex_device_battery (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, charge_pct, cycle_count, condition,
              is_charging, is_plugged, max_capacity_pct,
              design_capacity_mah, current_capacity_mah,
              voltage_mv, amperage_ma, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _vid_battery(scan_id, device_vid), today, 100, owner_did,
                scan_id, device_vid, batt.get("charge_pct"), batt.get("cycle_count"),
                batt.get("condition"), batt.get("is_charging"), batt.get("is_plugged"),
                batt.get("max_capacity_pct"), batt.get("design_capacity_mah"),
                batt.get("current_capacity_mah"), batt.get("voltage_mv"),
                batt.get("amperage_ma"), created_at,
            ),
        )

    # ── displays ─────────────────────────────────────────────────────
    for idx, disp in enumerate(inv.get("displays") or []):
        db_sync.execute(
            """
            INSERT INTO vertex_device_display (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, display_name, vendor_id, product_id,
              resolution_w, resolution_h, refresh_hz, pixel_depth_bits,
              is_main, is_builtin, is_mirrored, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _vid_display(scan_id, device_vid, idx), today, 100, owner_did,
                scan_id, device_vid, disp.get("display_name"),
                disp.get("vendor_id"), disp.get("product_id"),
                disp.get("resolution_w"), disp.get("resolution_h"),
                disp.get("refresh_hz"), disp.get("pixel_depth_bits"),
                bool(disp.get("is_main")), bool(disp.get("is_builtin")),
                bool(disp.get("is_mirrored")), created_at,
            ),
        )

    # ── installed apps + edges ───────────────────────────────────────
    bundle_to_app_vid: dict[str, str] = {}
    for a in inv.get("installed_apps") or []:
        bundle_id = a["bundle_id"]
        app_vid = _vid_app(bundle_id)
        bundle_to_app_vid[bundle_id] = app_vid

        # upsert vertex_app_installed
        db_sync.execute("DELETE FROM vertex_app_installed WHERE vertex_id = %s", (app_vid,))
        db_sync.execute(
            """
            INSERT INTO vertex_app_installed (
              vertex_id, created_date, sensitivity_ord, owner_did,
              bundle_id, app_name, vendor, category, install_kind,
              first_seen_at, last_seen_at, latest_version, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                app_vid, today, 100, owner_did,
                bundle_id, a.get("app_name"), a.get("vendor"), a.get("category"),
                a.get("install_kind"), created_at, created_at,
                a.get("short_version") or a.get("version"), created_at,
            ),
        )

        install_vid = _vid_app_install(scan_id, device_vid, bundle_id)
        db_sync.execute(
            """
            INSERT INTO vertex_app_installation (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, app_vid, bundle_id, app_name,
              version, short_version, app_path, size_mb,
              install_date, last_modified,
              signature_authority, obtained_from, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                install_vid, today, 100, owner_did,
                scan_id, device_vid, app_vid, bundle_id, a.get("app_name"),
                a.get("version"), a.get("short_version"), a.get("app_path"),
                a.get("size_mb"), a.get("install_date"), a.get("last_modified"),
                a.get("signature_authority"), a.get("obtained_from"), created_at,
            ),
        )

        db_sync.execute(
            """
            INSERT INTO edge_device_has_app_installed (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, bundle_id, version, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _eid("dev-app", scan_id, device_vid, bundle_id),
                device_vid, app_vid, today, 100, owner_did,
                scan_id, bundle_id, a.get("short_version") or a.get("version"),
                created_at,
            ),
        )

    # ── processes + edges ────────────────────────────────────────────
    for p in inv.get("processes") or []:
        proc_vid = _vid_process(scan_id, device_vid, p["pid"])
        app_vid = bundle_to_app_vid.get(p.get("bundle_id") or "", None)
        db_sync.execute(
            """
            INSERT INTO vertex_app_process (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, pid, ppid, process_name, command,
              user_name, cpu_pct_x100, memory_pct_x100, rss_kb, vsz_kb,
              started_at, elapsed_seconds, bundle_id, app_vid, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                proc_vid, today, 100, owner_did,
                scan_id, device_vid, p["pid"], p.get("ppid"),
                p.get("process_name"), p.get("command"), p.get("user_name"),
                p.get("cpu_pct_x100"), p.get("memory_pct_x100"),
                p.get("rss_kb"), p.get("vsz_kb"),
                p.get("started_at"), p.get("elapsed_seconds"),
                p.get("bundle_id") or None, app_vid, created_at,
            ),
        )
        db_sync.execute(
            """
            INSERT INTO edge_device_runs_process (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, pid, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _eid("dev-proc", scan_id, device_vid, str(p["pid"])),
                device_vid, proc_vid, today, 100, owner_did,
                scan_id, p["pid"], created_at,
            ),
        )
        if app_vid:
            db_sync.execute(
                """
                INSERT INTO edge_process_is_app (
                  edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
                  owner_did, scan_id, bundle_id, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    _eid("proc-app", scan_id, device_vid, str(p["pid"])),
                    proc_vid, app_vid, today, 100, owner_did,
                    scan_id, p.get("bundle_id"), created_at,
                ),
            )

    # ── launch items ─────────────────────────────────────────────────
    for li in inv.get("launchitems") or []:
        db_sync.execute(
            """
            INSERT INTO vertex_app_launchitem (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, label, plist_path, program,
              is_loaded, is_user, run_at_load, keep_alive, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _vid_launchitem(scan_id, device_vid, li["label"]),
                today, 100, owner_did, scan_id, device_vid,
                li["label"], li.get("plist_path"), li.get("program"),
                bool(li.get("is_loaded")), bool(li.get("is_user")),
                bool(li.get("run_at_load")), bool(li.get("keep_alive")),
                created_at,
            ),
        )

    return device_vid
