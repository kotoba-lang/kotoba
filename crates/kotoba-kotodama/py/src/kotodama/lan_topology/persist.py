"""Persist `run_lan_topology` output into RisingWave.

Maps the langgraph state (`interfaces`, `scans`, `findings`) into the
vertex_network_* / edge_* schema declared by
`r_20260512100000_vertex_network_topology` and INSERTs through the
`kotodama.db_sync` psycopg pool.

The Python actor is the single writer for this schema. Worker / CF
isolates MUST NOT INSERT here per ADR-2605111200.
"""

from __future__ import annotations

import ipaddress
import socket
import uuid
from collections import defaultdict
from datetime import datetime, date
from typing import Any, Iterable

from kotodama import db_sync


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today() -> date:
    return datetime.utcnow().date()


def _vid_scan(scan_id: str) -> str:
    return f"network:scan:{scan_id}"


def _vid_iface(scan_id: str, iface: str) -> str:
    return f"network:iface:{scan_id}:{iface}"


def _vid_host(scan_id: str, iface: str, ip: str) -> str:
    return f"network:host:{scan_id}:{iface}:{ip}"


def _vid_segment(scan_id: str, subnet: str, gw_mac: str) -> str:
    return f"network:segment:{scan_id}:{subnet}:{gw_mac or 'no-gw'}"


def _eid(*parts: str) -> str:
    return "edge:" + ":".join(parts)


def _prefix_len(netmask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}", strict=False).prefixlen
    except (ValueError, TypeError):
        return 0


def _subnet_cidr(ip: str, netmask: str) -> str:
    try:
        return str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False))
    except (ValueError, TypeError):
        return ""


def _segments_from_scans(
    scan_id: str,
    scans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive (subnet, gateway_mac) → segment rows; collapse interfaces
    that share the same (subnet, gw_mac) into a single segment."""
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for s in scans:
        iface = s["iface"]
        subnet = _subnet_cidr(iface.get("ip", ""), iface.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        key = (subnet, gw_mac)
        gw_oui = ""
        for h in s.get("hosts", []):
            if h["mac"] == gw_mac:
                gw_oui = h.get("oui_hint", "")
                break
        entry = by_key.setdefault(
            key,
            {
                "subnet_cidr": subnet,
                "gateway_mac": gw_mac,
                "gateway_ip": "",
                "gateway_oui_hint": gw_oui,
                "iface_names": [],
                "host_count": 0,
            },
        )
        entry["iface_names"].append(iface["name"])
        entry["host_count"] += len(s.get("hosts", []))
        # Capture gateway IP from the gateway host row if present.
        if not entry["gateway_ip"]:
            for h in s.get("hosts", []):
                if h["mac"] == gw_mac and gw_mac:
                    entry["gateway_ip"] = h["ip"]
                    break

    return [
        {
            **v,
            "iface_names": ",".join(sorted(set(v["iface_names"]))),
            "vertex_id": _vid_segment(scan_id, v["subnet_cidr"], v["gateway_mac"]),
        }
        for v in by_key.values()
    ]


_RANDOM_MAC_NIBBLES = {"2", "6", "a", "e"}


def _is_random_mac(mac: str) -> bool:
    return bool(mac) and len(mac) >= 2 and mac[1].lower() in _RANDOM_MAC_NIBBLES


def persist_topology(
    result: dict[str, Any],
    *,
    scan_id: str | None = None,
    host_did: str | None = None,
    host_hostname: str | None = None,
    owner_did: str | None = None,
) -> str:
    """Write a `run_lan_topology` result into RisingWave.

    Returns the `scan_id` (generated if not provided).
    """
    scan_id = scan_id or uuid.uuid4().hex
    scanned_at = _now_iso()
    created_at = scanned_at
    today = _today()
    host_hostname = host_hostname or socket.gethostname()
    scans = result.get("scans") or []
    findings: list[str] = result.get("findings") or []

    # ── vertex_network_scan ────────────────────────────────────────────
    total_hosts = sum(len(s.get("hosts", [])) for s in scans)
    segments = _segments_from_scans(scan_id, scans)
    db_sync.execute(
        """
        INSERT INTO vertex_network_scan (
          vertex_id, created_date, sensitivity_ord, owner_did,
          scan_id, host_did, host_hostname, scanned_at,
          iface_count, total_hosts, segment_count, finding_count,
          findings_text, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            _vid_scan(scan_id),
            today,
            100,
            owner_did,
            scan_id,
            host_did,
            host_hostname,
            scanned_at,
            len(scans),
            total_hosts,
            len(segments),
            len(findings),
            "\n".join(findings)[:8000] if findings else None,
            created_at,
        ),
    )

    # ── vertex_network_segment ────────────────────────────────────────
    for seg in segments:
        db_sync.execute(
            """
            INSERT INTO vertex_network_segment (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, subnet_cidr, gateway_ip, gateway_mac,
              gateway_oui_hint, iface_names, host_count, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                seg["vertex_id"], today, 100, owner_did,
                scan_id, seg["subnet_cidr"], seg.get("gateway_ip") or None,
                seg["gateway_mac"] or None, seg.get("gateway_oui_hint") or None,
                seg["iface_names"], seg["host_count"], created_at,
            ),
        )

    # ── vertex_network_interface + edges scan→iface, iface→segment ────
    for s in scans:
        iface = s["iface"]
        iface_vid = _vid_iface(scan_id, iface["name"])
        subnet = _subnet_cidr(iface.get("ip", ""), iface.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        gw_ip = ""
        for h in s.get("hosts", []):
            if h["mac"] == gw_mac and gw_mac:
                gw_ip = h["ip"]
                break

        db_sync.execute(
            """
            INSERT INTO vertex_network_interface (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, iface_name, ip, netmask, prefix_len, mac,
              medium, is_active, gateway_ip, gateway_mac, host_count, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                iface_vid, today, 100, owner_did,
                scan_id, iface["name"], iface.get("ip"), iface.get("netmask"),
                _prefix_len(iface.get("netmask", "")), iface.get("mac"),
                iface.get("medium"), bool(iface.get("is_active", True)),
                gw_ip or None, gw_mac or None,
                len(s.get("hosts", [])), created_at,
            ),
        )

        db_sync.execute(
            """
            INSERT INTO edge_scan_observed_interface (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _eid("scan-iface", scan_id, iface["name"]),
                _vid_scan(scan_id), iface_vid, today, 100, owner_did,
                scan_id, created_at,
            ),
        )

        seg_vid = _vid_segment(scan_id, subnet, gw_mac)
        db_sync.execute(
            """
            INSERT INTO edge_interface_in_segment (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                _eid("iface-seg", scan_id, iface["name"]),
                iface_vid, seg_vid, today, 100, owner_did, scan_id, created_at,
            ),
        )

    # ── vertex_network_host + edges host→segment + segment→gateway ────
    seen_segment_gw: set[str] = set()
    for s in scans:
        iface = s["iface"]
        subnet = _subnet_cidr(iface.get("ip", ""), iface.get("netmask", ""))
        gw_mac = s.get("gateway_mac") or ""
        seg_vid = _vid_segment(scan_id, subnet, gw_mac)
        self_ip = iface.get("ip", "")

        for h in s.get("hosts", []):
            host_vid = _vid_host(scan_id, iface["name"], h["ip"])
            is_gw = bool(gw_mac) and h["mac"] == gw_mac
            db_sync.execute(
                """
                INSERT INTO vertex_network_host (
                  vertex_id, created_date, sensitivity_ord, owner_did,
                  scan_id, iface_name, ip, mac, oui_hint,
                  is_gateway, is_self, is_random_mac, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    host_vid, today, 100, owner_did,
                    scan_id, iface["name"], h["ip"], h["mac"], h.get("oui_hint"),
                    is_gw, h["ip"] == self_ip, _is_random_mac(h["mac"]),
                    created_at,
                ),
            )

            db_sync.execute(
                """
                INSERT INTO edge_host_in_segment (
                  edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
                  owner_did, scan_id, ip, mac, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    _eid("host-seg", scan_id, iface["name"], h["ip"]),
                    host_vid, seg_vid, today, 100, owner_did,
                    scan_id, h["ip"], h["mac"], created_at,
                ),
            )

            if is_gw and seg_vid not in seen_segment_gw:
                db_sync.execute(
                    """
                    INSERT INTO edge_segment_has_gateway (
                      edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
                      owner_did, scan_id, gateway_ip, gateway_mac, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        _eid("seg-gw", scan_id, seg_vid),
                        seg_vid, host_vid, today, 100, owner_did,
                        scan_id, h["ip"], h["mac"], created_at,
                    ),
                )
                seen_segment_gw.add(seg_vid)

    return scan_id


async def run_and_persist(
    ifaces: list[str] | None = None,
    *,
    owner_did: str | None = None,
    host_did: str | None = None,
) -> dict[str, Any]:
    """Convenience: run the langgraph workflow then persist.

    Returns a dict with `scan_id` plus the original langgraph output.
    """
    from .graph import run_lan_topology

    result = await run_lan_topology(ifaces=ifaces)
    scan_id = persist_topology(
        result,
        owner_did=owner_did,
        host_did=host_did,
    )
    return {"scan_id": scan_id, **result}
