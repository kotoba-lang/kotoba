"""Airline Frequent Flyer Program XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-ffp.etzhayyim.com"
ACTOR_SLUG = "air-ffp"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-ffp:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-ffp:{kind}:{uuid.uuid4().hex}"


def enroll_member(
    callerDid: str = "",
    memberDid: str = "",
    memberNumber: str = "",
    firstName: str = "",
    lastName: str = "",
    email: str = "",
    nationality: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("member", memberNumber or memberDid)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_member", {
        "vertex_id": vertex_id,
        "member_did": memberDid or callerDid or APP_DID,
        "member_number": memberNumber or vertex_id,
        "first_name": firstName or '',
        "last_name": lastName or '',
        "email": email or '',
        "nationality": nationality or '',
        "tier": 'classic',
        "miles_balance": 0,
        "status": 'active',
        "enrolled_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber or vertex_id,
        "tier": "classic",
        "milesBalance": 0,
        "enrollmentStatus": "active",
    }


def accrue_miles(
    callerDid: str = "",
    memberNumber: str = "",
    flightNo: str = "",
    depDate: str = "",
    milesEarned: int = 0,
    bonusMiles: int = 0,
    transactionRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("accrue")
    now = _now()
    total_miles = int(milesEarned) + int(bonusMiles)
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "member_number": memberNumber,
        "flight_no": flightNo or '',
        "dep_date": depDate or '',
        "miles_earned": int(milesEarned),
        "bonus_miles": int(bonusMiles),
        "total_miles": total_miles,
        "transaction_ref": transactionRef or vertex_id,
        "transaction_type": 'accrual',
        "status": 'posted',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber,
        "milesEarned": int(milesEarned),
        "bonusMiles": int(bonusMiles),
        "totalMiles": total_miles,
        "transactionRef": transactionRef or vertex_id,
    }


def redeem_reward(
    callerDid: str = "",
    memberNumber: str = "",
    rewardCode: str = "",
    milesRequired: int = 0,
    currentBalance: int = 0,
    redemptionRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("redeem")
    now = _now()
    sufficient = int(currentBalance) >= int(milesRequired)
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "member_number": memberNumber,
        "reward_code": rewardCode,
        "miles_required": int(milesRequired),
        "current_balance": int(currentBalance),
        "sufficient": sufficient,
        "redemption_ref": redemptionRef or vertex_id,
        "transaction_type": 'redemption',
        "status": 'approved' if sufficient else 'declined',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber,
        "rewardCode": rewardCode,
        "sufficient": sufficient,
        "redemptionStatus": "approved" if sufficient else "declined",
        "redemptionRef": redemptionRef or vertex_id,
    }


def update_tier(
    callerDid: str = "",
    memberNumber: str = "",
    newTier: str = "",
    previousTier: str = "",
    qualifyingMiles: int = 0,
    effectiveDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("tier-update")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_member", {
        "vertex_id": vertex_id,
        "member_number": memberNumber,
        "new_tier": newTier,
        "previous_tier": previousTier or '',
        "qualifying_miles": int(qualifyingMiles),
        "effective_date": effectiveDate or now[:10],
        "status": 'tier_updated',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber,
        "newTier": newTier,
        "previousTier": previousTier,
        "effectiveDate": effectiveDate or now[:10],
    }


def transfer_miles(
    callerDid: str = "",
    fromMemberNumber: str = "",
    toMemberNumber: str = "",
    milesAmount: int = 0,
    transferRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("transfer")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "from_member_number": fromMemberNumber,
        "to_member_number": toMemberNumber,
        "miles_amount": int(milesAmount),
        "transfer_ref": transferRef or vertex_id,
        "transaction_type": 'transfer',
        "status": 'completed',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "fromMemberNumber": fromMemberNumber,
        "toMemberNumber": toMemberNumber,
        "milesAmount": int(milesAmount),
        "transferRef": transferRef or vertex_id,
        "transferStatus": "completed",
    }


def purchase_miles(
    callerDid: str = "",
    memberNumber: str = "",
    milesPurchased: int = 0,
    pricePerMile: float = 0.0,
    totalPrice: float = 0.0,
    currency: str = "USD",
    paymentRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("purchase")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "member_number": memberNumber,
        "miles_purchased": int(milesPurchased),
        "price_per_mile": float(pricePerMile),
        "total_price": float(totalPrice),
        "currency": currency,
        "payment_ref": paymentRef or vertex_id,
        "transaction_type": 'purchase',
        "status": 'completed',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber,
        "milesPurchased": int(milesPurchased),
        "totalPrice": float(totalPrice),
        "currency": currency,
        "purchaseStatus": "completed",
    }


def expire_miles(
    callerDid: str = "",
    memberNumber: str = "",
    milesExpired: int = 0,
    expiryDate: str = "",
    reason: str = "inactivity",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("expire")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "member_number": memberNumber,
        "miles_expired": int(milesExpired),
        "expiry_date": expiryDate or now[:10],
        "reason": reason,
        "transaction_type": 'expiry',
        "status": 'expired',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "memberNumber": memberNumber,
        "milesExpired": int(milesExpired),
        "expiryDate": expiryDate or now[:10],
        "expiryStatus": "expired",
    }


def partner_reconcile(
    callerDid: str = "",
    partnerCode: str = "",
    reconciliationPeriod: str = "",
    transactionCount: int = 0,
    totalMiles: int = 0,
    currency: str = "USD",
    settlementAmount: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("partner-reconcile", f"{partnerCode}:{reconciliationPeriod}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ffp_transaction", {
        "vertex_id": vertex_id,
        "partner_code": partnerCode,
        "reconciliation_period": reconciliationPeriod,
        "transaction_count": int(transactionCount),
        "total_miles": int(totalMiles),
        "currency": currency,
        "settlement_amount": float(settlementAmount),
        "transaction_type": 'partner_reconciliation',
        "status": 'reconciled',
        "reconciled_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 3,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "partnerCode": partnerCode,
        "reconciliationPeriod": reconciliationPeriod,
        "totalMiles": int(totalMiles),
        "settlementAmount": float(settlementAmount),
        "reconcileStatus": "reconciled",
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.ffp.member.enroll": enroll_member,
        "air.ffp.miles.accrue": accrue_miles,
        "air.ffp.reward.redeem": redeem_reward,
        "air.ffp.tier.update": update_tier,
        "air.ffp.miles.transfer": transfer_miles,
        "air.ffp.miles.purchase": purchase_miles,
        "air.ffp.miles.expire": expire_miles,
        "air.ffp.partner.reconcile": partner_reconcile,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
