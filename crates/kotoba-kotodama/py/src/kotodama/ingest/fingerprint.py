"""
fingerprint — TLS/HTTP fingerprinting for shadow-level hosts.

Pulls domains from vertex_dns_observation + IPs from vertex_ip_address,
probes TLS handshake (cert subject/issuer/SANs/expiry/cipher) and
HTTP response headers via external proxy, writes results to vertex_scan_result.

Task type: netintel.fingerprint.delta
Env:
  SCAN_PROXY_URL — external probe service base URL (required; skips if absent)
  SCAN_PROXY_KEY — Bearer token for probe service (optional)
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
SOURCE_ID = "netintel-fingerprint"
_HTTPS_PORT = 443
_HTTP_PORT = 80
_TIMEOUT = 30


def _proxy_fingerprint(host: str, port: int, proxy_url: str, key: str) -> dict:
    url = proxy_url.rstrip("/") + "/fingerprint"
    payload = json.dumps({"host": host, "port": port}).encode()
    headers: dict = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        LOG.debug("proxy_fingerprint failed host=%s:%s: %s", host, port, e)
        return {}


def _stale_hosts(batch_size: int) -> list[str]:
    """Return domains that haven't been fingerprinted recently.

    # R0: This query requires Datalog for temporal filtering, distinct, order-by, and limit.
    """
    try:
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        # Note: The Datalog query expects named parameters, but kotoba_datomic.q accepts a tuple of args.
        # The args are substituted positionally for variables in the :in clause.
        # Since this query does not have an explicit :in clause, the variables are implicitly
        # bound by their usage in the :where clause and passed as a tuple.
        query_edn = f"""
            [:find (distinct ?domain)
             :where
             [?e :vertex.dns-observation/domain ?domain]
             [?e :vertex.dns-observation/observed-at ?observed-at]
             [(< ?observed-at "{thirty_days_ago}")] ; direct substitution for string literal
             :order-by [?observed-at :asc]
             :limit {int(batch_size)}]
        """
        results = get_kotoba_client().q(query_edn)
        return [row[0] for row in results if row and row[0]]
    except Exception as e:
        LOG.warning("stale_hosts_fingerprint query failed: %s", e)
        return []


def _insert_fingerprint(host: str, port: int, fp: dict, run_id: str) -> bool:
    ts = now_iso()
    proto = "tls" if port == _HTTPS_PORT else "tcp"
    vertex_id = (
        f"at://did:web:ingest.etzhayyim.com/com.etzhayyim.apps.collector.scanResult"
        f"/{host}:{port}:fp"
    )
    banner_raw = fp.get("banner", "") or fp.get("http_server", "")

    row_dict = {
        "vertex_id": vertex_id,
        "owner_did": INGEST_ACTOR,
        "ip": host,
        "port": int(port),
        "protocol": proto,
        "state": "open" if fp.get("open") else "filtered",
        "service": fp.get("service", "https" if port == _HTTPS_PORT else "http"),
        "software": fp.get("software", ""),
        "version": fp.get("version", ""),
        "banner": str(banner_raw)[:512],
        "tls_version": fp.get("tls_version", ""),
        "tls_cipher": fp.get("tls_cipher", ""),
        "cert_subject": str(fp.get("cert_subject", ""))[:512],
        "cert_issuer": str(fp.get("cert_issuer", ""))[:256],
        "cert_expires": fp.get("cert_expires", ""),
        "os_guess": "",
        "scanner_host": "proxy-fp",
        "scanned_at": ts,
        "sensitivity_ord": 1,
        "created_date": datetime.now(timezone.utc).date().isoformat(),
    }

    try:
        get_kotoba_client().insert_row("vertex_scan_result", row_dict)
        return True  # If insert_row succeeds without exception, it's considered successful
    except Exception as e:
        LOG.warning("fingerprint insert failed host=%s:%s: %s", host, port, e)
        return False


def ingest_fingerprint_delta(
    run_id: str = "",
    target_tier: str = "shadow",
    batch_size: int = 8,
) -> dict[str, Any]:
    proxy_url = os.environ.get("SCAN_PROXY_URL", "").strip()
    proxy_key = os.environ.get("SCAN_PROXY_KEY", "")
    if not proxy_url:
        LOG.warning("SCAN_PROXY_URL not set — fingerprint skipped")
        return {"ok": False, "error": "SCAN_PROXY_URL not configured",
                "hostsProbed": 0, "rowsWritten": 0}

    if not run_id:
        run_id = stable_run_id("netintel", SOURCE_ID, "delta")

    run = IngestRun(ingest_family="netintel", source_id=SOURCE_ID, run_id=run_id, status="running")
    upsert_run(run)

    hosts = _stale_hosts(batch_size)
    hosts_probed = len(hosts)
    rows_written = 0
    errors = 0

    for host in hosts:
        for port in (_HTTPS_PORT, _HTTP_PORT):
            try:
                fp = _proxy_fingerprint(host, port, proxy_url, proxy_key)
                if fp and _insert_fingerprint(host, port, fp, run_id):
                    rows_written += 1
            except Exception as e:
                LOG.warning("fingerprint failed host=%s port=%s: %s", host, port, e)
                errors += 1
        time.sleep(0.2)

    mark_run_finished(run_id, status="completed",
                      records_read=hosts_probed,
                      records_written=rows_written,
                      records_skipped=0,
                      error_count=errors)

    return {
        "ok": True,
        "runId": run_id,
        "hostsProbed": hosts_probed,
        "rowsWritten": rows_written,
        "errorCount": errors,
    }
