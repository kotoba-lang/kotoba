"""Stripe Issuing handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.ingest import credits

ACTOR = "did:web:stripe.etzhayyim.com"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _gid(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:8]}"


def _rkey(value: str) -> str:
    return "".join(c if c.isalnum() or c in "._~-" else "-" for c in value.lower())[:220] or uuid.uuid4().hex





def _stripe_form(data: dict[str, Any]) -> bytes:
    pairs: list[tuple[str, str]] = []

    def add(prefix: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                add(f"{prefix}[{k}]", v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                add(f"{prefix}[{i}]", v)
        else:
            pairs.append((prefix, str(value)))

    for key, value in data.items():
        add(key, value)
    return urllib.parse.urlencode(pairs).encode()


def _stripe(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("SS_STRIPE_SECRET_KEY") or ""
    if not key:
        return {"error": "stripeNotConfigured"}
    req = urllib.request.Request(
        f"https://api.stripe.com/v1{path}",
        method=method,
        data=None if method == "GET" else _stripe_form(body or {}),
        headers={"authorization": f"Bearer {key}", "content-type": "application/x-www-form-urlencoded", "user-agent": "etzhayyim-stripe-zeebe/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw[:500]}
        return {"error": "stripeApiError", "status": e.code, "detail": data}


def _normalize_cardholder(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row.get("id"), "userId": row.get("user_id"), "name": row.get("name"), "email": row.get("email"), "phone": row.get("phone"), "authTier": row.get("auth_tier"), "stripeCardholderId": row.get("stripe_cardholder_id"), "status": row.get("status"), "orgId": row.get("org_id"), "actorId": row.get("actor_id"), "createdAt": row.get("created_at")}


def _normalize_card(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row.get("id"), "cardholderId": row.get("cardholder_id"), "userId": row.get("user_id"), "cardType": row.get("card_type"), "status": row.get("status"), "lastFour": row.get("last_four"), "currency": row.get("currency"), "spendingLimitAmount": _int(row.get("spending_limit_amount")), "spendingLimitInterval": row.get("spending_limit_interval"), "stripeCardId": row.get("stripe_card_id"), "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at")}


def _normalize_auth(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row.get("id"), "cardId": row.get("card_id"), "userId": row.get("user_id"), "stripeCardId": row.get("stripe_card_id"), "amount": _int(row.get("amount")), "currency": row.get("currency"), "decision": row.get("decision"), "reason": row.get("reason"), "availableBefore": _int(row.get("available_before")), "availableAfter": _int(row.get("available_after")), "createdAt": row.get("created_at")}


def _cardholder(user_id: str, active: bool = False) -> dict[str, Any] | None:
    kotoba = get_kotoba_client()
    if active:
        # R0: in-Python filter for 'status'
        rows = kotoba.select_where("vertex_stripe_cardholder", "user_id", user_id, limit=2000)
        row = next((r for r in rows if r.get("status") == "active"), None)
    else:
        row = kotoba.select_first_where("vertex_stripe_cardholder", "user_id", user_id)
    return _normalize_cardholder(row) if row else None


def _card(user_id: str, card_id: str) -> dict[str, Any] | None:
    kotoba = get_kotoba_client()
    # R0: in-Python filter for card_id
    rows = kotoba.select_where("vertex_stripe_issued_card", "user_id", user_id, limit=2000)
    row = next((r for r in rows if r.get("id") == card_id), None)
    return _normalize_card(row) if row else None


def _card_by_stripe(stripe_card_id: str) -> dict[str, Any] | None:
    kotoba = get_kotoba_client()
    row = kotoba.select_first_where("vertex_stripe_issued_card", "stripe_card_id", stripe_card_id)
    return _normalize_card(row) if row else None


def _auth_tier(user_id: str) -> str:
    kotoba = get_kotoba_client()
    for col in ("membership_plan", "membershipPlan"):
        try:
            row = kotoba.select_first_where("vertex_auth_account", "user_id", user_id, columns=[col])
            plan = _str((row or {}).get(col))
            if plan in ("telecom", "verified"):
                return plan
        except Exception:
            pass
    return "guest"


def _insert_cardholder(record: dict[str, Any]) -> None:
    kotoba = get_kotoba_client()
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.cardholder/{_rkey(record['id'])}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": record["id"],
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.cardholder',
        "status": record["status"],
        "id": record["id"],
        "user_id": record["userId"],
        "name": record["name"],
        "email": record["email"],
        "phone": record.get("phone", ""),
        "auth_tier": record["authTier"],
        "stripe_cardholder_id": record["stripeCardholderId"],
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": record["createdAt"],
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_cardholder", row_dict)


def _insert_card(record: dict[str, Any]) -> None:
    kotoba = get_kotoba_client()
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.issuedCard/{_rkey(record['id'])}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": record["id"],
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.issuedCard',
        "status": record["status"],
        "id": record["id"],
        "cardholder_id": record["cardholderId"],
        "user_id": record["userId"],
        "card_type": record["cardType"],
        "last_four": record["lastFour"],
        "currency": record["currency"],
        "spending_limit_amount": record["spendingLimitAmount"],
        "spending_limit_interval": record["spendingLimitInterval"],
        "stripe_card_id": record["stripeCardId"],
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": record["createdAt"],
        "updated_at": record.get("updatedAt", ""),
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_issued_card", row_dict)


def create_cardholder(userId: str = "", name: str = "", email: str = "", phone: str = "", billingAddress: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    if not userId or not name or not email:
        return {"error": "missingRequiredFields", "required": ["userId", "name", "email"]}
    tier = _auth_tier(userId)
    if tier == "guest":
        return {"error": "authTierInsufficient", "required": "verified", "current": tier}
    existing = _cardholder(userId)
    if existing:
        return {"error": "cardholderAlreadyExists", "cardholder": existing}
    result = _stripe("POST", "/issuing/cardholders", {"name": name, "email": email, "phone_number": phone, "type": "individual", "billing": {"address": billingAddress or {}}, "status": "active"})
    if result.get("error"):
        return {"error": "stripeApiError", "detail": result}
    rec = {"id": _gid("ch"), "userId": userId, "name": name, "email": email, "phone": phone, "authTier": tier, "stripeCardholderId": _str(result.get("id")), "status": "active", "createdAt": now_iso()}
    _insert_cardholder(rec)
    return {"status": "created", "cardholder": rec}


def issue_card(userId: str = "", cardType: str = "virtual", currency: str = "jpy", spendingLimitAmount: Any = 0, spendingLimitInterval: str = "monthly", initialCreditAllocation: Any = 0, destinationId: str = "", **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "missingUserId"}
    tier = _auth_tier(userId)
    ctype = "physical" if cardType == "physical" else "virtual"
    if tier == "guest" or (ctype == "physical" and tier != "telecom"):
        return {"error": "authTierInsufficient", "required": "telecom" if ctype == "physical" else "verified", "current": tier}
    holder = _cardholder(userId, True)
    if not holder:
        return {"error": "noCardholder", "message": "Create a cardholder first"}
    amount = _int(spendingLimitAmount)
    result = _stripe("POST", "/issuing/cards", {"cardholder": holder["stripeCardholderId"], "type": ctype, "currency": currency or "jpy", "status": "active", "spending_controls": {"spending_limits": [{"amount": amount, "interval": spendingLimitInterval or "monthly"}]} if amount > 0 else None, "metadata": {"etzhayyimCreditsAllocated": "0", "etzhayyimCreditsConsumed": "0", "etzhayyimCreditsUserId": userId, "etzhayyimCreditsUpdatedAt": now_iso()}})
    if result.get("error"):
        return {"error": "stripeApiError", "detail": result}
    rec = {"id": _gid("card"), "cardholderId": holder["id"], "userId": userId, "cardType": ctype, "status": "active", "lastFour": _str(result.get("last4")), "currency": currency or "jpy", "spendingLimitAmount": amount, "spendingLimitInterval": spendingLimitInterval or "monthly", "stripeCardId": _str(result.get("id")), "createdAt": now_iso()}
    _insert_card(rec)
    allocation = assign_card_credits(userId=userId, cardId=rec["id"], amount=initialCreditAllocation, destinationId=destinationId) if _int(initialCreditAllocation) > 0 else None
    return {"status": "issued", "card": rec, **({"allocation": allocation} if allocation else {})}


def get_card(userId: str = "", cardId: str = "", **_: Any) -> dict[str, Any]:
    card = _card(userId, cardId) if userId and cardId else None
    return card or {"error": "notFound"}


def list_cards(userId: str = "", limit: Any = 20, **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "missingUserId"}
    kotoba = get_kotoba_client()
    # R0: in-Python sort and limit
    # Fetch a reasonable number of cards to sort and limit in Python
    # Assuming there won't be millions of cards for a single user for now.
    # Set limit higher than actual requested limit to allow for sorting.
    fetch_limit = max(1, min(_int(limit, 20), 100)) * 2
    all_cards = kotoba.select_where("vertex_stripe_issued_card", "user_id", userId, limit=fetch_limit)
    # Sort by created_at (assuming it's a string, can be converted to datetime if needed for robust sorting)
    all_cards.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    rows = all_cards[:max(1, min(_int(limit, 20), 100))] # Apply actual limit after sorting
    items = [_normalize_card(r) for r in rows]
    return {"items": items, "total": len(items)}


def _stripe_card_credits(stripe_card: dict[str, Any]) -> dict[str, Any]:
    meta = stripe_card.get("metadata") if isinstance(stripe_card.get("metadata"), dict) else {}
    allocated = _int(meta.get("etzhayyimCreditsAllocated"))
    consumed = _int(meta.get("etzhayyimCreditsConsumed"))
    return {"allocated": allocated, "consumed": consumed, "available": max(allocated - consumed, 0), "userId": _str(meta.get("etzhayyimCreditsUserId"))}


def _update_card_credits(stripe_card_id: str, allocated: int, consumed: int, user_id: str) -> dict[str, Any]:
    return _stripe("POST", f"/issuing/cards/{stripe_card_id}", {f"metadata[etzhayyimCreditsAllocated]": str(max(allocated, 0)), f"metadata[etzhayyimCreditsConsumed]": str(max(consumed, 0)), f"metadata[etzhayyimCreditsUserId]": user_id, f"metadata[etzhayyimCreditsUpdatedAt]": now_iso()})


def assign_card_credits(userId: str = "", cardId: str = "", amount: Any = 0, destinationId: str = "", **_: Any) -> dict[str, Any]:
    value = _int(amount)
    if not userId or not cardId or value <= 0:
        return {"error": "missingRequiredFields", "required": ["userId", "cardId", "amount"]}
    card = _card(userId, cardId)
    if not card:
        return {"error": "cardNotFound"}
    allowed = credits.check_spend_allowed(userId=userId, action="cardAllocate", amount=value, destinationId=destinationId)
    if not allowed.get("allowed"):
        return {"error": "insufficientCredits", "reason": allowed.get("reason"), "balance": allowed.get("balance", 0), "required": value}
    spend = credits.spend_credits(userId=userId, action="cardAllocate", amount=value, destinationId=destinationId, sourceRef=f"stripe:cardAllocate:{cardId}:{uuid.uuid4().hex}")
    if spend.get("error"):
        return {"error": "creditSpendFailed", "detail": spend}
    stripe_card = _stripe("GET", f"/issuing/cards/{card['stripeCardId']}")
    current = _stripe_card_credits(stripe_card) if not stripe_card.get("error") else {"allocated": 0, "consumed": 0}
    allocated = _int(current.get("allocated")) + value
    consumed = _int(current.get("consumed"))
    updated = _update_card_credits(card["stripeCardId"], allocated, consumed, userId)
    if updated.get("error"):
        return {"error": "stripeMetadataUpdateFailed", "detail": updated, "warning": "credits already spent"}
    _insert_allocation(cardId, userId, value, allocated, consumed, max(allocated - consumed, 0), destinationId)
    return {"status": "allocated", "cardId": cardId, "allocated": allocated, "consumed": consumed, "available": max(allocated - consumed, 0), "creditsBalanceAfter": spend.get("balance"), "creditsTxId": spend.get("txId")}


def _insert_allocation(card_id: str, user_id: str, amount: int, allocated: int, consumed: int, available: int, destination_id: str) -> None:
    kotoba = get_kotoba_client()
    rid = _gid("cca")
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.cardCreditAllocation/{rid}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.cardCreditAllocation',
        "status": 'active',
        "id": rid,
        "card_id": card_id,
        "user_id": user_id,
        "amount": amount,
        "allocated_total": allocated,
        "consumed_total": consumed,
        "available_total": available,
        "destination_id": destination_id,
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": now_iso(),
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_card_credit_allocation", row_dict)

def get_card_credits(userId: str = "", cardId: str = "", **_: Any) -> dict[str, Any]:
    card = _card(userId, cardId) if userId and cardId else None
    if not card:
        return {"error": "cardNotFound"}
    stripe_card = _stripe("GET", f"/issuing/cards/{card['stripeCardId']}")
    if stripe_card.get("error"):
        return {"error": "stripeApiError", "detail": stripe_card}
    return {"cardId": cardId, **_stripe_card_credits(stripe_card)}


def handle_authorization(authorization: dict[str, Any] | None = None, payload: str = "", **_: Any) -> dict[str, Any]:
    auth = authorization or (json.loads(payload) if payload else {})
    card_field = auth.get("card")
    stripe_card_id = card_field if isinstance(card_field, str) else _str((card_field or {}).get("id"))
    pending = auth.get("pending_request") or auth.get("pendingRequest") or {}
    amount = _int(pending.get("amount") or auth.get("amount"))
    currency = _str(pending.get("currency") or auth.get("currency") or "jpy")
    if not stripe_card_id or amount <= 0:
        return {"approved": False, "reason": "invalidAuthorizationPayload"}
    card = _card_by_stripe(stripe_card_id)
    if not card:
        return {"approved": False, "reason": "cardNotFound"}
    stripe_card = _stripe("GET", f"/issuing/cards/{stripe_card_id}")
    if stripe_card.get("error"):
        return {"approved": False, "reason": "stripeCardFetchFailed", "detail": stripe_card}
    snap = _stripe_card_credits(stripe_card)
    if _int(snap["available"]) < amount:
        _insert_authorization(card["id"], card["userId"], stripe_card_id, amount, currency, "decline", "insufficientAssignedCredits", _int(snap["available"]), _int(snap["available"]))
        return {"approved": False, "reason": "insufficientAssignedCredits", "available": snap["available"], "required": amount}
    next_consumed = _int(snap["consumed"]) + amount
    updated = _update_card_credits(stripe_card_id, _int(snap["allocated"]), next_consumed, snap.get("userId") or card["userId"])
    if updated.get("error"):
        return {"approved": False, "reason": "metadataUpdateFailed", "detail": updated}
    after = max(_int(snap["allocated"]) - next_consumed, 0)
    _insert_authorization(card["id"], card["userId"], stripe_card_id, amount, currency, "approve", "assignedCreditsAvailable", _int(snap["available"]), after)
    _insert_consumption(card["id"], card["userId"], stripe_card_id, amount, _int(snap["allocated"]), next_consumed, after)
    return {"approved": True, "cardId": card["id"], "amount": amount, "creditSnapshot": {"allocated": snap["allocated"], "consumed": next_consumed, "available": after}}


def _insert_authorization(card_id: str, user_id: str, stripe_card_id: str, amount: int, currency: str, decision: str, reason: str, before: int, after: int) -> None:
    kotoba = get_kotoba_client()
    rid = _gid("auth")
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.authorization/{rid}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.authorization',
        "status": 'active',
        "id": rid,
        "card_id": card_id,
        "user_id": user_id,
        "stripe_card_id": stripe_card_id,
        "amount": amount,
        "currency": currency,
        "decision": decision,
        "reason": reason,
        "available_before": before,
        "available_after": after,
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": now_iso(),
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_authorization", row_dict)

def _insert_consumption(card_id: str, user_id: str, stripe_card_id: str, amount: int, allocated: int, consumed: int, available: int) -> None:
    kotoba = get_kotoba_client()
    rid = _gid("ccc")
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.cardCreditConsumption/{rid}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.cardCreditConsumption',
        "status": 'active',
        "id": rid,
        "card_id": card_id,
        "user_id": user_id,
        "stripe_card_id": stripe_card_id,
        "amount": amount,
        "allocated_total": allocated,
        "consumed_total": consumed,
        "available_total": available,
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": now_iso(),
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_card_credit_consumption", row_dict)

def _card_status(userId: str, cardId: str, status: str, label: str) -> dict[str, Any]:
    card = _card(userId, cardId) if userId and cardId else None
    if not card:
        return {"error": "notFound"}
    result = _stripe("POST", f"/issuing/cards/{card['stripeCardId']}", {"status": status})
    if result.get("error"):
        return {"error": "stripeApiError", "detail": result}

    kotoba = get_kotoba_client()
    # R0: Datomic update is an upsert via insert_row
    current_raw_card_data = kotoba.select_first_where("vertex_stripe_issued_card", "id", cardId)
    if not current_raw_card_data:
        return {"error": "notFound"} # Should not happen if _card found it

    current_raw_card_data["status"] = status
    current_raw_card_data["updated_at"] = now_iso()

    kotoba.insert_row("vertex_stripe_issued_card", current_raw_card_data)

    return {"status": label, "cardId": cardId}


def freeze_card(userId: str = "", cardId: str = "", **_: Any) -> dict[str, Any]:
    return _card_status(userId, cardId, "inactive", "frozen")


def unfreeze_card(userId: str = "", cardId: str = "", **_: Any) -> dict[str, Any]:
    return _card_status(userId, cardId, "active", "unfrozen")


def cancel_card(userId: str = "", cardId: str = "", **_: Any) -> dict[str, Any]:
    return _card_status(userId, cardId, "canceled", "canceled")


def update_spending_limit(userId: str = "", cardId: str = "", amount: Any = None, interval: str = "monthly", categories: list[str] | None = None, **_: Any) -> dict[str, Any]:
    card = _card(userId, cardId) if userId and cardId and amount is not None else None
    if not card:
        return {"error": "missingRequiredFields"}
    value = _int(amount)
    result = _stripe("POST", f"/issuing/cards/{card['stripeCardId']}", {"spending_controls": {"spending_limits": [{"amount": value, "interval": interval or "monthly", "categories": categories or []}]}})
    if result.get("error"):
        return {"error": "stripeApiError", "detail": result}

    kotoba = get_kotoba_client()
    rid = _gid("sl")
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.stripe.spendingLimit/{rid}",
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "collection": 'com.etzhayyim.apps.stripe.spendingLimit',
        "status": 'active',
        "id": rid, # Corrected: unique ID for the spending limit record
        "card_id": cardId,
        "user_id": userId,
        "amount": value,
        "interval": interval or "monthly",
        "categories_json": json.dumps(categories or []),
        "org_id": 'anon',
        "actor_id": ACTOR,
        "created_at": now_iso(),
        "actor_did": ACTOR,
        "org_did": 'anon',
    }
    kotoba.insert_row("vertex_stripe_spending_limit", row_dict)
    return {"status": "updated", "cardId": cardId, "amount": value, "interval": interval or "monthly"}


def list_transactions(userId: str = "", cardId: str = "", limit: Any = 50, **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "missingUserId"}
    kotoba = get_kotoba_client()
    fetch_limit = max(1, min(_int(limit, 50), 100)) * 2 # Fetch double the requested limit

    all_transactions = []
    if cardId:
        # R0: in-Python filter for card_id, sort and limit
        transactions_by_user = kotoba.select_where("vertex_stripe_authorization", "user_id", userId, limit=fetch_limit)
        all_transactions = [t for t in transactions_by_user if t.get("card_id") == cardId]
    else:
        # R0: in-Python sort and limit
        all_transactions = kotoba.select_where("vertex_stripe_authorization", "user_id", userId, limit=fetch_limit)

    all_transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    rows = all_transactions[:max(1, min(_int(limit, 50), 100))] # Apply actual limit after sorting

    items = [_normalize_auth(r) for r in rows]
    return {"items": items, "total": len(items)}


def get_cardholder(userId: str = "", **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "missingUserId"}
    return _cardholder(userId) or {"error": "notFound"}


def wave(**_: Any) -> dict[str, Any]:
    return {"status": "posted"}


def stats(**_: Any) -> dict[str, Any]:
    kotoba = get_kotoba_client()
    ch_count = kotoba.aggregate_where("vertex_stripe_cardholder", "count", "*")
    cards_count = kotoba.aggregate_where("vertex_stripe_issued_card", "count", "*")
    auths_count = kotoba.aggregate_where("vertex_stripe_authorization", "count", "*")
    return {"totalCardholders": _int(ch_count), "totalCards": _int(cards_count), "totalAuthorizations": _int(auths_count), "domain": "stripe"}


def handle_commit(collection: str = "", action: str = "", **_: Any) -> dict[str, Any]:
    if action and action != "create":
        return {"ok": True, "detail": "skip non-create"}
    return {"ok": True, "detail": f"accepted {collection or 'commit'}"}
