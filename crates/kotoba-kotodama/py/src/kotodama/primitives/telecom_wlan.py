"""telecom Phase 13 primitives — WBA OpenRoaming + Hotspot 2.0.

Eight BPMN service tasks:

  - telecom.wlan.rcoi.register
  - telecom.wlan.venue.register
  - telecom.wlan.pps.provision
  - telecom.wlan.anqp.query
  - telecom.wlan.session.attach
  - telecom.wlan.roaming.exchange
  - telecom.wlan.andsp.bridge
  - telecom.wlan.roaming.settle

Discipline:
  - UE MAC / IP / EAP credentials persisted as sha256: hashes only.
  - PPS-MO XML body, ANDSP policy, EAP credentials via vault://+sha256.
  - `attachWlanSession` UPDATE-on-release computes duration_seconds.
  - `settleWlanRoamingInvoice` aggregates wlan_roaming_exchange per partner.
    accounting_start/interim → outbound_byte payable side, accounting_stop →
    receivable side (mirrors Phase 3 TAP cellular settlement shape).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.wlan"

FEDERATIONS = {"wba_openroaming", "eduroam", "cityroam", "private", "regional"}
PROFILE_KINDS = {"settled", "settlement_free", "private"}
VENUE_GROUPS = {"unspecified", "assembly", "business", "educational",
                "factory_industrial", "institutional", "mercantile",
                "residential", "storage", "utility", "vehicular", "outdoor"}
OSU_KINDS = {"soap_xml", "spp_oma_dm", "none"}
EAP_METHODS = {"EAP-SIM", "EAP-AKA", "EAP-AKA-prime", "EAP-TLS", "EAP-TTLS", "EAP-PEAP"}
CREDENTIAL_KINDS = {"sim", "certificate", "username_password", "passpoint_r3"}
GAS_PROTOCOLS = {"gas_anqp", "gas_p2p", "gas_h2t"}
ANQP_ELEMENTS = {"nai_realm", "venue_name", "domain_name", "roaming_consortium",
                 "ip_addr_type", "3gpp_cellular", "icon_request", "osu_providers",
                 "advice_of_charge"}
IP_ASSIGNMENTS = {"dhcp_v4", "slaac_v6", "dual_stack", "ipv6_only", "static"}
TRANSPORT_KINDS = {"radius", "radsec", "diameter"}
PEER_KINDS = {"home_idp", "visited_anp", "drr", "roam_server", "settlement_hub"}
MESSAGE_KINDS = {"access_request", "access_accept", "access_reject",
                 "accounting_start", "accounting_interim", "accounting_stop"}
ATSSS_MODES = {"mptcp", "mpquic", "atsss-ll", "switch_only"}
TRANSITION_KINDS = {"wifi_to_5g", "5g_to_wifi", "concurrent_steering", "active_active"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:20]}"


def _join_vids(values: Any, kind: str) -> str | None:
    if values is None or not isinstance(values, (list, tuple, set)):
        return None
    vids = [_vid(kind, str(v).strip()) for v in values if str(v).strip()]
    return ",".join(vids) if vids else None


def _parse_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return date.fromisoformat(value[:10])


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _caller(payload: dict[str, Any]) -> str:
    return str(payload.get("callerDid") or TELECOM_DID)


def _audit(payload: dict[str, Any]) -> dict[str, Any]:
    did = _caller(payload)
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 2,
        "org_id": did,
        "user_id": did,
        "actor_id": ACTOR_TAG,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    # Use the kotoba client for insertion
    get_kotoba_client().insert_row(table, row)


def _vid(kind: str, ident: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.{kind}/{ident}"


def _require_vault_ref(value: str | None, field: str) -> None:
    if value and not value.startswith("vault://"):
        raise ValueError(f"{field} must be a vault:// pointer")


def _require_hash_prefix(value: str, field: str) -> None:
    if not (value.startswith("sha256:") or value.startswith("sha384:") or value.startswith("sha512:")):
        raise ValueError(f"{field} must be prefixed with sha256:|sha384:|sha512:")


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_wlan_rcoi_register(
    oiHex: str = "", federation: str = "",
    identityProviderOrgId: str = "", profileKind: str = "",
    validFrom: str = "", validUntil: str = "", observedAt: str = "",
    rcoiId: str = "", agreementId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"oiHex": oiHex, "federation": federation,
               "identityProviderOrgId": identityProviderOrgId,
               "profileKind": profileKind,
               "validFrom": validFrom, "validUntil": validUntil,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["oiHex", "federation", "identityProviderOrgId",
                       "profileKind", "validFrom", "validUntil", "observedAt"])
    if federation not in FEDERATIONS:
        raise ValueError(f"unsupported federation: {federation}")
    if profileKind not in PROFILE_KINDS:
        raise ValueError(f"unsupported profileKind: {profileKind}")
    r_id = rcoiId.strip() or _new_id("rcoi", oiHex, identityProviderOrgId)
    vid = _vid("wlanRcoi", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "rcoi_id": r_id, "oi_hex": oiHex, "federation": federation,
        "identity_provider_org_id": identityProviderOrgId,
        "agreement_vid": _vid("interconnectAgreement", agreementId) if agreementId else None,
        "profile_kind": profileKind,
        "valid_from": validFrom, "valid_until": validUntil,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_rcoi", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "rcoiId": r_id, "status": row["status"]}


def task_telecom_wlan_venue_register(
    venueName: str = "", venueGroup: str = "", venueType: str = "",
    jurisdiction: str = "", ssid: str = "",
    advertisedRcoiIds: Any = None, observedAt: str = "",
    venueId: str = "", latitude: float | None = None,
    longitude: float | None = None, hessid: str = "", osuKind: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"venueName": venueName, "venueGroup": venueGroup,
               "venueType": venueType, "jurisdiction": jurisdiction,
               "ssid": ssid, "advertisedRcoiIds": advertisedRcoiIds,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["venueName", "venueGroup", "venueType",
                       "jurisdiction", "ssid", "advertisedRcoiIds",
                       "observedAt"])
    if venueGroup not in VENUE_GROUPS:
        raise ValueError(f"unsupported venueGroup: {venueGroup}")
    if osuKind and osuKind not in OSU_KINDS:
        raise ValueError(f"unsupported osuKind: {osuKind}")
    if not isinstance(advertisedRcoiIds, (list, tuple)) or not advertisedRcoiIds:
        raise ValueError("advertisedRcoiIds must be a non-empty list")
    v_id = venueId.strip() or _new_id("vnu", jurisdiction, venueName, ssid)
    vid = _vid("wlanVenue", v_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "venue_id": v_id, "venue_name": venueName,
        "venue_group": venueGroup, "venue_type": venueType,
        "jurisdiction": jurisdiction,
        "latitude": float(latitude) if latitude is not None else None,
        "longitude": float(longitude) if longitude is not None else None,
        "hessid": hessid or None,
        "ssid": ssid,
        "advertised_rcoi_vids": _join_vids(advertisedRcoiIds, "wlanRcoi"),
        "osu_kind": osuKind or None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_venue", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "venueId": v_id, "status": row["status"]}


def task_telecom_wlan_pps_provision(
    subscriberId: str = "", identityProviderOrgId: str = "",
    eapMethod: str = "", credentialKind: str = "",
    advertisedRcoiIds: Any = None, ppsMoHash: str = "",
    observedAt: str = "",
    ppsMoId: str = "", profileId: str = "",
    credentialRef: str = "", ppsMoRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId,
               "identityProviderOrgId": identityProviderOrgId,
               "eapMethod": eapMethod, "credentialKind": credentialKind,
               "advertisedRcoiIds": advertisedRcoiIds,
               "ppsMoHash": ppsMoHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["subscriberId", "identityProviderOrgId",
                       "eapMethod", "credentialKind", "advertisedRcoiIds",
                       "ppsMoHash", "observedAt"])
    if eapMethod not in EAP_METHODS:
        raise ValueError(f"unsupported eapMethod: {eapMethod}")
    if credentialKind not in CREDENTIAL_KINDS:
        raise ValueError(f"unsupported credentialKind: {credentialKind}")
    if not isinstance(advertisedRcoiIds, (list, tuple)) or not advertisedRcoiIds:
        raise ValueError("advertisedRcoiIds must be a non-empty list")
    _require_hash_prefix(ppsMoHash, "ppsMoHash")
    _require_vault_ref(credentialRef, "credentialRef")
    _require_vault_ref(ppsMoRef, "ppsMoRef")
    p_id = ppsMoId.strip() or _new_id("pps", subscriberId, identityProviderOrgId, eapMethod)
    vid = _vid("wlanPpsMo", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "pps_mo_id": p_id,
        "subscriber_vid": _vid("subscriber", subscriberId),
        "profile_vid": _vid("subscriberProfile5g", profileId) if profileId else None,
        "identity_provider_org_id": identityProviderOrgId,
        "eap_method": eapMethod,
        "credential_kind": credentialKind,
        "credential_ref": credentialRef or None,
        "advertised_rcoi_vids": _join_vids(advertisedRcoiIds, "wlanRcoi"),
        "pps_mo_hash": ppsMoHash,
        "pps_mo_ref": ppsMoRef or None,
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_pps_mo", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "ppsMoId": p_id, "status": row["status"]}


def task_telecom_wlan_anqp_query(
    venueId: str = "", ueMacHash: str = "", gasProtocol: str = "",
    queryElement: str = "", responseHash: str = "", observedAt: str = "",
    queryId: str = "", responseSize: int | None = None,
    latencyMs: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"venueId": venueId, "ueMacHash": ueMacHash,
               "gasProtocol": gasProtocol, "queryElement": queryElement,
               "responseHash": responseHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["venueId", "ueMacHash", "gasProtocol",
                       "queryElement", "responseHash", "observedAt"])
    if gasProtocol not in GAS_PROTOCOLS:
        raise ValueError(f"unsupported gasProtocol: {gasProtocol}")
    if queryElement not in ANQP_ELEMENTS:
        raise ValueError(f"unsupported queryElement: {queryElement}")
    _require_hash_prefix(ueMacHash, "ueMacHash")
    _require_hash_prefix(responseHash, "responseHash")
    q_id = queryId.strip() or _new_id("anqp", venueId, ueMacHash[:16], queryElement, observedAt)
    vid = _vid("wlanAnqpQuery", q_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "query_id": q_id,
        "venue_vid": _vid("wlanVenue", venueId),
        "ue_mac_hash": ueMacHash,
        "gas_protocol": gasProtocol,
        "query_element": queryElement,
        "response_hash": responseHash,
        "response_size": int(responseSize) if responseSize is not None else None,
        "latency_ms": float(latencyMs) if latencyMs is not None else None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_anqp_query", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "queryId": q_id, "status": row["status"]}


def task_telecom_wlan_session_attach(
    subscriberId: str = "", ppsMoId: str = "", venueId: str = "",
    rcoiId: str = "", ueMacHash: str = "", eapMethod: str = "",
    attachedAt: str = "",
    sessionId: str = "", ipAssignment: str = "", releasedAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId, "ppsMoId": ppsMoId,
               "venueId": venueId, "rcoiId": rcoiId,
               "ueMacHash": ueMacHash, "eapMethod": eapMethod,
               "attachedAt": attachedAt, "callerDid": callerDid}
    _require(payload, ["subscriberId", "ppsMoId", "venueId", "rcoiId",
                       "ueMacHash", "eapMethod", "attachedAt"])
    if eapMethod not in EAP_METHODS:
        raise ValueError(f"unsupported eapMethod: {eapMethod}")
    if ipAssignment and ipAssignment not in IP_ASSIGNMENTS:
        raise ValueError(f"unsupported ipAssignment: {ipAssignment}")
    _require_hash_prefix(ueMacHash, "ueMacHash")
    s_id = sessionId.strip() or _new_id("wlsess", subscriberId, venueId, attachedAt)
    vid = _vid("wlanSession", s_id)
    is_release = bool(releasedAt and not sessionId)
    if releasedAt and sessionId and not dryRun:
        # Fetch the existing session to get 'attached_at'
        existing_session = get_kotoba_client().select_first_where(
            "vertex_telecom_wlan_session", "vertex_id", vid,
            columns=["attached_at"] # Only need this column for duration calculation
        )

        if existing_session:
            attached_at_str = existing_session["attached_at"]
            # Convert to datetime objects for calculation
            attached_at_dt = datetime.fromisoformat(attached_at_str)
            released_at_dt = datetime.fromisoformat(releasedAt)

            duration_seconds = int((released_at_dt - attached_at_dt).total_seconds())

            # Prepare the update row. insert_row will upsert based on vertex_id.
            update_row = {
                "vertex_id": vid,
                "released_at": releasedAt,
                "duration_seconds": duration_seconds,
                "status": "released",
            }
            # The client's insert_row performs an upsert on the identity column (vertex_id)
            get_kotoba_client().insert_row("vertex_telecom_wlan_session", update_row)
            return {"ok": True, "vertexId": vid, "sessionId": s_id, "status": "released"}
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "session_id": s_id,
        "subscriber_vid": _vid("subscriber", subscriberId),
        "pps_mo_vid": _vid("wlanPpsMo", ppsMoId),
        "venue_vid": _vid("wlanVenue", venueId),
        "rcoi_vid": _vid("wlanRcoi", rcoiId),
        "ue_mac_hash": ueMacHash,
        "eap_method": eapMethod,
        "ip_assignment": ipAssignment or None,
        "attached_at": attachedAt,
        "released_at": releasedAt or None,
        "duration_seconds": None,
        "status": "released" if is_release else "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_session", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "sessionId": s_id, "status": row["status"]}


def task_telecom_wlan_roaming_exchange(
    sessionId: str = "", transportKind: str = "", peerKind: str = "",
    partnerOrgId: str = "", messageKind: str = "",
    resultCode: int = 0, observedAt: str = "",
    exchangeId: str = "", drrInstanceId: str = "",
    sessionTimeSeconds: int | None = None,
    ingressBytes: int | None = None, egressBytes: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sessionId": sessionId, "transportKind": transportKind,
               "peerKind": peerKind, "partnerOrgId": partnerOrgId,
               "messageKind": messageKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["sessionId", "transportKind", "peerKind",
                       "partnerOrgId", "messageKind", "observedAt"])
    if transportKind not in TRANSPORT_KINDS:
        raise ValueError(f"unsupported transportKind: {transportKind}")
    if peerKind not in PEER_KINDS:
        raise ValueError(f"unsupported peerKind: {peerKind}")
    if messageKind not in MESSAGE_KINDS:
        raise ValueError(f"unsupported messageKind: {messageKind}")
    e_id = exchangeId.strip() or _new_id("wlex", sessionId, messageKind, observedAt)
    vid = _vid("wlanRoamingExchange", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "exchange_id": e_id,
        "session_vid": _vid("wlanSession", sessionId),
        "transport_kind": transportKind,
        "peer_kind": peerKind,
        "partner_org_id": partnerOrgId,
        "drr_instance_id": drrInstanceId or None,
        "message_kind": messageKind,
        "result_code": int(resultCode),
        "session_time_seconds": int(sessionTimeSeconds) if sessionTimeSeconds is not None else None,
        "ingress_bytes": int(ingressBytes) if ingressBytes is not None else None,
        "egress_bytes": int(egressBytes) if egressBytes is not None else None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_roaming_exchange", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "exchangeId": e_id, "status": row["status"]}


def task_telecom_wlan_andsp_bridge(
    sessionId: str = "", profileId: str = "", atsssMode: str = "",
    transitionKind: str = "", observedAt: str = "",
    bridgeId: str = "", andspPolicyHash: str = "",
    andspPolicyRef: str = "",
    targetSnssai: str = "", targetDnn: str = "",
    targetPduSessionId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sessionId": sessionId, "profileId": profileId,
               "atsssMode": atsssMode, "transitionKind": transitionKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["sessionId", "profileId", "atsssMode",
                       "transitionKind", "observedAt"])
    if atsssMode not in ATSSS_MODES:
        raise ValueError(f"unsupported atsssMode: {atsssMode}")
    if transitionKind not in TRANSITION_KINDS:
        raise ValueError(f"unsupported transitionKind: {transitionKind}")
    if andspPolicyHash:
        _require_hash_prefix(andspPolicyHash, "andspPolicyHash")
    _require_vault_ref(andspPolicyRef, "andspPolicyRef")
    b_id = bridgeId.strip() or _new_id("brg", sessionId, transitionKind, observedAt)
    vid = _vid("wlanAndspBridge", b_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "bridge_id": b_id,
        "session_vid": _vid("wlanSession", sessionId),
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "atsss_mode": atsssMode,
        "andsp_policy_hash": andspPolicyHash or None,
        "andsp_policy_ref": andspPolicyRef or None,
        "target_snssai": targetSnssai or None,
        "target_dnn": targetDnn or None,
        "target_pdu_session_vid": _vid("pduSession", targetPduSessionId) if targetPduSessionId else None,
        "transition_kind": transitionKind,
        "observed_at": observedAt,
        "status": "bridged",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_andsp_bridge", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "bridgeId": b_id, "status": row["status"]}


def task_telecom_wlan_roaming_settle(
    partnerOrgId: str = "", periodStart: str = "", periodEnd: str = "",
    invoiceId: str = "", currency: str = "USD",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"partnerOrgId": partnerOrgId, "periodStart": periodStart,
               "periodEnd": periodEnd, "callerDid": callerDid}
    _require(payload, ["partnerOrgId", "periodStart", "periodEnd"])
    ps = _parse_date(periodStart, "periodStart")
    pe = _parse_date(periodEnd, "periodEnd")
    if pe <= ps:
        raise ValueError("periodEnd must be after periodStart")
    inv_id = invoiceId.strip() or _new_id("wlinv", partnerOrgId, ps.isoformat(), pe.isoformat())
    vid = _vid("wlanRoamingInvoice", inv_id)
    session_count = 0
    total_session_time = 0
    total_in = 0
    total_out = 0
    if not dryRun:
        # R0: Multi-predicate query, aggregating in Python due to shim limitations.
        # Fetch records matching partner_org_id and message_kind
        exchanges = get_kotoba_client().select_where(
            "vertex_telecom_wlan_roaming_exchange",
            "partner_org_id",
            partnerOrgId,
            # Fetch all columns needed for filtering and aggregation
            columns=["session_vid", "session_time_seconds", "ingress_bytes", "egress_bytes", "observed_at", "message_kind"]
        )

        filtered_exchanges = []
        for ex in exchanges:
            # Apply remaining filters in Python
            if ex.get("message_kind") == "accounting_stop" and \
               ex.get("observed_at", "") >= ps.isoformat() and \
               ex.get("observed_at", "") < pe.isoformat():
                filtered_exchanges.append(ex)

        session_vids = set()
        total_session_time = 0
        total_in = 0
        total_out = 0

        for ex in filtered_exchanges:
            session_vids.add(ex["session_vid"])
            total_session_time += int(ex.get("session_time_seconds") or 0)
            total_in += int(ex.get("ingress_bytes") or 0)
            total_out += int(ex.get("egress_bytes") or 0)

        session_count = len(session_vids)
    # Phase 13 default rate card (cents / unit). Tunable via Phase 1 rate card lookup later.
    # ingress (UE → AP) = receivable from partner; egress = payable to partner.
    receivable = round(total_in * 0.000_000_01, 4)
    payable = round(total_out * 0.000_000_01, 4)
    net = round(receivable - payable, 4)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "invoice_id": inv_id,
        "partner_org_id": partnerOrgId,
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
        "currency": currency or "USD",
        "receivable_amount": receivable,
        "payable_amount": payable,
        "net_amount": net,
        "session_count": session_count,
        "total_session_time_seconds": total_session_time,
        "total_ingress_bytes": total_in,
        "total_egress_bytes": total_out,
        "issued_at": _now_iso(),
        "status": "issued",
        **_audit(payload),
    }
    _insert("vertex_telecom_wlan_roaming_invoice", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "invoiceId": inv_id,
            "netAmount": net, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.wlan.rcoi.register",     single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_rcoi_register)
    worker.task(task_type="telecom.wlan.venue.register",    single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_venue_register)
    worker.task(task_type="telecom.wlan.pps.provision",     single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_pps_provision)
    worker.task(task_type="telecom.wlan.anqp.query",        single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_anqp_query)
    worker.task(task_type="telecom.wlan.session.attach",    single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_session_attach)
    worker.task(task_type="telecom.wlan.roaming.exchange",  single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_roaming_exchange)
    worker.task(task_type="telecom.wlan.andsp.bridge",      single_value=False, timeout_ms=timeout_ms)(task_telecom_wlan_andsp_bridge)
    worker.task(task_type="telecom.wlan.roaming.settle",    single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_wlan_roaming_settle)
