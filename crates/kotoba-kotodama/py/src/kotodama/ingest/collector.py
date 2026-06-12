"""Collector business logic for Zeebe workers."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:collector.etzhayyim.com"

TABLE_COLUMNS: dict[str, set[str]] = {
    "vertex_collector_run": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "label", "did", "run_id", "collector", "target", "status", "started_at",
        "finished_at", "props", "actor_did", "org_did",
    },
    "vertex_collector_dns_observation": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "domain", "handle", "status", "observed_at", "registrar",
        "registrar_handle", "registrar_iana_id", "registration_date",
        "expiration_date", "last_changed_date", "dnssec", "run_id", "a_records",
        "aaaa_records", "cname_records", "mx_records", "ns_records", "txt_records",
        "nameservers", "created_at", "org_id", "user_id", "actor_id", "actor_did",
        "org_did",
    },
    "vertex_collector_dns_snapshot": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "domain", "registrar", "dnssec", "run_id", "snapshot_at",
        "a_records", "aaaa_records", "cname_records", "mx_records", "ns_records",
        "txt_records", "nameservers", "created_at", "org_id", "user_id", "actor_id",
        "actor_did", "org_did",
    },
    "vertex_collector_organization": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "name", "handle", "iana_id", "type", "created_at", "org_id",
        "user_id", "actor_id", "actor_did", "org_did",
    },
    "vertex_collector_blockchain_actor": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "address", "chain", "label", "source", "balance", "total_received",
        "total_sent", "tx_count", "unconfirmed_tx_count", "observed_at",
        "created_at", "org_id", "user_id", "actor_id", "actor_did", "org_did",
    },
    "vertex_collector_risk_signal": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "target_node_id", "signal_type", "address", "chain", "currency",
        "domain", "value", "confidence", "detected_at", "created_at", "org_id",
        "user_id", "actor_id", "actor_did", "org_did",
    },
    "vertex_collector_archive_snapshot": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "domain", "source", "url_key", "original", "mimetype",
        "status_code", "digest", "observed_at", "created_at", "org_id", "user_id",
        "actor_id", "actor_did", "org_did",
    },
    "vertex_collector_scan_result": {
        "vertex_id", "created_date", "sensitivity_ord", "owner_did", "rkey", "repo",
        "node_id", "ip", "port", "protocol", "state", "service", "software",
        "version", "banner", "cert_issuer", "cert_subject", "cert_expires",
        "tls_version", "tls_cipher", "os_guess", "scanner_host", "scanned_at",
        "created_at", "org_id", "user_id", "actor_id", "actor_did", "org_did",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


def gen_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _str(value: Any) -> str:
    return "" if value is None else str(value)








def _http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": "etzhayyim-collector-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"accept": "*/*", "user-agent": "etzhayyim-collector-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _insert(table: str, rec: dict[str, Any]) -> None:
    rkey = _str(rec.get("rkey") or rec.get("nodeId") or rec.get("runId") or rec.get("resultId") or gen_id("r"))
    created = _str(rec.get("createdAt") or rec.get("created_at") or now_iso())
    base = {
        "vertex_id": f"at://{ACTOR_DID}/com.etzhayyim.apps.collector.{table.removeprefix('vertex_collector_')}/{rkey}",
        "created_date": created[:10],
        "sensitivity_ord": 100,
        "owner_did": ACTOR_DID,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "created_at": created,
        "org_id": _str(rec.get("orgId") or "anon"),
        "user_id": _str(rec.get("userId") or "anon"),
        "actor_id": _str(rec.get("actorId") or "sys.collector"),
        "actor_did": _str(rec.get("actorDid") or ACTOR_DID),
        "org_did": _str(rec.get("orgDid") or "anon"),
    }
    row = {**base, **{_snake(k): (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in rec.items()}}
    allowed = TABLE_COLUMNS.get(table)
    if allowed:
        row = {k: v for k, v in row.items() if k in allowed}
    get_kotoba_client().insert_row(table, row)


def _snake(name: str) -> str:
    out = ""
    for ch in name:
        out += f"_{ch.lower()}" if ch.isupper() else ch
    return out.lstrip("_")


def _rdap_domain(domain: str) -> dict[str, Any] | None:
    tld = domain.rsplit(".", 1)[-1].lower() if "." in domain else ""
    bases = {
        "com": "https://rdap.verisign.com/com/v1",
        "net": "https://rdap.verisign.com/net/v1",
        "org": "https://rdap.org",
        "jp": "https://rdap.jprs.jp",
        "ai": "https://rdap.nic.ai",
        "io": "https://rdap.nic.io",
    }
    for base in [bases.get(tld, "https://rdap.iana.org"), "https://rdap.iana.org"]:
        try:
            data = _http_json(f"{base}/domain/{urllib.parse.quote(domain)}", {"accept": "application/rdap+json"})
            if data:
                return data
        except Exception:
            continue
    return None


def _doh(domain: str, qtype: str) -> list[str]:
    try:
        data = _http_json(f"https://cloudflare-dns.com/dns-query?name={urllib.parse.quote(domain)}&type={qtype}", {"accept": "application/dns-json"})
        return [_str(r.get("data")).rstrip(".") for r in data.get("Answer", [])]
    except Exception:
        return []


def collect_netintel_dns(domain: str = "", **_: Any) -> dict[str, Any]:
    domain = domain.strip().lower()
    if not domain:
        return {"ok": False, "error": "domain required"}
    ts = now_iso()
    run_id = gen_id("run")
    rdap = _rdap_domain(domain)
    records = {k.lower(): _doh(domain, k) for k in ["A", "AAAA", "NS", "MX", "TXT", "CNAME"]}
    entities = rdap.get("entities", []) if isinstance(rdap, dict) else []
    registrar_entity = next((e for e in entities if "registrar" in (e.get("roles") or [])), {}) if entities else {}
    registrar = _vcard_name(registrar_entity)
    nameservers = [_str(ns.get("ldhName")).lower() for ns in (rdap.get("nameservers", []) if isinstance(rdap, dict) else []) if ns.get("ldhName")]
    nameservers = nameservers or records["ns"]
    events = rdap.get("events", []) if isinstance(rdap, dict) else []
    def event_date(action: str) -> str:
        return next((_str(e.get("eventDate")) for e in events if e.get("eventAction") == action), "")
    _insert("vertex_collector_run", {"runId": run_id, "collector": "netintel-dns", "target": domain, "status": "ok" if rdap else "partial", "startedAt": ts, "finishedAt": ts})
    _insert("vertex_collector_dns_observation", {
        "nodeId": f"dns:{domain}", "domain": domain, "handle": rdap.get("handle") if isinstance(rdap, dict) else "",
        "registrar": registrar, "registrarHandle": registrar_entity.get("handle"), "registrarIanaId": "",
        "nameservers": json.dumps(nameservers), "registrationDate": event_date("registration"),
        "expirationDate": event_date("expiration"), "lastChangedDate": event_date("last changed"),
        "dnssec": str(bool((rdap.get("secureDNS") or {}).get("delegationSigned"))) if isinstance(rdap, dict) else "false",
        "status": json.dumps(rdap.get("status", []) if isinstance(rdap, dict) else []), "aRecords": json.dumps(records["a"]),
        "aaaaRecords": json.dumps(records["aaaa"]), "nsRecords": json.dumps(records["ns"]),
        "mxRecords": json.dumps(records["mx"]), "txtRecords": json.dumps(records["txt"]),
        "cnameRecords": json.dumps(records["cname"]), "runId": run_id, "observedAt": ts,
    })
    _insert("vertex_collector_dns_snapshot", {"nodeId": f"dns-snap:{domain}:{ts}", "domain": domain, "registrar": registrar, "nameservers": json.dumps(nameservers), "runId": run_id, "snapshotAt": ts, "aRecords": json.dumps(records["a"]), "aaaaRecords": json.dumps(records["aaaa"]), "nsRecords": json.dumps(records["ns"]), "mxRecords": json.dumps(records["mx"]), "txtRecords": json.dumps(records["txt"]), "cnameRecords": json.dumps(records["cname"]), "dnssec": "false"})
    if registrar_entity.get("handle"):
        _insert("vertex_collector_organization", {"nodeId": f"org:rdap-registrar-{registrar_entity.get('handle')}", "name": registrar, "handle": registrar_entity.get("handle"), "ianaId": "", "type": "registrar"})
    return {"ok": True, "domain": domain, "registrar": registrar, "nameservers": nameservers, "records": records}


def _vcard_name(entity: dict[str, Any]) -> str:
    arr = entity.get("vcardArray") or []
    if len(arr) < 2 or not isinstance(arr[1], list):
        return ""
    for field in arr[1]:
        if isinstance(field, list) and field and field[0] == "fn" and len(field) > 3:
            return _str(field[3])
    return ""


def _linode_lookup(chain: str, address: str) -> dict[str, Any] | None:
    base = os.environ.get("SS_LINODE_CRYPTO_URL", "").rstrip("/")
    if not base:
        return None
    token = os.environ.get("SS_LINODE_CRYPTO_TOKEN", "")
    try:
        return _http_json(f"{base}/{chain}/address/{urllib.parse.quote(address)}", {"x-auth-token": token})
    except Exception:
        return None


def collect_blockchain_btc(address: str = "", label: str = "", **_: Any) -> dict[str, Any]:
    return _collect_blockchain("btc", address, label)


def collect_blockchain_eth(address: str = "", label: str = "", **_: Any) -> dict[str, Any]:
    return _collect_blockchain("eth", address, label)


def _collect_blockchain(chain: str, address: str, label: str) -> dict[str, Any]:
    if not address:
        return {"ok": False, "error": "address required"}
    ts = now_iso()
    run_id = gen_id("run")
    data = _linode_lookup(chain, address) or {}
    _insert("vertex_collector_run", {"runId": run_id, "collector": f"malak-{chain}", "target": address, "status": "ok" if data else "error", "startedAt": ts, "finishedAt": ts})
    _insert("vertex_collector_blockchain_actor", {"nodeId": f"bchain:{chain}:{address}", "chain": chain, "address": address, "label": label, "totalReceived": data.get("totalReceived", 0), "totalSent": data.get("totalSent", 0), "balance": data.get("balance", 0), "txCount": data.get("txCount", 0), "unconfirmedTxCount": data.get("unconfirmedTxCount", 0), "source": f"linode-{chain}", "observedAt": ts})
    return {"ok": True, "address": address, "chain": chain, "balance": data.get("balance"), "txCount": data.get("txCount")}


def collect_common_crawl(domain: str = "", limit: int = 5, **_: Any) -> dict[str, Any]:
    return _collect_cdx("common_crawl", domain, int(limit or 5))


def collect_archive(domain: str = "", limit: int = 5, **_: Any) -> dict[str, Any]:
    return _collect_cdx("internet_archive", domain, int(limit or 5))


def _collect_cdx(source: str, domain: str, limit: int) -> dict[str, Any]:
    if not domain:
        return {"ok": False, "error": "domain required"}
    limit = min(limit, 20)
    ts = now_iso()
    records: list[dict[str, Any]] = []
    try:
        if source == "common_crawl":
            text = _http_text(f"https://index.commoncrawl.org/CC-MAIN-2024-51-index?url={urllib.parse.quote(domain + '/*')}&output=json&limit={limit}")
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            rows = _http_json(f"https://web.archive.org/cdx/search/cdx?url={urllib.parse.quote(domain)}&output=json&limit={limit}&fl=timestamp,statuscode,mimetype,urlkey")
            headers, data = rows[0], rows[1:]
            records = [dict(zip(headers, row)) for row in data]
    except Exception:
        records = []
    for rec in records:
        stamp = _str(rec.get("timestamp"))
        _insert("vertex_collector_archive_snapshot", {"nodeId": f"{source}:{domain}:{stamp}", "source": source, "domain": domain, "urlKey": rec.get("urlkey"), "original": rec.get("original"), "timestamp": stamp, "mimetype": rec.get("mimetype"), "statusCode": rec.get("statuscode"), "digest": rec.get("digest"), "observedAt": ts})
    return {"ok": True, "domain": domain, "source": source, "records": len(records)}


def ingest_scan_result(**req: Any) -> dict[str, Any]:
    if not req.get("ip") or not req.get("port"):
        return {"ok": False, "error": "ip and port required"}
    result_id = gen_id("scan")
    ts = _str(req.get("scannedAt") or now_iso())
    _insert("vertex_collector_scan_result", {"resultId": result_id, "nodeId": f"scan:{req.get('ip')}:{req.get('port')}:{ts}", "ip": req.get("ip"), "port": int(req.get("port")), "protocol": req.get("protocol") or "tcp", "state": req.get("state") or "open", "service": req.get("service"), "software": req.get("software"), "version": req.get("version"), "banner": _str(req.get("banner"))[:512], "tlsVersion": req.get("tlsVersion"), "tlsCipher": req.get("tlsCipher"), "certSubject": req.get("certSubject"), "certIssuer": req.get("certIssuer"), "certExpires": req.get("certExpires"), "osGuess": req.get("osGuess"), "scannerHost": req.get("scannerHost") or "unknown", "scannedAt": ts})
    return {"ok": True, "resultId": result_id, "ip": req.get("ip"), "port": req.get("port"), "state": req.get("state")}


def trigger_run(collector: str = "", target: str = "", **kwargs: Any) -> dict[str, Any]:
    dispatch = {
        "netintel-dns": lambda: collect_netintel_dns(domain=target, **kwargs),
        "malak-btc": lambda: collect_blockchain_btc(address=target, **kwargs),
        "malak-eth": lambda: collect_blockchain_eth(address=target, **kwargs),
        "common-crawl": lambda: collect_common_crawl(domain=target, **kwargs),
        "internet-archive": lambda: collect_archive(domain=target, **kwargs),
    }
    fn = dispatch.get(collector)
    if not fn:
        return {"ok": False, "error": f"unknown collector: {collector}", "available": list(dispatch)}
    return fn()


def get_dashboard(**_: Any) -> dict[str, Any]:
    # R0: `mv_collector_dashboard_counts` is a materialized view which doesn't directly map to Datomic entities.
    # This Datalog query retrieves all facts for entities that have `mv_collector_dashboard_counts/metric` and `mv_collector_dashboard_counts/cnt` attributes.
    # We then process these results in Python to recreate the original dictionary structure.
    rows = get_kotoba_client().q(
        '[:find ?metric ?cnt :where [?e :mv_collector_dashboard_counts/metric ?metric] [?e :mv_collector_dashboard_counts/cnt ?cnt]]'
    )
    by_metric = {r[0]: int(r[1]) for r in rows}
    return {"ok": True, "collectorRuns": by_metric.get("collectorRuns", 0), "dnsObservations": by_metric.get("dnsObservations", 0), "btcAddresses": by_metric.get("btcAddresses", 0), "ethAddresses": by_metric.get("ethAddresses", 0), "scanResults": by_metric.get("scanResults", 0), "archiveSnapshots": by_metric.get("archiveSnapshots", 0)}


def list_jobs(collector: str = "", limit: int = 50, offset: int = 0, **_: Any) -> dict[str, Any]:
    limit = min(int(limit or 50), 100)
    offset = max(int(offset or 0), 0)
    # R0: Datalog handles filtering, but ORDER BY, LIMIT, OFFSET are applied in Python.
    # We fetch all relevant runs and then apply Python's sorting and slicing for pagination.
    query = '[:find ?run_id ?collector ?target ?status ?started_at ?finished_at :where [?e :vertex_collector_run/run_id ?run_id] [?e :vertex_collector_run/collector ?collector] [?e :vertex_collector_run/target ?target] [?e :vertex_collector_run/status ?status] [?e :vertex_collector_run/started_at ?started_at] [?e :vertex_collector_run/finished_at ?finished_at]]'
    if collector:
        query = f'[:find ?run_id ?collector ?target ?status ?started_at ?finished_at :where [?e :vertex_collector_run/run_id ?run_id] [?e :vertex_collector_run/collector "{collector}"] [?e :vertex_collector_run/target ?target] [?e :vertex_collector_run/status ?status] [?e :vertex_collector_run/started_at ?started_at] [?e :vertex_collector_run/finished_at ?finished_at]]'

    all_rows = get_kotoba_client().q(query)

    # Sort by 'started_at' descending
    all_rows.sort(key=lambda x: x[4], reverse=True) # x[4] corresponds to started_at

    # Apply limit and offset
    paginated_rows = all_rows[offset : offset + limit]

    jobs = [dict(zip(["run_id", "collector", "target", "status", "started_at", "finished_at"], r)) for r in paginated_rows]

    return {"ok": True, "jobs": jobs, "total": len(jobs), "offset": offset, "limit": limit}
