"""kouza.etzhayyim.com resident scheduler and MCP-facing control handlers."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from kotodama import udf
from kotodama.kotoba_datomic import get_kotoba_client

NS = "com.etzhayyim.apps.kouza"


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(params_json: str) -> dict[str, Any]:
    if not params_json:
        return {}
    data = json.loads(params_json)
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _record_did(owner_did: str, collection: str, rkey: str) -> str:
    return f"at://{owner_did}/{collection}/{rkey}"


def _core_sync_endpoint() -> str:
    base = os.environ.get("KOUZA_CORE_URL", "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/xrpc/{NS}.syncConnection"


def _call_core_sync(connection_did: str, owner_did: str, timeout_sec: float = 20.0) -> dict[str, Any]:
    url = _core_sync_endpoint()
    if not url:
        return {}
    payload = json.dumps(
        {"connectionDid": connection_did, "ownerDid": owner_did},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
    }
    bearer = os.environ.get("KOUZA_CORE_BEARER", "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise ValueError("kouza-core response must be a JSON object")
            data["_httpStatus"] = resp.status
            return data
    except urllib.error.HTTPError as e:
        body = e.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"kouza-core HTTP {e.code}: {body[:500]}") from e


def _int_param(params: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = params.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer") from None
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _select_due_connections(owner_did: str, stale_minutes: int, limit: int) -> list[tuple[str, str, str]]:
    # R0: Order by and limit are applied in Python due to Datalog query limitations.
    # R0: Datalog does not directly support 'NOT EXISTS' with complex predicates or 'NULLS FIRST' ordering.
    kotoba_client = get_kotoba_client()
    stale_ago = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
    stale_ago_iso = stale_ago.isoformat(timespec='seconds') + 'Z'

    if owner_did:
        query_edn_template = """
            [:find ?c-id ?found-owner-did ?provider-key ?updated-at ?created-at
             :in $ ?owner-did-val ?stale-ago-inst
             :where
             [?c-id :atrecord/kouza.institution.connection/status "active"]
             [?c-id :atrecord/kouza.institution.connection/ownerDid ?owner-did-val]
             (not
              [?r-id :atrecord/kouza.sync.run/connectionDid ?c-id]
              [?r-id :atrecord/kouza.sync.run/startedAt ?started-at-str]
              [(.compareTo ?started-at-str ?stale-ago-inst) ?cmp]
              [(> ?cmp 0)])
             [?c-id :atrecord/kouza.institution.connection/ownerDid ?found-owner-did]
             [?c-id :atrecord/kouza.institution.connection/providerKey ?provider-key]
             [?c-id :atrecord/kouza.institution.connection/updatedAt ?updated-at]
             [?c-id :atrecord/kouza.institution.connection/createdAt ?created-at]]
        """
        datalog_args = [owner_did, stale_ago_iso]
    else:
        query_edn_template = """
            [:find ?c-id ?owner-did ?provider-key ?updated-at ?created-at
             :in $ ?stale-ago-inst
             :where
             [?c-id :atrecord/kouza.institution.connection/status "active"]
             (not
              [?r-id :atrecord/kouza.sync.run/connectionDid ?c-id]
              [?r-id :atrecord/kouza.sync.run/startedAt ?started-at-str]
              [(.compareTo ?started-at-str ?stale-ago-inst) ?cmp]
              [(> ?cmp 0)])
             [?c-id :atrecord/kouza.institution.connection/ownerDid ?owner-did]
             [?c-id :atrecord/kouza.institution.connection/providerKey ?provider-key]
             [?c-id :atrecord/kouza.institution.connection/updatedAt ?updated-at]
             [?c-id :atrecord/kouza.institution.connection/createdAt ?created-at]]
        """
        datalog_args = [stale_ago_iso]

    raw_results = kotoba_client.q(query_edn_template, args=tuple(datalog_args))

    parsed_results = []
    for row in raw_results:
        c_id, o_did, p_key, updated_at_str, created_at_str = row
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00")) if updated_at_str else None
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else None
        parsed_results.append((c_id, o_did, p_key, updated_at, created_at))

    # Sort by updated_at (NULLs first) then created_at (ASC)
    sorted_results = sorted(
        parsed_results,
        key=lambda x: (x[3] is None, x[3], x[4])
    )

    return [row[:3] for row in sorted_results[:limit]]


def sync_due_connections_payload(params: dict[str, Any]) -> dict[str, Any]:
    owner_did = str(params.get("ownerDid") or "").strip()
    if owner_did and not owner_did.startswith("did:"):
        raise ValueError("ownerDid must be a DID")
    limit = _int_param(params, "maxConnections", 25, 1, 200)
    stale_minutes = _int_param(params, "staleMinutes", 60, 1, 10080)
    dry_run = bool(params.get("dryRun") or False)

    rows = _select_due_connections(owner_did, stale_minutes, limit)
    if dry_run:
        return {
            "ok": True,
            "dryRun": True,
            "adapterMode": "kouza-core" if _core_sync_endpoint() else "local-pending",
            "connectionsScanned": len(rows),
            "syncRunsCreated": 0,
            "syncRunDids": [],
        }

    if _core_sync_endpoint():
        sync_run_dids: list[str] = []
        for connection_did, row_owner_did, _provider_key in rows:
            result = _call_core_sync(connection_did, row_owner_did)
            sync_run_did = str(result.get("syncRunDid") or "")
            if sync_run_did:
                sync_run_dids.append(sync_run_did)
        return {
            "ok": True,
            "dryRun": False,
            "adapterMode": "kouza-core",
            "connectionsScanned": len(rows),
            "syncRunsCreated": len(sync_run_dids),
            "syncRunDids": sync_run_dids,
        }

    now = _now_iso()
    sync_run_dids: list[str] = []
    kotoba_client = get_kotoba_client()
    all_seqs = [
        row["_seq"]
        for row in kotoba_client.select_where("vertex_atrecord_kouza_sync_run", "_seq", "*", columns=["_seq"])
        if "_seq" in row
    ]
    seq = (max(all_seqs) if all_seqs else 0) + 1
    for idx, (connection_did, row_owner_did, provider_key) in enumerate(rows):
        rkey = f"sync-zeebe-{_hash({'connectionDid': connection_did, 'now': now, 'idx': idx})}"
        sync_run_did = _record_did(row_owner_did, f"{NS}.syncRun", rkey)
        sync_run_row = {
            "vertex_id": sync_run_did,
            "_seq": seq + idx,
            "owner_did": row_owner_did,
            "rkey": rkey,
            "connection_did": connection_did,
            "adapter_key": provider_key or "zeebe-python-resident",
            "started_at": now,
            "finished_at": now,
            "accounts_imported": 0,
            "transactions_imported": 0,
            "documents_imported": 0,
            "status": "adapter_pending",
            "error_code": "ADAPTER_NOT_CONFIGURED",
            "error_message": "Resident Zeebe/Python scheduler recorded a due sync; provider adapter is not configured yet.",
            "created_at": now,
        }
        kotoba_client.insert_row("vertex_atrecord_kouza_sync_run", sync_run_row)

        # For UPDATE, we treat it as an upsert of the vertex record
        connection_update_row = {
            "vertex_id": connection_did,
            "last_sync_run_did": sync_run_did,
            "updated_at": now,
        }
        kotoba_client.insert_row("vertex_atrecord_kouza_institution_connection", connection_update_row)
        sync_run_dids.append(sync_run_did)

    return {
        "ok": True,
        "dryRun": False,
        "adapterMode": "local-pending",
        "connectionsScanned": len(rows),
        "syncRunsCreated": len(sync_run_dids),
        "syncRunDids": sync_run_dids,
    }


@udf(
    nsid="com.etzhayyim.apps.kouza.syncDueConnections",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("kouza", "sync", "scheduler", "mcp"),
    agent_tool="Scan due kouza institution connections and record resident syncRun audit rows.",
)
def kouza_sync_due_connections(params_json: str) -> str:
    try:
        return _dump(sync_due_connections_payload(_loads(params_json)))
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e), "connectionsScanned": 0, "syncRunsCreated": 0})
    except Exception as e:  # noqa: BLE001
        return _dump(
            {
                "ok": False,
                "error": f"kouza.syncDueConnections failed: {e}",
                "connectionsScanned": 0,
                "syncRunsCreated": 0,
            }
        )
