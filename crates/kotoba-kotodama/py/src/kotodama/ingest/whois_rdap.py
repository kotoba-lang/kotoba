"""
whois_rdap — WHOIS snapshot collection for shadow-level domains.

Pulls domains from vertex_dns_observation, queries RDAP (IANA + TLD-specific
endpoints), and writes structured snapshots to vertex_whois_record, stored in the kotoba Datom log.

New table: vertex_whois_record (see migration 20260428180000)

Task type: netintel.whois.delta
Env: none required (uses public RDAP APIs)
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any
from datetime import datetime, timedelta, timezone

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
SOURCE_ID = "netintel-whois"
# rdap.org bootstraps to the correct registrar RDAP endpoint per RFC 7484.
# rdap.iana.org serves TLD info only and returns 404 for SLDs like cloudflare.com.
_RDAP_BOOTSTRAP = "https://rdap.org/domain/"
_TIMEOUT = 12


def _http_json(url: str, timeout: int = _TIMEOUT) -> dict | None:
    req = urllib.request.Request(url, headers={"Accept": "application/rdap+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _rdap_fetch(domain: str) -> dict[str, Any]:
    data = _http_json(f"{_RDAP_BOOTSTRAP}{domain}")
    if not data:
        return {}

    registrar = ""
    registrar_iana_id = ""
    for ent in data.get("entities", []):
        roles = ent.get("roles", [])
        if "registrar" in roles:
            registrar_iana_id = str(ent.get("handle", "")).lstrip("IANA-")
            vcard = ent.get("vcardArray", [])
            if isinstance(vcard, list) and len(vcard) > 1:
                for prop in vcard[1]:
                    if isinstance(prop, list) and prop[0] == "fn":
                        registrar = str(prop[3] or "")
                        break
            break

    nameservers = []
    for ns in data.get("nameservers", []):
        ldhName = ns.get("ldhName", "")
        if ldhName:
            nameservers.append(ldhName.lower())

    events: dict[str, str] = {}
    for ev in data.get("events", []):
        act = ev.get("eventAction", "")
        dt = ev.get("eventDate", "")
        if act and dt:
            events[act] = dt

    status = [s for s in data.get("status", []) if isinstance(s, str)]
    dnssec = data.get("secureDNS", {})
    dnssec_str = "signed" if dnssec.get("delegationSigned") else "unsigned"

    raw_excerpt = json.dumps({
        "handle": data.get("handle", ""),
        "ldhName": data.get("ldhName", ""),
        "status": status[:5],
        "events": events,
    }, ensure_ascii=False)[:4096]

    return {
        "registrar": registrar[:512],
        "registrar_iana_id": registrar_iana_id[:64],
        "nameservers": ",".join(nameservers)[:2048],
        "created_date_rdap": events.get("registration", ""),
        "updated_date_rdap": events.get("last changed", ""),
        "expires_date_rdap": events.get("expiration", ""),
        "status": ",".join(status)[:512],
        "dnssec": dnssec_str,
        "raw_excerpt": raw_excerpt,
    }


def _stale_domains(batch_size: int) -> list[str]:
    # Domains not already snapshotted in vertex_whois_record within 30 days.
    # R0: Multi-predicate filter, grouping, and ordering applied in Python.
    # Domains not already snapshotted in vertex_whois_record within 30 days.
    from datetime import datetime, timedelta, timezone
    kotoba = get_kotoba_client()
    try:
        # Fetch all dns observations
        dns_observations = kotoba.select_where("vertex_dns_observation", "domain", "*", columns=["domain", "observed_at"], limit=20000) # Arbitrary large limit

        # Fetch all whois records
        whois_records = kotoba.select_where("vertex_whois_record", "domain", "*", columns=["domain", "queried_at"], limit=20000) # Arbitrary large limit

        # Create a map of domain to latest queried_at from whois_records
        latest_queried_at = {}
        for record in whois_records:
            domain = record["domain"]
            queried_at_str = record["queried_at"]
            if queried_at_str:
                queried_at = datetime.fromisoformat(queried_at_str.replace("Z", "+00:00"))
                if domain not in latest_queried_at or queried_at > latest_queried_at[domain]:
                    latest_queried_at[domain] = queried_at

        stale_candidate_domains = []
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Filter out domains that have been queried recently
        for obs in dns_observations:
            domain = obs["domain"]
            if domain:
                if domain in latest_queried_at:
                    if latest_queried_at[domain] < thirty_days_ago:
                        stale_candidate_domains.append(obs)
                else: # No whois record exists, so it's stale
                    stale_candidate_domains.append(obs)

        # Group by domain and find the minimum observed_at
        domain_min_observed_at = {}
        for obs in stale_candidate_domains:
            domain = obs["domain"]
            observed_at_str = obs["observed_at"]
            if observed_at_str:
                observed_at = datetime.fromisoformat(observed_at_str.replace("Z", "+00:00"))
                if domain not in domain_min_observed_at or observed_at < domain_min_observed_at[domain]:
                    domain_min_observed_at[domain] = observed_at

        # Sort by minimum observed_at and limit to batch_size
        sorted_domains = sorted(domain_min_observed_at.items(), key=lambda item: item[1])
        return [domain for domain, _ in sorted_domains[:batch_size]]
    except Exception as e:
        LOG.warning("stale_domains_for_whois failed: %s", e)
        return []


def _insert_whois(domain: str, rdap: dict, run_id: str) -> bool:
    kotoba = get_kotoba_client()
    ts = now_iso()
    created_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    snap_hash = f"{domain}:{ts}" # No need for hashlib, just a string for uniqueness
    vertex_id = f"at://did:web:ingest.etzhayyim.com/com.etzhayyim.apps.ingest.whoisRecord/{domain}:{snap_hash}"

    row_dict = {
        "vertex_id": vertex_id,
        "owner_did": INGEST_ACTOR,
        "domain": domain,
        "registrar": rdap.get("registrar", ""),
        "registrar_iana_id": rdap.get("registrar_iana_id", ""),
        "nameservers": rdap.get("nameservers", ""),
        "created_date_rdap": rdap.get("created_date_rdap", ""),
        "updated_date_rdap": rdap.get("updated_date_rdap", ""),
        "expires_date_rdap": rdap.get("expires_date_rdap", ""),
        "status": rdap.get("status", ""),
        "dnssec": rdap.get("dnssec", ""),
        "raw_excerpt": rdap.get("raw_excerpt", ""),
        "queried_at": ts,
        "run_id": run_id,
        "sensitivity_ord": 1,
        "created_date": created_date,
    }
    try:
        kotoba.insert_row("vertex_whois_record", row_dict)
        return True # insert_row does not return rowcount, assume success if no exception
    except Exception as e:
        LOG.warning("whois insert failed domain=%s: %s", domain, e)
        return False


def ingest_whois_delta(
    run_id: str = "",
    target_tier: str = "shadow",
    batch_size: int = 50,
) -> dict[str, Any]:
    if not run_id:
        run_id = stable_run_id("netintel", SOURCE_ID, "delta")

    run = IngestRun(ingest_family="netintel", source_id=SOURCE_ID, run_id=run_id, status="running")
    upsert_run(run)

    domains = _stale_domains(batch_size)
    domains_read = len(domains)
    rows_written = 0
    errors = 0

    for domain in domains:
        try:
            rdap = _rdap_fetch(domain)
            if rdap and _insert_whois(domain, rdap, run_id):
                rows_written += 1
        except Exception as e:
            LOG.warning("whois enrich failed domain=%s: %s", domain, e)
            errors += 1
        time.sleep(0.15)

    mark_run_finished(run_id, status="completed",
                      records_read=domains_read,
                      records_written=rows_written,
                      records_skipped=0,
                      error_count=errors)

    return {
        "ok": True,
        "runId": run_id,
        "domainsRead": domains_read,
        "rowsWritten": rows_written,
        "errorCount": errors,
    }
