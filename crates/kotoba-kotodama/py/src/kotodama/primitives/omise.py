"""Omise marketplace XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


APP_DID = "did:web:omise.etzhayyim.com"

A = {
    "platformAdmin": f"{APP_DID}:actor:platformAdmin",
    "platformSupport": f"{APP_DID}:actor:platformSupport",
    "sellerOnboarding": f"{APP_DID}:actor:sellerOnboarding",
    "sellerCatalog": f"{APP_DID}:actor:sellerCatalog",
    "sellerFulfillment": f"{APP_DID}:actor:sellerFulfillment",
    "sellerFinance": f"{APP_DID}:actor:sellerFinance",
    "sellerMarketing": f"{APP_DID}:actor:sellerMarketing",
    "buyerAssistant": f"{APP_DID}:actor:buyerAssistant",
    "buyerReview": f"{APP_DID}:actor:buyerReview",
    "logistics": f"{APP_DID}:actor:logistics",
    "analyst": f"{APP_DID}:actor:analyst",
}

TABLE = {
    "seller": "vertex_OmiseSeller",
    "product": "vertex_OmiseProduct",
    "order": "vertex_OmiseOrder",
    "cart": "vertex_OmiseCart",
    "coupon": "vertex_OmiseCoupon",
    "review": "vertex_OmiseReview",
    "shipment": "vertex_OmiseShipment",
    "settlement": "vertex_OmiseSettlement",
    "dispute": "vertex_OmiseDispute",
    "payout": "vertex_OmisePayout",
    "pickup": "vertex_OmisePickupRequest",
}


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:6]}"


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        n = float(v)
        return n if n == n and n not in (float("inf"), float("-inf")) else fallback
    except (TypeError, ValueError):
        return fallback


def _int(v: Any, fallback: int = 0) -> int:
    return int(_num(v, fallback))


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _rls(actor: str) -> dict[str, Any]:
    return {"org_id": "anon", "user_id": "anon", "actor_id": actor, "created_at": _now()}


def _select(table: str, match: dict[str, Any] | None = None, *, limit: int = 50, offset: int = 0, order: str = "created_at") -> list[dict[str, Any]]:
    match = {k: v for k, v in (match or {}).items() if v not in ("", None)}
    # R0: Multi-predicate match, offset, limit, and order are handled in Python after fetching from kotoba Datom log client.
    # The kotoba client's select_where only supports single equality predicates and a basic limit.
    # Datalog 'q' could be used for more complex queries, but Python filtering is sufficient here.

    kotoba_client = get_kotoba_client()
    if match and len(match) == 1:
        col, val = next(iter(match.items()))
        # Fetch up to 2000 rows with the single matching condition
        all_rows = kotoba_client.select_where(table, col, val, limit=2000)
    else:
        # If no match or multiple matches, fetch a broad set and filter in Python
        all_rows = kotoba_client.select_where(table, None, None, limit=2000) # Fetch up to 2000 rows broadly
        if match:
            all_rows = [row for row in all_rows if all(row.get(k) == v for k, v in match.items())]

    # Apply ordering in Python (assuming DESC based on original SQL)
    all_rows.sort(key=lambda x: x.get(order, ""), reverse=True)

    # Apply offset and limit in Python
    return all_rows[offset : offset + limit]


def _count(table: str, match: dict[str, Any] | None = None) -> int:
    match = {k: v for k, v in (match or {}).items() if v not in ("", None)}
    # R0: Multi-predicate match is handled in Python after fetching from kotoba Datom log client.
    # The kotoba client's aggregate_where only supports single equality predicates.

    kotoba_client = get_kotoba_client()
    if match and len(match) == 1:
        col, val = next(iter(match.items()))
        count = kotoba_client.aggregate_where(table, "count", "*", col, val)
        return int(count)
    else:
        # If no match or multiple matches, fetch broadly and count in Python
        all_rows = kotoba_client.select_where(table, None, None, limit=2000) # Fetch up to 2000 rows broadly
        if match:
            all_rows = [row for row in all_rows if all(row.get(k) == v for k, v in match.items())]
        return len(all_rows)


def _insert(table: str, record: dict[str, Any]) -> None:
    # insert_row handles UPSERT based on identity columns.
    get_kotoba_client().insert_row(table, record)


def _latest_cart(user_did: str) -> dict[str, Any] | None:
    rows = _select(TABLE["cart"], {"user_did": user_did}, limit=1)
    return rows[0] if rows else None


def _cart_items(user_did: str) -> tuple[str, list[dict[str, Any]]]:
    cart = _latest_cart(user_did)
    cart_id = _str(cart.get("cart_id")) if cart else _gid("cart")
    raw = cart.get("items_json") if cart else "[]"
    try:
        items = json.loads(raw) if isinstance(raw, str) else []
    except json.JSONDecodeError:
        items = []
    return cart_id, items if isinstance(items, list) else []


def _upsert_status(table: str, id_field: str, id_value: str, status: str, actor: str, **extra: Any) -> dict[str, Any]:
    if not id_value:
        return {"error": f"{id_field} is required"}
    _insert(table, {id_field: id_value, "status": status, **extra, **_rls(actor)})
    return {"status": status, id_field: id_value}


def task_omise_approve_seller(sellerId: str = "", **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    _insert(TABLE["seller"], {"seller_id": sellerId, "status": "active", "approved_at": _now(), **_rls(A["platformAdmin"])})
    return {"status": "approved", "sellerId": sellerId}


def task_omise_suspend_seller(sellerId: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["seller"], "seller_id", sellerId, "suspended", A["platformAdmin"], suspend_reason=reason or "policy violation", suspended_at=_now())


def task_omise_list_pending_sellers(limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["seller"], {"status": "pending"}, limit=_int(limit, 50), offset=_int(offset, 0))
    return {"sellers": rows, "total": _count(TABLE["seller"], {"status": "pending"}), "offset": _int(offset, 0), "limit": _int(limit, 50)}


def task_omise_resolve_dispute(orderId: str = "", resolution: str = "", refundAmount: Any = 0, **_: Any) -> dict[str, Any]:
    if not orderId or not resolution:
        return {"error": "orderId and resolution are required"}
    _insert(TABLE["dispute"], {"order_id": orderId, "resolution": resolution, "refund_amount": _num(refundAmount), "resolved_at": _now(), **_rls(A["platformSupport"])})
    return {"status": "resolved", "orderId": orderId, "resolution": resolution, "refundAmount": _num(refundAmount)}


def task_omise_register_seller(ownerDid: str = "", storeName: str = "", **args: Any) -> dict[str, Any]:
    if not ownerDid or not storeName:
        return {"error": "ownerDid and storeName are required"}
    seller_id = _gid("seller")
    record = {
        "seller_id": seller_id,
        "owner_did": ownerDid,
        "store_name": storeName,
        "description": _str(args.get("description")),
        "category": _str(args.get("category")) or "general",
        "currency": _str(args.get("currency")) or "JPY",
        "commission_rate": _num(args.get("commissionRate"), 0.1),
        "bank_info": _str(args.get("bankInfo")),
        "status": "pending",
        **_rls(A["sellerOnboarding"]),
    }
    _insert(TABLE["seller"], record)
    return {"status": "pending", "sellerId": seller_id, "record": record}


def task_omise_update_seller_profile(sellerId: str = "", **args: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    record = {"seller_id": sellerId, **_rls(A["sellerOnboarding"])}
    for src, dst in (("storeName", "store_name"), ("description", "description"), ("category", "category"), ("currency", "currency"), ("bankInfo", "bank_info")):
        if src in args:
            record[dst] = _str(args.get(src))
    _insert(TABLE["seller"], record)
    return {"status": "updated", "sellerId": sellerId}


def task_omise_get_seller_profile(sellerId: str = "", **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    rows = _select(TABLE["seller"], {"seller_id": sellerId}, limit=1)
    if not rows:
        return {"error": "not found", "sellerId": sellerId}
    return {"seller": rows[0], "productCount": _count(TABLE["product"], {"seller_id": sellerId, "status": "active"}), "orderCount": _count(TABLE["order"], {"seller_id": sellerId})}


def task_omise_list_sellers(status: str = "active", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    match = {"status": status or "active"}
    return {"sellers": _select(TABLE["seller"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["seller"], match), "offset": _int(offset, 0), "limit": _int(limit, 50)}


def task_omise_create_product(sellerId: str = "", name: str = "", price: Any = 0, **args: Any) -> dict[str, Any]:
    if not sellerId or not name:
        return {"error": "sellerId and name are required"}
    if _num(price) <= 0:
        return {"error": "price must be positive"}
    product_id = _gid("prod")
    record = {
        "product_id": product_id,
        "seller_id": sellerId,
        "name": name,
        "description": _str(args.get("description")),
        "price": _num(price),
        "currency": _str(args.get("currency")) or "JPY",
        "inventory": max(0, _num(args.get("inventory"))),
        "category": _str(args.get("category")) or "general",
        "image_url": _str(args.get("imageUrl")),
        "variants_json": _str(args.get("variantsJson")) or "[]",
        "status": "active",
        **_rls(A["sellerCatalog"]),
    }
    _insert(TABLE["product"], record)
    return {"status": "created", "productId": product_id, "record": record}


def task_omise_update_product(productId: str = "", **args: Any) -> dict[str, Any]:
    if not productId:
        return {"error": "productId is required"}
    record = {"product_id": productId, **_rls(A["sellerCatalog"])}
    for src, dst in (("name", "name"), ("description", "description"), ("price", "price"), ("category", "category"), ("imageUrl", "image_url"), ("variantsJson", "variants_json"), ("status", "status")):
        if src in args:
            record[dst] = _num(args[src]) if src == "price" else _str(args[src])
    _insert(TABLE["product"], record)
    return {"status": "updated", "productId": productId}


def task_omise_archive_product(productId: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["product"], "product_id", productId, "archived", A["sellerCatalog"])


def task_omise_list_seller_products(sellerId: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    match = {"seller_id": sellerId}
    if status:
        match["status"] = status
    return {"products": _select(TABLE["product"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["product"], match), "offset": _int(offset, 0), "limit": _int(limit, 50)}


def task_omise_update_inventory(productId: str = "", inventory: Any = 0, **_: Any) -> dict[str, Any]:
    if not productId:
        return {"error": "productId is required"}
    inv = _num(inventory)
    if inv < 0:
        return {"error": "inventory must be non-negative"}
    _insert(TABLE["product"], {"product_id": productId, "inventory": inv, **_rls(A["sellerCatalog"])})
    return {"status": "updated", "productId": productId, "inventory": inv}


def task_omise_list_seller_orders(sellerId: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    match = {"seller_id": sellerId}
    if status:
        match["status"] = status
    return {"orders": _select(TABLE["order"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["order"], match), "offset": _int(offset, 0), "limit": _int(limit, 50)}


def task_omise_accept_order(orderId: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["order"], "order_id", orderId, "accepted", A["sellerFulfillment"], accepted_at=_now())


def task_omise_reject_order(orderId: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["order"], "order_id", orderId, "rejected", A["sellerFulfillment"], reject_reason=reason or "out of stock", rejected_at=_now())


def task_omise_mark_ready_to_ship(orderId: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["order"], "order_id", orderId, "readyToShip", A["sellerFulfillment"], ready_at=_now())


def task_omise_request_pickup(orderId: str = "", carrier: str = "", pickupDate: str = "", **_: Any) -> dict[str, Any]:
    if not orderId or not carrier:
        return {"error": "orderId and carrier are required"}
    _insert(TABLE["pickup"], {"order_id": orderId, "carrier": carrier, "pickup_date": pickupDate or _now(), "status": "requested", **_rls(A["sellerFulfillment"])})
    return {"status": "requested", "orderId": orderId, "carrier": carrier}


def task_omise_get_seller_balance(sellerId: str = "", **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    orders = _select(TABLE["order"], {"seller_id": sellerId, "status": "completed"}, limit=1000)
    seller = (_select(TABLE["seller"], {"seller_id": sellerId}, limit=1) or [{}])[0]
    rate = _num(seller.get("commission_rate"), 0.1)
    gross = sum(_num(o.get("total_amount")) for o in orders)
    commission = int(gross * rate)
    return {"sellerId": sellerId, "gross": gross, "commission": commission, "net": gross - commission, "currency": _str(seller.get("currency")) or "JPY"}


def task_omise_request_payout(sellerId: str = "", amount: Any = 0, **_: Any) -> dict[str, Any]:
    if not sellerId:
        return {"error": "sellerId is required"}
    payout_id = _gid("payout")
    _insert(TABLE["payout"], {"payout_id": payout_id, "seller_id": sellerId, "amount": _num(amount), "currency": "JPY", "status": "requested", **_rls(A["sellerFinance"])})
    return {"status": "requested", "payoutId": payout_id, "sellerId": sellerId, "amount": _num(amount)}


def task_omise_list_settlements(sellerId: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    match = {"seller_id": sellerId}
    if status:
        match["status"] = status
    return {"settlements": _select(TABLE["settlement"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["settlement"], match)}


def task_omise_get_seller_revenue(sellerId: str = "", **_: Any) -> dict[str, Any]:
    bal = task_omise_get_seller_balance(sellerId)
    if bal.get("error"):
        return bal
    return {"sellerId": sellerId, "orders": _count(TABLE["order"], {"seller_id": sellerId}), "completed": _count(TABLE["order"], {"seller_id": sellerId, "status": "completed"}), "revenue": bal}


def task_omise_create_coupon(sellerId: str = "", code: str = "", discountType: str = "", discountValue: Any = 0, **args: Any) -> dict[str, Any]:
    if not sellerId or not code:
        return {"error": "sellerId and code are required"}
    coupon_id = _gid("coupon")
    record = {"coupon_id": coupon_id, "seller_id": sellerId, "code": code, "discount_type": discountType or "percent", "discount_value": _num(discountValue), "status": "active", "expires_at": _str(args.get("expiresAt")), **_rls(A["sellerMarketing"])}
    _insert(TABLE["coupon"], record)
    return {"status": "created", "couponId": coupon_id, "record": record}


def task_omise_deactivate_coupon(couponId: str = "", **_: Any) -> dict[str, Any]:
    return _upsert_status(TABLE["coupon"], "coupon_id", couponId, "inactive", A["sellerMarketing"])


def task_omise_list_coupons(sellerId: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    match = {"seller_id": sellerId}
    if status:
        match["status"] = status
    return {"coupons": _select(TABLE["coupon"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["coupon"], match)}


def task_omise_apply_coupon(code: str = "", sellerId: str = "", subtotal: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["coupon"], {"code": code, "seller_id": sellerId, "status": "active"}, limit=1)
    if not rows:
        return {"error": "coupon not found or inactive"}
    c = rows[0]
    amount = _num(subtotal)
    value = _num(c.get("discount_value"))
    discount = min(amount, amount * value / 100 if c.get("discount_type") == "percent" else value)
    return {"ok": True, "coupon": c, "discount": discount, "total": amount - discount}


def task_omise_search_products(query: str = "", category: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["product"], {"status": "active"}, limit=_int(limit, 50) * 3, offset=0)
    q = query.lower()
    out = [r for r in rows if (not category or r.get("category") == category) and (not q or q in str(r.get("name", "")).lower() or q in str(r.get("description", "")).lower())]
    off = _int(offset, 0)
    lim = _int(limit, 50)
    return {"products": out[off:off + lim], "total": len(out), "offset": off, "limit": lim}


def task_omise_get_product(productId: str = "", **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["product"], {"product_id": productId}, limit=1)
    if not rows:
        return {"error": "not found", "productId": productId}
    seller = _select(TABLE["seller"], {"seller_id": _str(rows[0].get("seller_id"))}, limit=1)
    return {"product": rows[0], "seller": seller[0] if seller else None}


def task_omise_add_to_cart(userDid: str = "", productId: str = "", quantity: Any = 1, **_: Any) -> dict[str, Any]:
    if not userDid or not productId:
        return {"error": "userDid and productId are required"}
    cart_id, items = _cart_items(userDid)
    qty = max(1, _int(quantity, 1))
    found = False
    for item in items:
        if item.get("product_id") == productId:
            item["quantity"] = _int(item.get("quantity"), 0) + qty
            found = True
    if not found:
        items.append({"product_id": productId, "quantity": qty})
    _insert(TABLE["cart"], {"cart_id": cart_id, "user_did": userDid, "items_json": json.dumps(items, separators=(",", ":")), **_rls(A["buyerAssistant"])})
    return {"status": "added", "cartId": cart_id, "items": items}


def task_omise_remove_from_cart(userDid: str = "", productId: str = "", **_: Any) -> dict[str, Any]:
    if not userDid or not productId:
        return {"error": "userDid and productId are required"}
    cart_id, items = _cart_items(userDid)
    items = [i for i in items if i.get("product_id") != productId]
    _insert(TABLE["cart"], {"cart_id": cart_id, "user_did": userDid, "items_json": json.dumps(items, separators=(",", ":")), **_rls(A["buyerAssistant"])})
    return {"status": "removed", "cartId": cart_id, "items": items}


def task_omise_get_cart(userDid: str = "", **_: Any) -> dict[str, Any]:
    if not userDid:
        return {"error": "userDid is required"}
    cart_id, items = _cart_items(userDid)
    return {"cartId": cart_id, "userDid": userDid, "items": items}


def task_omise_clear_cart(userDid: str = "", **_: Any) -> dict[str, Any]:
    if not userDid:
        return {"error": "userDid is required"}
    cart_id, _ = _cart_items(userDid)
    _insert(TABLE["cart"], {"cart_id": cart_id, "user_did": userDid, "items_json": "[]", **_rls(A["buyerAssistant"])})
    return {"status": "cleared", "cartId": cart_id}


def task_omise_create_order(userDid: str = "", shippingAddress: str = "", paymentMethod: str = "", **_: Any) -> dict[str, Any]:
    if not userDid:
        return {"error": "userDid is required"}
    cart_id, items = _cart_items(userDid)
    if not items:
        return {"error": "cart is empty"}
    orders = []
    by_seller: dict[str, list[dict[str, Any]]] = {}
    products: dict[str, dict[str, Any]] = {}
    for item in items:
        product_id = _str(item.get("product_id"))
        prod = (_select(TABLE["product"], {"product_id": product_id, "status": "active"}, limit=1) or [{}])[0]
        if not prod:
            return {"error": "product not found", "productId": product_id}
        products[product_id] = prod
        by_seller.setdefault(_str(prod.get("seller_id")), []).append(item)
    for seller_id, seller_items in by_seller.items():
        order_id = _gid("order")
        subtotal = sum(_num(products[_str(i.get("product_id"))].get("price")) * max(1, _int(i.get("quantity"), 1)) for i in seller_items)
        record = {"order_id": order_id, "seller_id": seller_id, "user_did": userDid, "items_json": json.dumps(seller_items, separators=(",", ":")), "subtotal": subtotal, "discount": 0, "total_amount": subtotal, "currency": "JPY", "status": "paymentPending", "payment_method": paymentMethod, "shipping_address": shippingAddress, **_rls(A["buyerAssistant"])}
        _insert(TABLE["order"], record)
        orders.append(record)
    _insert(TABLE["cart"], {"cart_id": cart_id, "user_did": userDid, "items_json": "[]", **_rls(A["buyerAssistant"])})
    return {"status": "created", "orders": orders}


def task_omise_get_order(orderId: str = "", **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["order"], {"order_id": orderId}, limit=1)
    return {"order": rows[0]} if rows else {"error": "not found", "orderId": orderId}


def task_omise_list_orders(userDid: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    match = {"user_did": userDid}
    if status:
        match["status"] = status
    return {"orders": _select(TABLE["order"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["order"], match)}


def task_omise_submit_review(userDid: str = "", productId: str = "", rating: Any = 0, comment: str = "", **_: Any) -> dict[str, Any]:
    if not userDid or not productId:
        return {"error": "userDid and productId are required"}
    review_id = _gid("review")
    _insert(TABLE["review"], {"review_id": review_id, "product_id": productId, "user_did": userDid, "rating": max(1, min(5, _int(rating, 5))), "comment": comment, "status": "published", **_rls(A["buyerReview"])})
    return {"status": "published", "reviewId": review_id}


def task_omise_list_reviews(productId: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    return {"reviews": _select(TABLE["review"], {"product_id": productId}, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["review"], {"product_id": productId})}


def task_omise_create_shipment(orderId: str = "", carrier: str = "", trackingNumber: str = "", **_: Any) -> dict[str, Any]:
    if not orderId or not carrier:
        return {"error": "orderId and carrier are required"}
    order = (_select(TABLE["order"], {"order_id": orderId}, limit=1) or [{}])[0]
    shipment_id = _gid("ship")
    _insert(TABLE["shipment"], {"shipment_id": shipment_id, "order_id": orderId, "seller_id": _str(order.get("seller_id")), "carrier": carrier, "tracking_number": trackingNumber, "status": "preparing", **_rls(A["logistics"])})
    return {"status": "created", "shipmentId": shipment_id}


def task_omise_update_shipment_status(shipmentId: str = "", status: str = "", trackingNumber: str = "", **_: Any) -> dict[str, Any]:
    if not shipmentId or not status:
        return {"error": "shipmentId and status are required"}
    record = {"shipment_id": shipmentId, "status": status, **_rls(A["logistics"])}
    if trackingNumber:
        record["tracking_number"] = trackingNumber
    _insert(TABLE["shipment"], record)
    return {"status": "updated", "shipmentId": shipmentId, "newStatus": status}


def task_omise_get_shipment(shipmentId: str = "", **_: Any) -> dict[str, Any]:
    rows = _select(TABLE["shipment"], {"shipment_id": shipmentId}, limit=1)
    return {"shipment": rows[0]} if rows else {"error": "not found", "shipmentId": shipmentId}


def task_omise_list_shipments(orderId: str = "", sellerId: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    match = {"order_id": orderId, "seller_id": sellerId}
    if status:
        match["status"] = status
    return {"shipments": _select(TABLE["shipment"], match, limit=_int(limit, 50), offset=_int(offset, 0)), "total": _count(TABLE["shipment"], match)}


def task_omise_platform_analytics(**_: Any) -> dict[str, Any]:
    return {
        "sellers": {"active": _count(TABLE["seller"], {"status": "active"}), "pending": _count(TABLE["seller"], {"status": "pending"})},
        "products": _count(TABLE["product"], {"status": "active"}),
        "orders": {"total": _count(TABLE["order"], {}), "pending": _count(TABLE["order"], {"status": "paymentPending"}), "confirmed": _count(TABLE["order"], {"status": "confirmed"}), "completed": _count(TABLE["order"], {"status": "completed"})},
        "shipments": _count(TABLE["shipment"], {}),
        "reviews": _count(TABLE["review"], {}),
        "activeCoupons": _count(TABLE["coupon"], {"status": "active"}),
        "generatedAt": _now(),
    }


def task_omise_card_home(**_: Any) -> dict[str, Any]:
    return {
        "contentType": "application/vnd.etzhayyim.card.list",
        "payload": {
            "title": "Omise Marketplace",
            "items": [
                {"id": "sellers", "label": "Sellers", "sublabel": f"{_count(TABLE['seller'], {'status': 'active'})} active", "icon": "storefront", "action": "omise.listSellers"},
                {"id": "products", "label": "Products", "sublabel": f"{_count(TABLE['product'], {'status': 'active'})} listed", "icon": "package", "action": "omise.searchProducts"},
                {"id": "orders", "label": "Orders", "sublabel": f"{_count(TABLE['order'], {})} total", "icon": "receipt", "action": "omise.platformAnalytics"},
                {"id": "sell", "label": "Start Selling", "sublabel": "Register as seller", "icon": "plus-circle", "action": "omise.registerSeller"},
            ],
        },
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.omise.acceptOrder": task_omise_accept_order,
        "xrpc.com.etzhayyim.apps.omise.addToCart": task_omise_add_to_cart,
        "xrpc.com.etzhayyim.apps.omise.applyCoupon": task_omise_apply_coupon,
        "xrpc.com.etzhayyim.apps.omise.approveSeller": task_omise_approve_seller,
        "xrpc.com.etzhayyim.apps.omise.archiveProduct": task_omise_archive_product,
        "xrpc.com.etzhayyim.apps.omise.cardHome": task_omise_card_home,
        "xrpc.com.etzhayyim.apps.omise.clearCart": task_omise_clear_cart,
        "xrpc.com.etzhayyim.apps.omise.createCoupon": task_omise_create_coupon,
        "xrpc.com.etzhayyim.apps.omise.createOrder": task_omise_create_order,
        "xrpc.com.etzhayyim.apps.omise.createProduct": task_omise_create_product,
        "xrpc.com.etzhayyim.apps.omise.createShipment": task_omise_create_shipment,
        "xrpc.com.etzhayyim.apps.omise.deactivateCoupon": task_omise_deactivate_coupon,
        "xrpc.com.etzhayyim.apps.omise.getCart": task_omise_get_cart,
        "xrpc.com.etzhayyim.apps.omise.getOrder": task_omise_get_order,
        "xrpc.com.etzhayyim.apps.omise.getProduct": task_omise_get_product,
        "xrpc.com.etzhayyim.apps.omise.getSellerBalance": task_omise_get_seller_balance,
        "xrpc.com.etzhayyim.apps.omise.getSellerProfile": task_omise_get_seller_profile,
        "xrpc.com.etzhayyim.apps.omise.getSellerRevenue": task_omise_get_seller_revenue,
        "xrpc.com.etzhayyim.apps.omise.getShipment": task_omise_get_shipment,
        "xrpc.com.etzhayyim.apps.omise.listCoupons": task_omise_list_coupons,
        "xrpc.com.etzhayyim.apps.omise.listOrders": task_omise_list_orders,
        "xrpc.com.etzhayyim.apps.omise.listPendingSellers": task_omise_list_pending_sellers,
        "xrpc.com.etzhayyim.apps.omise.listReviews": task_omise_list_reviews,
        "xrpc.com.etzhayyim.apps.omise.listSellerOrders": task_omise_list_seller_orders,
        "xrpc.com.etzhayyim.apps.omise.listSellerProducts": task_omise_list_seller_products,
        "xrpc.com.etzhayyim.apps.omise.listSellers": task_omise_list_sellers,
        "xrpc.com.etzhayyim.apps.omise.listSettlements": task_omise_list_settlements,
        "xrpc.com.etzhayyim.apps.omise.listShipments": task_omise_list_shipments,
        "xrpc.com.etzhayyim.apps.omise.markReadyToShip": task_omise_mark_ready_to_ship,
        "xrpc.com.etzhayyim.apps.omise.platformAnalytics": task_omise_platform_analytics,
        "xrpc.com.etzhayyim.apps.omise.registerSeller": task_omise_register_seller,
        "xrpc.com.etzhayyim.apps.omise.rejectOrder": task_omise_reject_order,
        "xrpc.com.etzhayyim.apps.omise.removeFromCart": task_omise_remove_from_cart,
        "xrpc.com.etzhayyim.apps.omise.requestPayout": task_omise_request_payout,
        "xrpc.com.etzhayyim.apps.omise.requestPickup": task_omise_request_pickup,
        "xrpc.com.etzhayyim.apps.omise.resolveDispute": task_omise_resolve_dispute,
        "xrpc.com.etzhayyim.apps.omise.searchProducts": task_omise_search_products,
        "xrpc.com.etzhayyim.apps.omise.submitReview": task_omise_submit_review,
        "xrpc.com.etzhayyim.apps.omise.suspendSeller": task_omise_suspend_seller,
        "xrpc.com.etzhayyim.apps.omise.updateInventory": task_omise_update_inventory,
        "xrpc.com.etzhayyim.apps.omise.updateProduct": task_omise_update_product,
        "xrpc.com.etzhayyim.apps.omise.updateSellerProfile": task_omise_update_seller_profile,
        "xrpc.com.etzhayyim.apps.omise.updateShipmentStatus": task_omise_update_shipment_status,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
