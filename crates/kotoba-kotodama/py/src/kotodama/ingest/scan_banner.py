"""
scan_banner — port scan + banner grab for shadow-level IPs.

Pulls IPs from vertex_ip_address, submits scan jobs to an external proxy
service (SCAN_PROXY_URL), and writes results to vertex_scan_result.

Scanning is NEVER performed direct-socket from the Vultr VKE cluster to
avoid abuse reports. All traffic routes through SCAN_PROXY_URL.

Task type: netintel.scan.banner
Env:
  SCAN_PROXY_URL — external scan service base URL (required; skips if absent)
  SCAN_PROXY_KEY — Bearer token for scan service (optional)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from kotodama.ingest.core import (
    IngestRun,
    mark_run_finished,
    now_iso,
    stable_run_id,
    upsert_run,
)
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger(__name__)

INGEST_ACTOR = "did:web:ingest.etzhayyim.com"
SOURCE_ID = "netintel-scan"
_COMMON_PORTS = [21, 22, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995,
                 3306, 5432, 6379, 8080, 8443, 27017]
_TIMEOUT = 30


def _proxy_scan(ip: str, ports: list[int], proxy_url: str, key: str) -> list[dict]:
    url = proxy_url.rstrip("/") + "/scan"
    payload = json.dumps({"ip": ip, "ports": ports}).encode()
    headers: dict = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return data.get("results", []) if isinstance(data, dict) else []
    except Exception as e:
        LOG.debug("proxy_scan failed ip=%s: %s", ip, e)
        return []


def _stale_ips(batch_size: int) -> list[str]:
    # R0: Filtering by observed_at in Python as date arithmetic is not directly supported by the shims.
    try:
        # Fetch all IP addresses from vertex_ip_address
        all_ips = get_kotoba_client().select_where("vertex_ip_address", "pk", "*", columns=["address", "observed_at"], limit=2000)

        # Filter in Python
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        stale_ips_with_dates = [
            row for row in all_ips
            if row.get("observed_at") and datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")) < thirty_days_ago
        ]

        # Sort by observed_at and take the batch_size
        stale_ips_with_dates.sort(key=lambda x: x.get("observed_at", ""))

        return [row["address"] for row in stale_ips_with_dates[:batch_size] if row["address"]]
    except Exception as e:
        LOG.warning("stale_ips_scan query failed: %s", e)
        return []


def _insert_scan_result(ip: str, port: int, result: dict, run_id: str) -> bool:
    ts = now_iso()
    proto = result.get("protocol", "tcp")
    vertex_id = (
        f"at://did:web:ingest.etzhayyim.com/com.etzhayyim.apps.collector.scanResult"
        f"/{ip}:{port}:{proto}"
    )

    row_dict = {
        "vertex_id": vertex_id,
        "owner_did": INGEST_ACTOR,
        "ip": ip,
        "port": int(port),
        "protocol": proto,
        "state": result.get("state", ""),
        "service": result.get("service", ""),
        "software": result.get("software", ""),
        "version": result.get("version", ""),
        "banner": str(result.get("banner", ""))[:512],
        "tls_version": result.get("tls_version", ""),
        "tls_cipher": result.get("tls_cipher", ""),
        "cert_subject": result.get("cert_subject", ""),
        "cert_issuer": result.get("cert_issuer", ""),
        "cert_expires": result.get("cert_expires", ""),
        "os_guess": result.get("os_guess", ""),
        "scanner_host": "proxy",
        "scanned_at": ts,
        "sensitivity_ord": 1,
        "created_date": datetime.now(timezone.utc).date().isoformat(),
    }
    try:
        # insert_row handles upsert logic based on the identity column (vertex_id)
        get_kotoba_client().insert_row("vertex_scan_result", row_dict)
        return True
    except Exception as e:
        LOG.warning("scan_result insert failed ip=%s port=%s: %s", ip, port, e)
        return False


def ingest_scan_banner(
    run_id: str = "",
    target_tier: str = "shadow",
    batch_size: int = 8,
) -> dict[str, Any]:
    proxy_url = os.environ.get("SCAN_PROXY_URL", "").strip()
    proxy_key = os.environ.get("SCAN_PROXY_KEY", "")
    if not proxy_url:
        LOG.warning("SCAN_PROXY_URL not set — scan_banner skipped")
        return {"ok": False, "error": "SCAN_PROXY_URL not configured",
                "ipsScanned": 0, "rowsWritten": 0}

    if not run_id:
        run_id = stable_run_id("netintel", SOURCE_ID, "delta")

    run = IngestRun(ingest_family="netintel", source_id=SOURCE_ID, run_id=run_id, status="running")
    upsert_run(run)

    ips = _stale_ips(batch_size)
    ips_scanned = len(ips)
    rows_written = 0
    errors = 0

    for ip in ips:
        try:
            results = _proxy_scan(ip, _COMMON_PORTS, proxy_url, proxy_key)
            for r in results:
                port = int(r.get("port", 0))
                if port and _insert_scan_result(ip, port, r, run_id):
                    rows_written += 1
        except Exception as e:
            LOG.warning("scan_banner failed ip=%s: %s", ip, e)
            errors += 1
        time.sleep(0.2)

    mark_run_finished(run_id, status="completed",
                      records_read=ips_scanned,
                      records_written=rows_written,
                      records_skipped=0,
                      error_count=errors)

    return {
        "ok": True,
        "runId": run_id,
        "ipsScanned": ips_scanned,
        "rowsWritten": rows_written,
        "errorCount": errors,
    }
