"""
ip_enrich — GeoIP enrichment for shadow-level IP addresses.

Pulls IPs from vertex_ip_address that haven't been updated recently,
queries ipinfo.io (free tier, no key required for basic fields),
and writes enriched rows back.

Task type: netintel.ip.enrich
Env: IPINFO_TOKEN — optional ipinfo.io API token for higher rate limits
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.ingest.core import (
    IngestRun,
    mark_run_finished,
    now_iso,
    stable_run_id,
    upsert_run,
)
from kotodama.kotoba_datomic import get_kotoba_client
import os

LOG = logging.getLogger(__name__)

INGEST_ACTOR = "did:web:ingest.etzhayyim.com"
SOURCE_ID = "netintel-ip-enrich"
_IPINFO_BASE = "https://ipinfo.io"
_TIMEOUT = 10


def _ipinfo(ip: str, token: str) -> dict[str, Any]:
    url = f"{_IPINFO_BASE}/{ip}/json"
    if token:
        url += f"?token={token}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "etzhayyim-ingest/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return {}

    loc = data.get("loc", "")
    lat, lon = 0.0, 0.0
    if loc and "," in loc:
        parts = loc.split(",", 1)
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    org_raw = data.get("org", "")
    asn, asn_org = "", ""
    if org_raw:
        parts = org_raw.split(" ", 1)
        asn = parts[0].lstrip("AS")
        asn_org = parts[1] if len(parts) > 1 else ""

    return {
        "country_code": data.get("country", ""),
        "city": data.get("city", ""),
        "region": data.get("region", ""),
        "lat": lat,
        "lon": lon,
        "asn": asn,
        "asn_org": asn_org,
        "isp": asn_org,
        "ptr_record": data.get("hostname", ""),
    }


def _stale_ips(batch_size: int) -> list[str]:
    try:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        # R0: Multi-predicate filter for 'observed_at' and ordering is applied in Python after fetching.
        # Fetching all potential stale IPs up to a reasonable limit, then filtering/sorting.
        query_edn = """
        [:find ?address ?observed_at
         :where
           [?e :vertex-ip-address/address ?address]
           [?e :vertex-ip-address/observed-at ?observed_at]]
        """
        client = get_kotoba_client()
        results = client.q(query_edn)

        # Filter and sort in Python
        stale_ips_with_time = []
        for row in results:
            address = row[0]
            observed_at_str = row[1] # Assuming observed_at is stored as string/ISO format
            try:
                # Convert observed_at to datetime object for comparison
                observed_at = datetime.fromisoformat(observed_at_str.replace("Z", "+00:00"))
                if observed_at < thirty_days_ago:
                    stale_ips_with_time.append({"address": address, "observed_at": observed_at})
            except ValueError:
                LOG.warning(f"Could not parse observed_at '{observed_at_str}' for IP '{address}'")
                continue

        stale_ips_with_time.sort(key=lambda x: x["observed_at"])
        return [item["address"] for item in stale_ips_with_time[:batch_size]]
    except Exception as e:
        LOG.warning("stale_ips query failed with kotoba Datom client: %s", e)
        return []



def _upsert_ip(ip: str, geo: dict, run_id: str) -> bool:
    ts = now_iso()
    vertex_id = f"at://did:web:ingest.etzhayyim.com/com.etzhayyim.apps.collector.ipAddress/{ip}"

    # Construct the row_dict for insert_row
    row_dict = {
        "vertex_id": vertex_id,
        "owner_did": INGEST_ACTOR,
        "address": ip,
        "country_code": geo.get("country_code", ""),
        "city": geo.get("city", ""),
        "region": geo.get("region", ""),
        "lat": geo.get("lat", 0.0),
        "lon": geo.get("lon", 0.0),
        "asn": geo.get("asn", ""),
        "asn_org": geo.get("asn_org", ""),
        "isp": geo.get("isp", ""),
        "ptr_record": geo.get("ptr_record", ""),
        "observed_at": ts,
        "sensitivity_ord": 1,
        "created_date": datetime.now(timezone.utc).date().isoformat(), # Use isoformat for date
    }

    try:
        client = get_kotoba_client()
        result = client.insert_row("vertex_ip_address", row_dict)
        # insert_row returns the inserted/updated row as a dict, or None if no change/failure.
        # We assume success if a dict is returned.
        return result is not None
    except Exception as e:
        LOG.warning("ip upsert failed ip=%s: %s", ip, e)
        return False


def ingest_ip_enrich(
    run_id: str = "",
    target_tier: str = "shadow",
    batch_size: int = 50,
) -> dict[str, Any]:
    if not run_id:
        run_id = stable_run_id("netintel", SOURCE_ID, "delta")

    token = os.environ.get("IPINFO_TOKEN", "")

    run = IngestRun(ingest_family="netintel", source_id=SOURCE_ID, run_id=run_id, status="running")
    upsert_run(run)

    ips = _stale_ips(batch_size)
    ips_read = len(ips)
    rows_written = 0
    errors = 0

    for ip in ips:
        try:
            geo = _ipinfo(ip, token)
            if geo and _upsert_ip(ip, geo, run_id):
                rows_written += 1
        except Exception as e:
            LOG.warning("ip enrich failed ip=%s: %s", ip, e)
            errors += 1
        time.sleep(0.05)

    mark_run_finished(run_id, status="completed",
                      records_read=ips_read,
                      records_written=rows_written,
                      records_skipped=0,
                      error_count=errors)

    return {
        "ok": True,
        "runId": run_id,
        "ipsRead": ips_read,
        "rowsWritten": rows_written,
        "errorCount": errors,
    }
