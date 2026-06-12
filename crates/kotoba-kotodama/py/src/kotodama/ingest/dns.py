"""DNS / Cloudflare Registrar handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:scndu0rf.etzhayyim.com"
CF_REGISTRAR_DID = "did:web:scndu0rf.etzhayyim.com:actor:cfRegistrar"
SQ_EXPORTER_DID = "did:web:sqddf3sp.etzhayyim.com:actor:sqExporter"
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _id(prefix: str = "dns") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _domain_slug(domain: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_")


def _caller(kwargs: dict[str, Any]) -> str:
    for key in ("requesterDid", "callerDid", "did", "actorDid"):
        value = kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    caller = kwargs.get("caller")
    if isinstance(caller, dict) and isinstance(caller.get("did"), str):
        return caller["did"]
    return OWNER_DID




def ensure_cf_registrar_actor() -> None:
    get_kotoba_client().insert_row(
        "vertex_actor",
        {
            "vertex_id": CF_REGISTRAR_DID,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "did": CF_REGISTRAR_DID,
            "handle": "cf-registrar-scndu0rf.etzhayyim.com",
            "display_name": "Cloudflare Registrar Receiver",
            "name": "Cloudflare Registrar Receiver",
            "execution_tier": "T1",
            "performer_type": "service",
            "status": "active",
            "category": "infra",
            "classification": "dns-registrar",
            "operator": "etzhayyim.com",
            "agent_type": "autonomous",
            "runtime_type": "worker",
            "ui_type": "appview",
            "country": "jp",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )
    profile = {
        "displayName": "Cloudflare Registrar Receiver",
        "description": "Accepts inbound domain transfers and drives the Cloudflare Registrar API.",
        "isBot": True,
        "agentType": "autonomous",
    }
    get_kotoba_client().insert_row(
        "vertex_actor_manifest",
        {
            "vertex_id": CF_REGISTRAR_DID,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "did": CF_REGISTRAR_DID,
            "name": "Cloudflare Registrar Receiver",
            "display_name": "Cloudflare Registrar Receiver",
            "description": "Cloudflare Registrar API receiver",
            "execution_tier": "T1",
            "performer_type": "service",
            "profile_json": json.dumps(profile, ensure_ascii=False),
            "status": "active",
            "created_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )


def transfer_from_squarespace(**kwargs: Any) -> dict[str, Any]:
    ensure_cf_registrar_actor()
    domain = str(kwargs.get("domain") or "").strip().lower().rstrip(".")
    if not DOMAIN_RE.match(domain):
        return {"error": "domain required"}
    approvals = kwargs.get("approvals")
    approval_list = approvals if isinstance(approvals, list) else []
    approval_list = [str(a) for a in approval_list[:8] if a]
    status = "approved" if len(approval_list) >= 3 else "requested"
    rkey = _id("transfer")
    transfer_request_uri = f"at://{CF_REGISTRAR_DID}/com.etzhayyim.apps.dns.transferRequest/{rkey}"
    requested_at = now_iso()
    record = {
        "domain": domain,
        "fromRegistrar": "squarespace",
        "toRegistrar": "cloudflare",
        "requesterDid": _caller(kwargs),
        "cfRegistrarDid": CF_REGISTRAR_DID,
        "sqExporterDid": SQ_EXPORTER_DID,
        "projectConvoId": rkey,
        "status": status,
        "approvals": approval_list,
        "requestedAt": requested_at,
    }
    if kwargs.get("note"):
        record["note"] = str(kwargs.get("note"))[:512]
    get_kotoba_client().insert_row(
        "vertex_atrecord_dns_transfer_request",
        {
            "vertex_id": transfer_request_uri,
            "owner_did": CF_REGISTRAR_DID,
            "rkey": rkey,
            "domain": domain,
            "from_registrar": "squarespace",
            "to_registrar": "cloudflare",
            "requester_did": record["requesterDid"],
            "cf_registrar_did": CF_REGISTRAR_DID,
            "sq_exporter_did": SQ_EXPORTER_DID,
            "project_convo_id": rkey,
            "status": status,
            "approvals_json": json.dumps(approval_list),
            "requested_at": requested_at,
            "record_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        },
    )
    return {
        "transferRequestUri": transfer_request_uri,
        "transferRequestRkey": rkey,
        "status": status,
        "missingApprovals": max(0, 3 - len(approval_list)),
    }


def transfer_outcome(**kwargs: Any) -> dict[str, Any]:
    ensure_cf_registrar_actor()
    domain = str(kwargs.get("domain") or "").strip().lower().rstrip(".")
    result = str(kwargs.get("result") or "")
    if not DOMAIN_RE.match(domain):
        return {"error": "domain required"}
    if result not in {"success", "failure", "aborted"}:
        return {"error": "result must be success, failure, or aborted"}
    rkey = str(kwargs.get("rkey") or _id("outcome"))
    completed_at = str(kwargs.get("completedAt") or now_iso())
    zone_did = str(kwargs.get("zoneDid") or f"did:web:dns.etzhayyim.com:zone:{_domain_slug(domain)}")
    record = {
        "transferRequestUri": kwargs.get("transferRequestUri") or "",
        "domain": domain,
        "result": result,
        "zoneDid": zone_did if result == "success" else kwargs.get("zoneDid"),
        "cloudflareZoneId": kwargs.get("cloudflareZoneId"),
        "failureReason": kwargs.get("failureReason"),
        "rollbackSteps": kwargs.get("rollbackSteps") if isinstance(kwargs.get("rollbackSteps"), list) else [],
        "completedAt": completed_at,
    }
    get_kotoba_client().insert_row(
        "vertex_atrecord_dns_transfer_outcome",
        {
            "vertex_id": f"at://{CF_REGISTRAR_DID}/com.etzhayyim.apps.dns.transferOutcome/{rkey}",
            "owner_did": CF_REGISTRAR_DID,
            "rkey": rkey,
            "transfer_request_uri": record["transferRequestUri"],
            "domain": domain,
            "result": result,
            "zone_did": record.get("zoneDid"),
            "cloudflare_zone_id": record.get("cloudflareZoneId"),
            "failure_reason": record.get("failureReason"),
            "rollback_steps_json": json.dumps(record["rollbackSteps"]),
            "completed_at": completed_at,
            "record_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        },
    )
    if result != "success":
        return {"status": "recorded", "result": result, "domain": domain}
    get_kotoba_client().insert_row(
        "vertex_actor",
        {
            "vertex_id": zone_did,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "did": zone_did,
            "handle": f"{_domain_slug(domain)}.dns.etzhayyim.com",
            "display_name": domain,
            "name": domain,
            "execution_tier": "T1",
            "performer_type": "service",
            "status": "active",
            "category": "dns-zone",
            "classification": "cloudflare-zone",
            "operator": "etzhayyim.com",
            "agent_type": "logical",
            "runtime_type": "db-only",
            "ui_type": "metadata-only",
            "country": "jp",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )
    ownership_id = f"at://{CF_REGISTRAR_DID}/com.etzhayyim.apps.dns.ownershipTransfer/{_id('own')}"
    ownership = {
        "domain": domain,
        "fromRegistrar": "squarespace",
        "toRegistrar": "cloudflare",
        "transferDate": completed_at,
        "status": "completed",
        "zoneDid": zone_did,
    }
    get_kotoba_client().insert_row(
        "vertex_atrecord_dns_ownership_transfer",
        {
            "vertex_id": ownership_id,
            "owner_did": CF_REGISTRAR_DID,
            "domain": domain,
            "from_registrar": "squarespace",
            "to_registrar": "cloudflare",
            "zone_did": zone_did,
            "transfer_date": completed_at,
            "status": "completed",
            "record_json": json.dumps(ownership, ensure_ascii=False, sort_keys=True),
        },
    )
    return {"status": "completed", "result": result, "domain": domain, "zoneDid": zone_did, "ownershipTransferUri": ownership_id}
