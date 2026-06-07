from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any



MA_DID = "did:web:ma.etzhayyim.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    out = []
    for char in text:
        out.append(char if char.isalnum() else "-")
    slug = "-".join(part for part in "".join(out).split("-") if part)
    return slug[:96] or "unknown"


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _bounded_score(*parts: Any, floor: float = 0.45, span: float = 0.45) -> float:
    digest = hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return round(floor + value * span, 3)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _deal_vid(deal_id: str) -> str:
    return f"at://{MA_DID}/com.etzhayyim.apps.ma.deal/{_slug(deal_id)}"


def _candidate_vid(candidate_id: str) -> str:
    return f"at://{MA_DID}/com.etzhayyim.apps.ma.candidate/{_slug(candidate_id)}"


def _valuation_vid(valuation_id: str) -> str:
    return f"at://{MA_DID}/com.etzhayyim.apps.ma.valuation/{_slug(valuation_id)}"


def _match_vid(match_id: str) -> str:
    return f"at://{MA_DID}/com.etzhayyim.apps.ma.match/{_slug(match_id)}"


def _edge_id(kind: str, src: str, dst: str) -> str:
    digest = hashlib.sha256(f"{kind}|{src}|{dst}".encode("utf-8")).hexdigest()[:24]
    return f"edge:{kind}:{digest}"


def task_ma_sales_origination_intake(
    dealId: str = "",
    side: str = "sell-side",
    clientName: str = "",
    targetName: str = "",
    sector: str = "",
    jurisdiction: str = "",
    expectedValueUsd: float = 0.0,
    operatorDid: str = "",
) -> dict[str, Any]:
    deal_id = dealId or _stable_id("ma-deal", side, clientName, targetName, sector)
    clean_side = side if side in {"sell-side", "buy-side"} else "sell-side"
    return {
        "dealId": deal_id,
        "side": clean_side,
        "clientName": clientName,
        "targetName": targetName,
        "sector": sector,
        "jurisdiction": jurisdiction,
        "expectedValueUsd": _as_float(expectedValueUsd),
        "operatorDid": operatorDid,
        "status": "intake-complete",
        "stage": "sales-origination",
        "dealDid": f"{MA_DID}:deal:{_slug(deal_id)}",
        "workflowStartedAt": _now_iso(),
        "ownerActor": "org-ma-global-m-a-brokerage-orchestrator-v1",
    }


def task_ma_target_screening_score(
    dealId: str = "",
    side: str = "sell-side",
    sector: str = "",
    jurisdiction: str = "",
    targetName: str = "",
    expectedValueUsd: float = 0.0,
) -> dict[str, Any]:
    score = _bounded_score(dealId, side, sector, jurisdiction, targetName, expectedValueUsd)
    return {
        "dealId": dealId,
        "status": "screened",
        "stage": "target-screening",
        "screeningScore": score,
        "screeningVerdict": "advance" if score >= 0.62 else "hold-for-review",
        "screeningFactors": [
            {"factor": "sector-fit", "score": _bounded_score(sector, dealId)},
            {"factor": "jurisdiction-fit", "score": _bounded_score(jurisdiction, dealId)},
            {"factor": "deal-size-fit", "score": _bounded_score(expectedValueUsd, sector)},
        ],
    }


def task_ma_investment_adviser_valuation(
    dealId: str = "",
    expectedValueUsd: float = 0.0,
    screeningScore: float = 0.65,
    sector: str = "",
) -> dict[str, Any]:
    base = max(_as_float(expectedValueUsd), 1_000_000.0)
    score = max(0.1, min(_as_float(screeningScore, 0.65), 1.0))
    spread = 0.18 + (1.0 - score) * 0.16
    midpoint = base * (0.92 + score * 0.16)
    low = round(midpoint * (1.0 - spread), 2)
    high = round(midpoint * (1.0 + spread), 2)
    return {
        "dealId": dealId,
        "status": "valued",
        "stage": "valuation",
        "valuationId": _stable_id("ma-valuation", dealId, sector, base),
        "valuationMethod": "screening-score-adjusted-market-range",
        "valuationRangeLowUsd": low,
        "valuationRangeHighUsd": high,
        "valuationMidpointUsd": round(midpoint, 2),
        "valuationConfidence": round(0.45 + score * 0.4, 3),
    }


def task_ma_buyer_matching_rank(
    dealId: str = "",
    sector: str = "",
    jurisdiction: str = "",
    side: str = "sell-side",
    buyerCandidates: Any = None,
) -> dict[str, Any]:
    raw_candidates = buyerCandidates if isinstance(buyerCandidates, list) else []
    if not raw_candidates:
        raw_candidates = [
            {"name": f"{sector or 'sector'} strategic buyer", "kind": "strategic"},
            {"name": f"{jurisdiction or 'global'} financial sponsor", "kind": "financial-sponsor"},
            {"name": "cross-border platform acquirer", "kind": "platform"},
        ]
    matches = []
    for index, candidate in enumerate(raw_candidates[:10], start=1):
        if not isinstance(candidate, dict):
            candidate = {"name": str(candidate), "kind": "unknown"}
        name = str(candidate.get("name") or candidate.get("candidateName") or f"buyer-{index}")
        fit = _bounded_score(dealId, sector, jurisdiction, side, name)
        matches.append(
            {
                "matchId": _stable_id("ma-match", dealId, name),
                "buyerCandidateId": _stable_id("ma-candidate", name),
                "buyerName": name,
                "buyerKind": candidate.get("kind") or candidate.get("candidateKind") or "unknown",
                "rank": index,
                "fitScore": fit,
                "status": "shortlisted" if fit >= 0.58 else "watchlist",
            }
        )
    matches.sort(key=lambda item: item["fitScore"], reverse=True)
    for index, item in enumerate(matches, start=1):
        item["rank"] = index
    return {
        "dealId": dealId,
        "status": "matched",
        "stage": "buyer-matching",
        "matches": matches,
        "matchedBuyerCount": len([item for item in matches if item["status"] == "shortlisted"]),
        "topBuyerCandidateId": matches[0]["buyerCandidateId"] if matches else "",
    }


def task_ma_trade_broker_negotiate(
    dealId: str = "",
    matches: Any = None,
    valuationRangeLowUsd: float = 0.0,
    valuationRangeHighUsd: float = 0.0,
) -> dict[str, Any]:
    match_list = matches if isinstance(matches, list) else []
    top = match_list[0] if match_list and isinstance(match_list[0], dict) else {}
    low = _as_float(valuationRangeLowUsd)
    high = _as_float(valuationRangeHighUsd)
    return {
        "dealId": dealId,
        "status": "negotiation-ready",
        "stage": "negotiation",
        "negotiationId": _stable_id("ma-negotiation", dealId, top.get("buyerCandidateId")),
        "preferredBuyerCandidateId": top.get("buyerCandidateId", ""),
        "preferredBuyerName": top.get("buyerName", ""),
        "termSheetRangeUsd": {"low": low, "high": high},
        "requiredApprovals": ["client-approval", "conflicts-check", "compliance-review"],
    }


def task_ma_outreach_compose_draft(
    dealId: str = "",
    side: str = "sell-side",
    clientName: str = "",
    targetName: str = "",
    sector: str = "",
    jurisdiction: str = "",
    matches: Any = None,
    preferredBuyerName: str = "",
    preferredBuyerCandidateId: str = "",
    valuationRangeLowUsd: float = 0.0,
    valuationRangeHighUsd: float = 0.0,
    outreachMode: str = "draft_only",
    approvalRequired: bool = True,
    mailboxLocal: str = "ma",
    **_ignored: Any,
) -> dict[str, Any]:
    match_list = matches if isinstance(matches, list) else []
    top = match_list[0] if match_list and isinstance(match_list[0], dict) else {}
    buyer_name = preferredBuyerName or str(top.get("buyerName") or "")
    buyer_candidate_id = preferredBuyerCandidateId or str(top.get("buyerCandidateId") or "")
    recipient_email = str(top.get("email") or top.get("recipientEmail") or "").strip()
    deal_id = dealId or _stable_id("ma-deal", side, clientName, targetName, sector)
    draft_id = _stable_id("ma-outreach-draft", deal_id, buyer_candidate_id, buyer_name)
    approval_id = _stable_id("ma-outreach-approval", draft_id)
    low = _as_float(valuationRangeLowUsd)
    high = _as_float(valuationRangeHighUsd)
    subject_target = targetName or clientName or "M&A opportunity"
    subject = f"Confidential {subject_target} process"
    body_lines = [
        f"Hello {buyer_name or 'team'},",
        "",
        f"We are coordinating a confidential {side} M&A process"
        f"{f' in {sector}' if sector else ''}{f' ({jurisdiction})' if jurisdiction else ''}.",
        f"Target/client reference: {subject_target}.",
    ]
    if low > 0 or high > 0:
        body_lines.append(f"Indicative valuation range: USD {low:,.0f} - {high:,.0f}.")
    body_lines.extend(
        [
            "",
            "Please confirm whether you would like to receive an NDA and process letter.",
            "",
            "This draft requires human approval before any external send.",
        ]
    )
    missing_fields = []
    if not recipient_email:
        missing_fields.append("recipientEmail")
    if not buyer_name:
        missing_fields.append("buyerName")
    sender_local = _slug(mailboxLocal).replace("-", ".") or "ma"
    sender_address = f"{sender_local}@etzhayyim.com"
    return {
        "dealId": deal_id,
        "status": "outreach-draft-ready",
        "stage": "outreach-approval",
        "outreachMode": "draft_only" if outreachMode != "internal_only" else "internal_only",
        "approvalRequired": bool(approvalRequired),
        "outreachDraft": {
            "draftId": draft_id,
            "provider": "mailer.etzhayyim.com",
            "outboundProvider": "resend",
            "inboundProvider": "cloudflare-email-routing",
            "sendNsid": "com.etzhayyim.apps.mailer.sendEmail",
            "inboundCollection": "com.etzhayyim.apps.mailer.inboundEmail",
            "sendPolicy": "draft_only",
            "recipientRole": "buyer_candidate",
            "recipientEmail": recipient_email,
            "recipientName": buyer_name,
            "subject": subject,
            "text": "\n".join(body_lines),
            "from": sender_address,
            "replyTo": sender_address,
            "missingFields": missing_fields,
        },
        "pendingApproval": {
            "approvalId": approval_id,
            "kind": "external_outreach",
            "status": "pending",
            "requiredBy": "human-operator",
            "reason": "External M&A outreach must be reviewed before send.",
        },
    }


def task_ma_outreach_prepare_mailer_send(
    outreachDraft: dict[str, Any] | None = None,
    outreachApproved: bool = False,
    approvalStatus: str = "",
    approvedBy: str = "",
    approvedAt: str = "",
    **_ignored: Any,
) -> dict[str, Any]:
    draft = outreachDraft if isinstance(outreachDraft, dict) else {}
    approved = bool(outreachApproved) or approvalStatus == "approved"
    missing = []
    if not str(draft.get("recipientEmail") or "").strip():
        missing.append("recipientEmail")
    if not str(draft.get("recipientName") or "").strip():
        missing.append("buyerName")
    if not approved:
        return {
            "ok": False,
            "status": "approval-required",
            "sendReady": False,
            "error": "human approval required before mailer send",
        }
    if missing:
        return {
            "ok": False,
            "status": "missing-fields",
            "sendReady": False,
            "missingFields": missing,
            "error": "outreach draft is missing fields required by mailer",
        }
    payload = {
        "to": str(draft.get("recipientEmail") or ""),
        "subject": str(draft.get("subject") or ""),
        "text": str(draft.get("text") or ""),
        "from": str(draft.get("from") or "ma@etzhayyim.com"),
        "replyTo": str(draft.get("replyTo") or draft.get("from") or "ma@etzhayyim.com"),
    }
    missing_payload = [key for key in ("to", "subject", "text") if not payload[key]]
    if missing_payload:
        return {
            "ok": False,
            "status": "missing-mailer-payload",
            "sendReady": False,
            "missingFields": missing_payload,
            "error": "mailer payload requires to/subject/text",
        }
    return {
        "ok": True,
        "status": "mailer-send-ready",
        "sendReady": True,
        "sendNsid": "com.etzhayyim.apps.mailer.sendEmail",
        "mailerSendPayload": payload,
        "approval": {
            "status": "approved",
            "approvedBy": approvedBy,
            "approvedAt": approvedAt,
        },
    }


def task_ma_outreach_send_approved(
    mailerSendPayload: dict[str, Any] | None = None,
    sendReady: bool = False,
    sendNsid: str = "com.etzhayyim.apps.mailer.sendEmail",
    mailerUrl: str = "https://mailer.etzhayyim.com",
    mailerBearer: str = "",
    dryRun: bool = True,
    sendEnabled: bool = False,
    **_ignored: Any,
) -> dict[str, Any]:
    payload = mailerSendPayload if isinstance(mailerSendPayload, dict) else {}
    missing = [key for key in ("to", "subject", "text") if not str(payload.get(key) or "").strip()]
    if not sendReady:
        return {
            "ok": False,
            "status": "send-not-ready",
            "sent": False,
            "error": "sendReady must be true before approved mailer send",
        }
    if missing:
        return {
            "ok": False,
            "status": "missing-mailer-payload",
            "sent": False,
            "missingFields": missing,
            "error": "mailer payload requires to/subject/text",
        }
    request = {
        "method": "POST",
        "url": f"{mailerUrl.rstrip('/')}/xrpc/{sendNsid}",
        "body": payload,
    }
    if dryRun or not sendEnabled:
        return {
            "ok": True,
            "status": "send-staged",
            "sent": False,
            "dryRun": True,
            "sendNsid": sendNsid,
            "request": request,
            "reason": "set dryRun=false and sendEnabled=true to call mailer.etzhayyim.com",
        }

    headers = {"content-type": "application/json", "accept": "application/json"}
    if mailerBearer:
        headers["authorization"] = f"Bearer {mailerBearer}"
    req = urllib.request.Request(
        request["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read(16384).decode("utf-8", errors="replace")
            try:
                body = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = {"bodyText": text}
            return {
                "ok": 200 <= int(resp.status) < 300,
                "status": "sent" if 200 <= int(resp.status) < 300 else "mailer-error",
                "sent": 200 <= int(resp.status) < 300,
                "dryRun": False,
                "sendNsid": sendNsid,
                "httpStatus": int(resp.status),
                "response": body,
            }
    except urllib.error.HTTPError as e:
        body_text = e.read(4096).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": "mailer-error",
            "sent": False,
            "dryRun": False,
            "sendNsid": sendNsid,
            "httpStatus": int(e.code),
            "error": body_text,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "status": "transport-error",
            "sent": False,
            "dryRun": False,
            "sendNsid": sendNsid,
            "error": str(e),
        }


def task_ma_integration_close_and_handoff(
    dealId: str = "",
    status: str = "negotiation-ready",
    preferredBuyerCandidateId: str = "",
    closingStage: str = "",
) -> dict[str, Any]:
    stage = closingStage or ("pmi-handoff-ready" if status == "negotiation-ready" else "pending")
    return {
        "dealId": dealId,
        "status": "handoff-ready" if stage == "pmi-handoff-ready" else "pending",
        "stage": "closing-pmi-handoff",
        "closingStage": stage,
        "pmiHandoffId": _stable_id("ma-pmi", dealId, preferredBuyerCandidateId),
        "handoffRecords": [
            "ma.deal.summary",
            "ma.valuation.range",
            "ma.buyer.shortlist",
            "ma.negotiation.terms",
            "ma.pmi.readiness",
        ],
        "completedAt": _now_iso(),
    }


def graph_rows(
    *,
    dealId: str,
    side: str = "sell-side",
    clientName: str = "",
    targetName: str = "",
    sector: str = "",
    jurisdiction: str = "",
    expectedValueUsd: float = 0.0,
    status: str = "",
    stage: str = "",
    operatorDid: str = "",
    screeningScore: float | None = None,
    valuationId: str = "",
    valuationMethod: str = "",
    valuationRangeLowUsd: float | None = None,
    valuationRangeHighUsd: float | None = None,
    valuationMidpointUsd: float | None = None,
    valuationConfidence: float | None = None,
    matches: Any = None,
) -> dict[str, list[dict[str, Any]]]:
    deal_id = dealId or _stable_id("ma-deal", side, clientName, targetName, sector)
    deal_vid = _deal_vid(deal_id)
    created_date = _today()
    rows: dict[str, list[dict[str, Any]]] = {
        "vertex_ma_deal": [
            {
                "vertex_id": deal_vid,
                "_seq": None,
                "created_date": created_date,
                "sensitivity_ord": 3,
                "owner_did": MA_DID,
                "rkey": _slug(deal_id),
                "repo": MA_DID,
                "did": f"{MA_DID}:deal:{_slug(deal_id)}",
                "deal_id": deal_id,
                "side": side,
                "client_name": clientName or None,
                "target_name": targetName or None,
                "sector": sector or None,
                "jurisdiction": jurisdiction or None,
                "expected_value_usd": _as_float(expectedValueUsd) or None,
                "status": status or None,
                "stage": stage or None,
                "operator_did": operatorDid or None,
                "confidence": screeningScore,
            }
        ],
        "vertex_ma_candidate": [],
        "vertex_ma_valuation": [],
        "vertex_ma_match": [],
        "edge_ma_deal_candidate": [],
        "edge_ma_deal_buyer": [],
    }

    if targetName:
        target_candidate_id = _stable_id("ma-candidate", "target", deal_id, targetName)
        target_vid = _candidate_vid(target_candidate_id)
        rows["vertex_ma_candidate"].append(
            {
                "vertex_id": target_vid,
                "_seq": None,
                "created_date": created_date,
                "sensitivity_ord": 3,
                "owner_did": MA_DID,
                "rkey": _slug(target_candidate_id),
                "repo": MA_DID,
                "did": f"{MA_DID}:candidate:{_slug(target_candidate_id)}",
                "candidate_id": target_candidate_id,
                "candidate_name": targetName,
                "candidate_kind": "target",
                "sector": sector or None,
                "jurisdiction": jurisdiction or None,
                "screening_score": screeningScore,
                "confidence": screeningScore,
            }
        )
        rows["edge_ma_deal_candidate"].append(
            {
                "edge_id": _edge_id("ma-deal-target", deal_vid, target_vid),
                "src_vid": deal_vid,
                "dst_vid": target_vid,
                "relationship": "target",
                "role": side,
                "score": screeningScore,
                "created_at": _now_iso(),
            }
        )

    if valuationId or valuationRangeLowUsd is not None or valuationRangeHighUsd is not None:
        resolved_valuation_id = valuationId or _stable_id("ma-valuation", deal_id, sector)
        rows["vertex_ma_valuation"].append(
            {
                "vertex_id": _valuation_vid(resolved_valuation_id),
                "_seq": None,
                "created_date": created_date,
                "sensitivity_ord": 3,
                "owner_did": MA_DID,
                "rkey": _slug(resolved_valuation_id),
                "repo": MA_DID,
                "did": f"{MA_DID}:valuation:{_slug(resolved_valuation_id)}",
                "valuation_id": resolved_valuation_id,
                "deal_id": deal_id,
                "method": valuationMethod or "screening-score-adjusted-market-range",
                "low_usd": valuationRangeLowUsd,
                "high_usd": valuationRangeHighUsd,
                "midpoint_usd": valuationMidpointUsd,
                "currency": "USD",
                "as_of_date": created_date,
                "confidence": valuationConfidence,
            }
        )

    for item in matches if isinstance(matches, list) else []:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("buyerCandidateId") or _stable_id("ma-candidate", item.get("buyerName")))
        candidate_name = str(item.get("buyerName") or candidate_id)
        candidate_vid = _candidate_vid(candidate_id)
        match_id = str(item.get("matchId") or _stable_id("ma-match", deal_id, candidate_id))
        match_vid = _match_vid(match_id)
        fit_score = _as_float(item.get("fitScore"), 0.0)
        rank = int(item.get("rank") or 0) or None
        rows["vertex_ma_candidate"].append(
            {
                "vertex_id": candidate_vid,
                "_seq": None,
                "created_date": created_date,
                "sensitivity_ord": 3,
                "owner_did": MA_DID,
                "rkey": _slug(candidate_id),
                "repo": MA_DID,
                "did": f"{MA_DID}:candidate:{_slug(candidate_id)}",
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "candidate_kind": item.get("buyerKind") or "buyer",
                "sector": sector or None,
                "jurisdiction": jurisdiction or None,
                "screening_score": fit_score,
                "confidence": fit_score,
            }
        )
        rows["vertex_ma_match"].append(
            {
                "vertex_id": match_vid,
                "_seq": None,
                "created_date": created_date,
                "sensitivity_ord": 3,
                "owner_did": MA_DID,
                "rkey": _slug(match_id),
                "repo": MA_DID,
                "did": f"{MA_DID}:match:{_slug(match_id)}",
                "match_id": match_id,
                "deal_id": deal_id,
                "buyer_candidate_id": candidate_id,
                "rank": rank,
                "fit_score": fit_score,
                "status": item.get("status") or None,
                "confidence": fit_score,
            }
        )
        rows["edge_ma_deal_buyer"].append(
            {
                "edge_id": _edge_id("ma-deal-buyer", deal_vid, candidate_vid),
                "src_vid": deal_vid,
                "dst_vid": candidate_vid,
                "relationship": "buyer_candidate",
                "rank": rank,
                "fit_score": fit_score,
                "status": item.get("status") or None,
                "created_at": _now_iso(),
            }
        )

    return rows


def _insert_ignore(cur: Any, table: str, pk_col: str, values: dict[str, Any]) -> int:
    values = {k: v for k, v in values.items() if v is not None}
    cols = list(values)
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)
    _res = client.q(
        f"INSERT INTO {table} ({col_sql}) "
        f"SELECT {placeholders} "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE {pk_col} = %s)",
        (*[values[col] for col in cols], values[pk_col]),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _update_by_pk(cur: Any, table: str, pk_col: str, values: dict[str, Any]) -> int:
    clean_values = {
        k: v
        for k, v in values.items()
        if k != pk_col and k not in {"_seq", "created_date", "created_at"} and v is not None
    }
    if not clean_values:
        return 0
    set_sql = ", ".join(f"{k} = %s" for k in clean_values)
    _res = client.q(
        f"UPDATE {table} SET {set_sql} WHERE {pk_col} = %s",
        (*clean_values.values(), values[pk_col]),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _count_visible(cur: Any, table: str, pk_col: str, ids: list[str]) -> int:
    if not ids:
        return 0
    placeholders = ", ".join(["%s"] * len(ids))
    _res = client.q(f"SELECT COUNT(*) FROM {table} WHERE {pk_col} IN ({placeholders})", tuple(ids))
    row = (_res[0] if _res else None)
    return int(row[0] if row else 0)


def upsert_graph_rows(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    table_pk = {
        "vertex_ma_deal": "vertex_id",
        "vertex_ma_candidate": "vertex_id",
        "vertex_ma_valuation": "vertex_id",
        "vertex_ma_match": "vertex_id",
        "edge_ma_deal_candidate": "edge_id",
        "edge_ma_deal_buyer": "edge_id",
    }
    prepared = sum(len(items) for items in rows.values())
    inserted = 0
    updated = 0
    visibility: dict[str, dict[str, int]] = {}

    if True:

        client = get_kotoba_client()
        for table, items in rows.items():
            pk_col = table_pk[table]
            for item in items:
                inserted += _insert_ignore(cur, table, pk_col, item)
                updated += _update_by_pk(cur, table, pk_col, item)

        for table, items in rows.items():
            pk_col = table_pk[table]
            ids = [str(item[pk_col]) for item in items if item.get(pk_col)]
            visible = _count_visible(cur, table, pk_col, ids)
            visibility[table] = {"expected": len(ids), "visible": visible}

    visible_total = sum(v["visible"] for v in visibility.values())
    return {
        "ok": visible_total >= prepared,
        "recordsPrepared": prepared,
        "recordsInserted": inserted,
        "recordsUpdated": updated,
        "recordsVisible": visible_total,
        "visibility": visibility,
    }


def task_ma_write_graph(
    dealId: str = "",
    side: str = "sell-side",
    clientName: str = "",
    targetName: str = "",
    sector: str = "",
    jurisdiction: str = "",
    expectedValueUsd: float = 0.0,
    status: str = "",
    stage: str = "",
    operatorDid: str = "",
    screeningScore: float | None = None,
    valuationId: str = "",
    valuationMethod: str = "",
    valuationRangeLowUsd: float | None = None,
    valuationRangeHighUsd: float | None = None,
    valuationMidpointUsd: float | None = None,
    valuationConfidence: float | None = None,
    matches: Any = None,
    healthy: bool = False,
    rwHealthy: bool = False,
    dryRun: bool = True,
    **_ignored: Any,
) -> dict[str, Any]:
    rows = graph_rows(
        dealId=dealId,
        side=side,
        clientName=clientName,
        targetName=targetName,
        sector=sector,
        jurisdiction=jurisdiction,
        expectedValueUsd=expectedValueUsd,
        status=status,
        stage=stage,
        operatorDid=operatorDid,
        screeningScore=screeningScore,
        valuationId=valuationId,
        valuationMethod=valuationMethod,
        valuationRangeLowUsd=valuationRangeLowUsd,
        valuationRangeHighUsd=valuationRangeHighUsd,
        valuationMidpointUsd=valuationMidpointUsd,
        valuationConfidence=valuationConfidence,
        matches=matches,
    )
    prepared = sum(len(items) for items in rows.values())
    if dryRun:
        return {"ok": True, "dryRun": True, "recordsPrepared": prepared, "tables": rows}
    if not (healthy or rwHealthy):
        return {
            "ok": False,
            "degraded": True,
            "recordsPrepared": prepared,
            "error": "rw health gate required before ma.writeGraph",
        }
    try:
        result = upsert_graph_rows(rows)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "recordsPrepared": prepared, "error": f"ma.writeGraph failed: {e}"}
    return {"dryRun": False, **result}


def register(worker: Any, *, timeout_ms: int = 180_000) -> None:
    worker.task(task_type="ma.salesOrigination.intake", single_value=False, timeout_ms=timeout_ms)(
        task_ma_sales_origination_intake
    )
    worker.task(task_type="ma.targetScreening.score", single_value=False, timeout_ms=timeout_ms)(
        task_ma_target_screening_score
    )
    worker.task(task_type="ma.investmentAdviser.valuation", single_value=False, timeout_ms=timeout_ms)(
        task_ma_investment_adviser_valuation
    )
    worker.task(task_type="ma.buyerMatching.rank", single_value=False, timeout_ms=timeout_ms)(
        task_ma_buyer_matching_rank
    )
    worker.task(task_type="ma.tradeBroker.negotiate", single_value=False, timeout_ms=timeout_ms)(
        task_ma_trade_broker_negotiate
    )
    worker.task(task_type="ma.outreach.composeDraft", single_value=False, timeout_ms=timeout_ms)(
        task_ma_outreach_compose_draft
    )
    worker.task(task_type="ma.outreach.prepareMailerSend", single_value=False, timeout_ms=timeout_ms)(
        task_ma_outreach_prepare_mailer_send
    )
    worker.task(task_type="ma.outreach.sendApproved", single_value=False, timeout_ms=timeout_ms)(
        task_ma_outreach_send_approved
    )
    worker.task(task_type="ma.integration.closeAndHandoff", single_value=False, timeout_ms=timeout_ms)(
        task_ma_integration_close_and_handoff
    )
    worker.task(task_type="ma.writeGraph", single_value=False, timeout_ms=timeout_ms)(
        task_ma_write_graph
    )
