"""telecom Phase 5 primitives — IMS / VoLTE / VoNR voice control plane.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.ims.subscription
  - telecom.sip.register
  - telecom.voice.establish
  - telecom.voice.terminate
  - telecom.voice.suppService
  - telecom.voice.emergency
  - telecom.voice.interconnect
  - telecom.ims.billing

PII handling:
  - IMPI / IMPU / MSISDN persisted only as `sha256:` hashes.
  - Caller location for emergency_call hashed (regulator retention applies
    out-of-band; raw geolocation never written to graph).
  - SIP body / SDP / RTP media never persisted — signaling metadata only.

`task_telecom_voice_terminate` mutates an existing voice_call row by
issuing an UPDATE rather than INSERT, to roll the lifecycle into the
single row that bridges Phase 1 service / Phase 4 PDU session / Phase 3
interconnect.
"""

from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.ims"

ACCESS_NETWORKS = {"volte", "vonr", "wifi", "fixed", "vowifi"}
SESSION_VOLTYPES = {"volte", "vonr", "vowifi", "fixed", "interconnect"}
CODECS = {"AMR-NB", "AMR-WB", "EVS", "EVS-SWB", "EVS-FB", "G.711", "G.722"}
RELEASE_CAUSES = {"normal", "busy", "no_answer", "rejected", "network_failure", "media_failure", "timeout"}
RELEASED_BY = {"caller", "callee", "network", "interconnect"}
SUPP_SERVICE_TYPES = {"call_forward", "call_hold", "call_transfer", "call_waiting",
                      "conference", "clir", "clip", "do_not_disturb", "voicemail"}
SUPP_ACTIONS = {"activate", "deactivate", "invoke", "modify"}
EMERGENCY_SERVICES = {"police", "fire", "ambulance", "coastguard", "general"}
LOCATION_METHODS = {"network", "gps", "manual", "estimated"}
PEER_KINDS = {"pstn", "sip_trunk", "ims_ims", "skype_for_business", "voice_mvno"}
GATEWAY_KINDS = {"bgcf", "mgcf", "ibcf", "sbc"}
BILLING_EVENT_KINDS = {"call_setup", "call_complete", "supp_service", "emergency", "interconnect_leg"}
CHARGING_METHODS = {"online", "offline", "converged"}
USAGE_UNITS = {"seconds", "messages", "events"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_join(values: Any) -> str | None:
    if values is None:
        return None
    if isinstance(values, (list, tuple, set)):
        items = [_hash_id(v) for v in values if v]
        clean = [h for h in items if h]
        return ",".join(clean) if clean else None
    return _hash_id(values)


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:20]}"


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
    get_kotoba_client().insert_row(table, row)


def _vid(kind: str, ident: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.{kind}/{ident}"


def _epoch_seconds(iso: str) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:  # noqa: BLE001
        return None


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_ims_subscription(
    profileId: str = "", subscriberId: str = "", impi: str = "",
    impuList: Any = None, sCscfFqdn: str = "", hssNfId: str = "",
    subscriptionId: str = "", serviceProfileRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "subscriberId": subscriberId, "impi": impi,
               "impuList": impuList, "sCscfFqdn": sCscfFqdn, "hssNfId": hssNfId,
               "callerDid": callerDid}
    _require(payload, ["profileId", "subscriberId", "impi", "impuList", "sCscfFqdn", "hssNfId"])
    if not isinstance(impuList, (list, tuple)) or not impuList:
        raise ValueError("impuList must be a non-empty list of IMPU values")
    s_id = subscriptionId.strip() or _new_id("ims", subscriberId, impi)
    vid = _vid("imsSubscription", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "subscription_id": s_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "subscriber_vid": _vid("subscriber", subscriberId),
        "impi_hash": _hash_id(impi),
        "impu_hash_list": _hash_join(impuList),
        "service_profile_ref": serviceProfileRef or None,
        "s_cscf_fqdn": sCscfFqdn,
        "hss_nf_vid": _vid("nfInstance", hssNfId),
        "provisioned_at": _now_iso(),
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_ims_subscription", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "subscriptionId": s_id, "status": row["status"]}


def task_telecom_sip_register(
    subscriptionId: str = "", impi: str = "", impu: str = "",
    contactUri: str = "", pCscfFqdn: str = "",
    expiresSeconds: int = 0, observedAt: str = "",
    registrationId: str = "", accessNetwork: str = "",
    sessionId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriptionId": subscriptionId, "impi": impi, "impu": impu,
               "contactUri": contactUri, "pCscfFqdn": pCscfFqdn,
               "expiresSeconds": expiresSeconds, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["subscriptionId", "impi", "impu", "contactUri", "pCscfFqdn",
                       "expiresSeconds", "observedAt"])
    if accessNetwork and accessNetwork not in ACCESS_NETWORKS:
        raise ValueError(f"unsupported accessNetwork: {accessNetwork}")
    exp = int(expiresSeconds)
    if exp <= 0:
        raise ValueError("expiresSeconds must be > 0")
    r_id = registrationId.strip() or _new_id("sip", subscriptionId, impu, observedAt)
    vid = _vid("sipRegistration", r_id)
    expires_at = None
    base = _epoch_seconds(observedAt)
    if base is not None:
        expires_at = datetime.fromtimestamp(base + exp, UTC).replace(microsecond=0).isoformat()
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "registration_id": r_id,
        "subscription_vid": _vid("imsSubscription", subscriptionId),
        "impi_hash": _hash_id(impi),
        "impu_hash": _hash_id(impu),
        "contact_uri": contactUri,
        "p_cscf_fqdn": pCscfFqdn,
        "access_network": accessNetwork or None,
        "session_id": sessionId or None,
        "expires_seconds": exp,
        "registered_at": observedAt,
        "expires_at": expires_at,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_sip_registration", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "registrationId": r_id, "status": row["status"]}


def task_telecom_voice_establish(
    subscriberId: str = "", callerImpu: str = "", calleeImpu: str = "",
    sessionVoltype: str = "", sCscfNfId: str = "", tasNfId: str = "",
    invitedAt: str = "",
    callId: str = "", callerMsisdn: str = "", calleeMsisdn: str = "",
    codec: str = "", pduSessionId: str = "", answeredAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId, "callerImpu": callerImpu,
               "calleeImpu": calleeImpu, "sessionVoltype": sessionVoltype,
               "sCscfNfId": sCscfNfId, "tasNfId": tasNfId,
               "invitedAt": invitedAt, "callerDid": callerDid}
    _require(payload, ["subscriberId", "callerImpu", "calleeImpu",
                       "sessionVoltype", "sCscfNfId", "tasNfId", "invitedAt"])
    if sessionVoltype not in SESSION_VOLTYPES:
        raise ValueError(f"unsupported sessionVoltype: {sessionVoltype}")
    if codec and codec not in CODECS:
        raise ValueError(f"unsupported codec: {codec}")
    c_id = callId.strip() or _new_id("call", callerImpu, calleeImpu, invitedAt)
    vid = _vid("voiceCall", c_id)
    status = "ringing" if not answeredAt else "active"
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "call_id": c_id,
        "subscriber_vid": _vid("subscriber", subscriberId),
        "caller_impu_hash": _hash_id(callerImpu),
        "callee_impu_hash": _hash_id(calleeImpu),
        "caller_msisdn_hash": _hash_id(callerMsisdn) if callerMsisdn else None,
        "callee_msisdn_hash": _hash_id(calleeMsisdn) if calleeMsisdn else None,
        "session_voltype": sessionVoltype,
        "codec": codec or None,
        "pdu_session_vid": _vid("pduSession", pduSessionId) if pduSessionId else None,
        "s_cscf_nf_vid": _vid("nfInstance", sCscfNfId),
        "tas_nf_vid": _vid("nfInstance", tasNfId),
        "invited_at": invitedAt,
        "answered_at": answeredAt or None,
        "released_at": None,
        "duration_seconds": None,
        "release_cause": None, "released_by": None, "sip_response_code": None,
        "status": status,
        **_audit(payload),
    }
    _insert("vertex_telecom_voice_call", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "callId": c_id, "status": status}


def task_telecom_voice_terminate(
    callId: str = "", releaseCause: str = "", releasedBy: str = "",
    releasedAt: str = "",
    sipResponseCode: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"callId": callId, "releaseCause": releaseCause,
               "releasedBy": releasedBy, "releasedAt": releasedAt,
               "callerDid": callerDid}
    _require(payload, ["callId", "releaseCause", "releasedBy", "releasedAt"])
    if releaseCause not in RELEASE_CAUSES:
        raise ValueError(f"unsupported releaseCause: {releaseCause}")
    if releasedBy not in RELEASED_BY:
        raise ValueError(f"unsupported releasedBy: {releasedBy}")
    vid = _vid("voiceCall", callId)
    duration = None
    final_status = "released" if releaseCause == "normal" else "failed"
    if not dryRun:
        client = get_kotoba_client()
        # R0: Fetch existing call to calculate duration in Python
        existing_call = client.select_first_where(
            "vertex_telecom_voice_call", "vertex_id", vid, columns=["answered_at"]
        )
        answered_at_str = existing_call.get("answered_at") if existing_call else None

        calculated_duration = None
        if answered_at_str:
            try:
                answered_dt = datetime.fromisoformat(answered_at_str.replace("Z", "+00:00"))
                released_dt = datetime.fromisoformat(releasedAt.replace("Z", "+00:00"))
                calculated_duration = (released_dt - answered_dt).total_seconds()
            except ValueError:
                calculated_duration = 0.0
        else:
            calculated_duration = 0.0

        update_row = {
            "vertex_id": vid,  # Ensure vertex_id is present for upsert
            "released_at": releasedAt,
            "release_cause": releaseCause,
            "released_by": releasedBy,
            "sip_response_code": int(sipResponseCode) if sipResponseCode is not None else None,
            "duration_seconds": calculated_duration,
            "status": final_status,
        }
        client.insert_row("vertex_telecom_voice_call", update_row)
        duration = calculated_duration
    return {"ok": True, "vertexId": vid, "callId": callId,
            "durationSeconds": duration, "status": final_status}


def task_telecom_voice_supp_service(
    subscriptionId: str = "", serviceType: str = "", action: str = "",
    tasNfId: str = "", observedAt: str = "",
    eventId: str = "", callId: str = "", targetImpu: str = "", params: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriptionId": subscriptionId, "serviceType": serviceType,
               "action": action, "tasNfId": tasNfId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["subscriptionId", "serviceType", "action", "tasNfId", "observedAt"])
    if serviceType not in SUPP_SERVICE_TYPES:
        raise ValueError(f"unsupported serviceType: {serviceType}")
    if action not in SUPP_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    e_id = eventId.strip() or _new_id("supp", subscriptionId, serviceType, action, observedAt)
    vid = _vid("suppServiceEvent", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "event_id": e_id,
        "call_vid": _vid("voiceCall", callId) if callId else None,
        "subscription_vid": _vid("imsSubscription", subscriptionId),
        "service_type": serviceType, "action": action,
        "target_impu_hash": _hash_id(targetImpu) if targetImpu else None,
        "params": params or None,
        "tas_nf_vid": _vid("nfInstance", tasNfId),
        "observed_at": observedAt,
        "status": "applied",
        **_audit(payload),
    }
    _insert("vertex_telecom_supp_service_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "eventId": e_id, "status": row["status"]}


def task_telecom_voice_emergency(
    callId: str = "", emergencyService: str = "", jurisdiction: str = "",
    psapId: str = "", eCscfNfId: str = "", observedAt: str = "",
    emergencyId: str = "", subscriberId: str = "",
    callerLocation: str = "", locationMethod: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"callId": callId, "emergencyService": emergencyService,
               "jurisdiction": jurisdiction, "psapId": psapId,
               "eCscfNfId": eCscfNfId, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["callId", "emergencyService", "jurisdiction",
                       "psapId", "eCscfNfId", "observedAt"])
    if emergencyService not in EMERGENCY_SERVICES:
        raise ValueError(f"unsupported emergencyService: {emergencyService}")
    if locationMethod and locationMethod not in LOCATION_METHODS:
        raise ValueError(f"unsupported locationMethod: {locationMethod}")
    e_id = emergencyId.strip() or _new_id("emg", callId, jurisdiction, observedAt)
    vid = _vid("emergencyCall", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "emergency_id": e_id,
        "call_vid": _vid("voiceCall", callId),
        "subscriber_vid": _vid("subscriber", subscriberId) if subscriberId else None,
        "emergency_service": emergencyService,
        "jurisdiction": jurisdiction,
        "psap_id": psapId,
        "caller_location_hash": _hash_id(callerLocation) if callerLocation else None,
        "location_method": locationMethod or None,
        "e_cscf_nf_vid": _vid("nfInstance", eCscfNfId),
        "observed_at": observedAt,
        "status": "routed",
        **_audit(payload),
    }
    _insert("vertex_telecom_emergency_call", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "emergencyId": e_id,
            "psapId": psapId, "status": row["status"]}


def task_telecom_voice_interconnect(
    callId: str = "", agreementId: str = "", partnerId: str = "",
    gatewayKind: str = "", gatewayNfId: str = "", observedAt: str = "",
    bridgeId: str = "", peerKind: str = "", peerSipUri: str = "",
    peerTrunkRef: str = "", codec: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"callId": callId, "agreementId": agreementId,
               "partnerId": partnerId, "gatewayKind": gatewayKind,
               "gatewayNfId": gatewayNfId, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["callId", "agreementId", "partnerId",
                       "gatewayKind", "gatewayNfId", "observedAt"])
    if gatewayKind not in GATEWAY_KINDS:
        raise ValueError(f"unsupported gatewayKind: {gatewayKind}")
    if peerKind and peerKind not in PEER_KINDS:
        raise ValueError(f"unsupported peerKind: {peerKind}")
    if codec and codec not in CODECS:
        raise ValueError(f"unsupported codec: {codec}")
    b_id = bridgeId.strip() or _new_id("brg", callId, partnerId, observedAt)
    vid = _vid("voiceInterconnectBridge", b_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "bridge_id": b_id,
        "call_vid": _vid("voiceCall", callId),
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "partner_vid": _vid("roamingPartner", partnerId),
        "peer_kind": peerKind or None,
        "gateway_kind": gatewayKind,
        "gateway_nf_vid": _vid("nfInstance", gatewayNfId),
        "peer_sip_uri_hash": _hash_id(peerSipUri) if peerSipUri else None,
        "peer_trunk_ref": peerTrunkRef or None,
        "codec": codec or None,
        "observed_at": observedAt,
        "status": "bridged",
        **_audit(payload),
    }
    _insert("vertex_telecom_voice_interconnect_bridge", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "bridgeId": b_id, "status": row["status"]}


def task_telecom_ims_billing(
    callId: str = "", subscriberId: str = "", eventKind: str = "",
    ratingGroup: str = "", units: float = 0.0,
    currency: str = "", amount: float = 0.0,
    chargingMethod: str = "", startedAt: str = "",
    billingId: str = "", unitOfMeasure: str = "",
    cdfNfId: str = "", endedAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"callId": callId, "subscriberId": subscriberId,
               "eventKind": eventKind, "ratingGroup": ratingGroup,
               "currency": currency, "chargingMethod": chargingMethod,
               "startedAt": startedAt, "callerDid": callerDid}
    _require(payload, ["callId", "subscriberId", "eventKind", "ratingGroup",
                       "currency", "chargingMethod", "startedAt"])
    if eventKind not in BILLING_EVENT_KINDS:
        raise ValueError(f"unsupported eventKind: {eventKind}")
    if chargingMethod not in CHARGING_METHODS:
        raise ValueError(f"unsupported chargingMethod: {chargingMethod}")
    if unitOfMeasure and unitOfMeasure not in USAGE_UNITS:
        raise ValueError(f"unsupported unitOfMeasure: {unitOfMeasure}")
    units_f = float(units)
    amount_f = float(amount)
    if units_f < 0 or amount_f < 0:
        raise ValueError("units and amount must be non-negative")
    b_id = billingId.strip() or _new_id("imsbil", callId, eventKind, startedAt)
    vid = _vid("imsBillingEvent", b_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "billing_id": b_id,
        "call_vid": _vid("voiceCall", callId),
        "subscriber_vid": _vid("subscriber", subscriberId),
        "event_kind": eventKind,
        "rating_group": ratingGroup,
        "units": units_f, "unit_of_measure": unitOfMeasure or None,
        "currency": currency, "amount": amount_f,
        "charging_method": chargingMethod,
        "cdf_nf_vid": _vid("nfInstance", cdfNfId) if cdfNfId else None,
        "started_at": startedAt, "ended_at": endedAt or None,
        "status": "emitted",
        **_audit(payload),
    }
    _insert("vertex_telecom_ims_billing_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "billingId": b_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.ims.subscription",   single_value=False, timeout_ms=timeout_ms)(task_telecom_ims_subscription)
    worker.task(task_type="telecom.sip.register",       single_value=False, timeout_ms=timeout_ms)(task_telecom_sip_register)
    worker.task(task_type="telecom.voice.establish",    single_value=False, timeout_ms=timeout_ms)(task_telecom_voice_establish)
    worker.task(task_type="telecom.voice.terminate",    single_value=False, timeout_ms=timeout_ms)(task_telecom_voice_terminate)
    worker.task(task_type="telecom.voice.suppService",  single_value=False, timeout_ms=timeout_ms)(task_telecom_voice_supp_service)
    worker.task(task_type="telecom.voice.emergency",    single_value=False, timeout_ms=timeout_ms)(task_telecom_voice_emergency)
    worker.task(task_type="telecom.voice.interconnect", single_value=False, timeout_ms=timeout_ms)(task_telecom_voice_interconnect)
    worker.task(task_type="telecom.ims.billing",        single_value=False, timeout_ms=timeout_ms)(task_telecom_ims_billing)
