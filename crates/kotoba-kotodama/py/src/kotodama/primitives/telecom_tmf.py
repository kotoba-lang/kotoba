"""telecom Phase 17 primitives — TM Forum Open APIs.

Eight BPMN service tasks covering the full TMF Open API suite:

  - telecom.tmf.product.offering   (TMF620 Product Catalog)
  - telecom.tmf.product.order      (TMF622 Product Ordering)
  - telecom.tmf.product.inventory  (TMF637 Product Inventory)
  - telecom.tmf.service.order      (TMF641 Service Ordering)
  - telecom.tmf.service.activate   (TMF640 Service Activation)
  - telecom.tmf.service.inventory  (TMF638 Service Inventory)
  - telecom.tmf.account.register   (TMF666 Account Management)  ← PII hashed
  - telecom.tmf.bill.issue         (TMF678 Customer Bill)

PII discipline (TMF666):
  partyName / partyContact / partyTaxId / billingAddress → sha256: hashed
  (sensitivity_ord=2 for account; bill rows are sensitivity_ord=2)
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.tmf"

LIFECYCLE_STATUS_PRODUCT_OFFERING = {
    "In Study", "In Design", "In Test", "Active", "Launched",
    "Retired", "Obsolete", "Rejected",
}
LIFECYCLE_STATUS_PRODUCT_ORDER = {
    "acknowledged", "rejected", "pending", "held",
    "inProgress", "cancelled", "completed", "failed", "partial",
}
LIFECYCLE_STATUS_PRODUCT_INVENTORY = {
    "Created", "Pending Active", "Pending Terminate",
    "Active", "Suspended", "Terminated", "Aborted",
}
LIFECYCLE_STATUS_SERVICE_ORDER = {
    "acknowledged", "rejected", "pending", "held",
    "inProgress", "cancelled", "completed", "failed", "partial",
}
LIFECYCLE_STATUS_SERVICE_INVENTORY = {
    "feasibilityChecked", "designed", "reserved",
    "inactive", "active", "terminated",
}
ORDER_KINDS_PRODUCT = {"add", "modify", "suspend", "resume", "terminate"}
ORDER_KINDS_SERVICE = {"add", "modify", "delete", "noChange"}
CUSTOMER_KINDS = {"individual", "organization"}
ACCOUNT_KINDS = {"prepaid", "postpaid", "hybrid"}
PAYMENT_METHOD_KINDS = {"bankTransfer", "creditCard", "directDebit", "electronicCheck", "token"}
DELIVERY_CHANNELS = {"email", "post", "portal", "api"}
ACTIVATION_ACTIONS = {"activate", "deactivate", "configure", "test", "reconfigure"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_hex(10)}"


def _vid(kind: str, key: str) -> str:
    return f"at://{TELECOM_DID}/com.etzhayyim.apps.telecom.{kind}/{key}"


def _hash_pii(value: str | None) -> str | None:
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _join(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ",".join(items) if items else None
    text = str(value).strip()
    return text or None


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


# ─── TMF620: publishProductOffering ──────────────────────────────────────────

def handle_publish_product_offering(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["offeringId", "name", "lifecycleStatus"])

    offering_id = payload["offeringId"]
    lifecycle = payload["lifecycleStatus"]
    if lifecycle not in LIFECYCLE_STATUS_PRODUCT_OFFERING:
        lifecycle = "Active"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("productOffering", offering_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_product_offering", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "offering_id": offering_id,
        "name": payload['name'],
        "description": payload.get('description'),
        "lifecycle_status": lifecycle,
        "product_spec_id": payload.get('productSpecId'),
        "category_ids": _join(payload.get('categoryIds')),
        "channel_ids": _join(payload.get('channelIds')),
        "market_ids": _join(payload.get('marketIds')),
        "price_ref": payload.get('priceRef'),
        "valid_from_at": payload.get('validFromAt'),
        "valid_to_at": payload.get('validToAt'),
        "observed_at": observed_at,
        "status": 'active',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "offeringId": offering_id, "status": "active"}


# ─── TMF622: submitProductOrder ──────────────────────────────────────────────

def handle_submit_product_order(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["productOrderId", "accountId", "orderKind"])

    order_id = payload["productOrderId"]
    order_kind = payload["orderKind"]
    if order_kind not in ORDER_KINDS_PRODUCT:
        order_kind = "add"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("productOrder", order_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_product_order", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "product_order_id": order_id,
        "account_id": payload['accountId'],
        "order_kind": order_kind,
        "offering_id": payload.get('offeringId'),
        "product_id": payload.get('productId'),
        "order_item_hash": payload.get('orderItemHash'),
        "order_item_ref": payload.get('orderItemRef'),
        "requested_start_at": payload.get('requestedStartAt'),
        "requested_completion_at": payload.get('requestedCompletionAt'),
        "priority": payload.get('priority'),
        "channel_id": payload.get('channelId'),
        "observed_at": observed_at,
        "status": 'acknowledged',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "productOrderId": order_id, "status": "acknowledged"}


# ─── TMF637: recordProductInventoryItem ──────────────────────────────────────

def handle_record_product_inventory_item(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["recordId", "productId", "accountId", "lifecycleStatus"])

    record_id = payload["recordId"]
    lifecycle = payload["lifecycleStatus"]
    if lifecycle not in LIFECYCLE_STATUS_PRODUCT_INVENTORY:
        lifecycle = "Active"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("productInventory", record_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_product_inventory", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "record_id": record_id,
        "product_id": payload['productId'],
        "account_id": payload['accountId'],
        "offering_id": payload.get('offeringId'),
        "product_order_id": payload.get('productOrderId'),
        "lifecycle_status": lifecycle,
        "started_at": payload.get('startedAt'),
        "terminated_at": payload.get('terminatedAt'),
        "observed_at": observed_at,
        "status": 'recorded',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "recordId": record_id, "status": "recorded"}


# ─── TMF641: submitServiceOrder ──────────────────────────────────────────────

def handle_submit_service_order(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["serviceOrderId", "productOrderId", "orderKind"])

    svc_order_id = payload["serviceOrderId"]
    order_kind = payload["orderKind"]
    if order_kind not in ORDER_KINDS_SERVICE:
        order_kind = "add"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("serviceOrder", svc_order_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_service_order", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "service_order_id": svc_order_id,
        "product_order_id": payload['productOrderId'],
        "product_id": payload.get('productId'),
        "service_spec": payload.get('serviceSpec'),
        "order_kind": order_kind,
        "order_item_hash": payload.get('orderItemHash'),
        "order_item_ref": payload.get('orderItemRef'),
        "requested_start_at": payload.get('requestedStartAt'),
        "requested_completion_at": payload.get('requestedCompletionAt'),
        "observed_at": observed_at,
        "status": 'acknowledged',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "serviceOrderId": svc_order_id, "status": "acknowledged"}


# ─── TMF640: activateServiceInstance ─────────────────────────────────────────

def handle_activate_service_instance(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["activationId", "serviceOrderId", "serviceInstanceKind", "action"])

    act_id = payload["activationId"]
    action = payload["action"]
    if action not in ACTIVATION_ACTIONS:
        action = "activate"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("serviceActivation", act_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_service_activation", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "activation_id": act_id,
        "service_order_id": payload['serviceOrderId'],
        "service_instance_kind": payload['serviceInstanceKind'],
        "service_instance_vid": payload.get('serviceInstanceVid'),
        "action": action,
        "configuration_hash": payload.get('configurationHash'),
        "configuration_ref": payload.get('configurationRef'),
        "observed_at": observed_at,
        "status": 'completed',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "activationId": act_id, "status": "completed"}


# ─── TMF638: recordServiceInventoryItem ──────────────────────────────────────

def handle_record_service_inventory_item(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["recordId", "serviceInstanceKind", "lifecycleStatus"])

    record_id = payload["recordId"]
    lifecycle = payload["lifecycleStatus"]
    if lifecycle not in LIFECYCLE_STATUS_SERVICE_INVENTORY:
        lifecycle = "active"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("serviceInventory", record_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_service_inventory", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "record_id": record_id,
        "service_instance_kind": payload['serviceInstanceKind'],
        "service_instance_vid": payload.get('serviceInstanceVid'),
        "product_id": payload.get('productId'),
        "service_order_id": payload.get('serviceOrderId'),
        "lifecycle_status": lifecycle,
        "operational_state": payload.get('operationalState'),
        "started_at": payload.get('startedAt'),
        "observed_at": observed_at,
        "status": 'recorded',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "recordId": record_id, "status": "recorded"}


# ─── TMF666: registerCustomerAccount ─────────────────────────────────────────

def handle_register_customer_account(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["accountId", "customerKind", "accountKind"])

    account_id = payload["accountId"]
    customer_kind = payload["customerKind"]
    if customer_kind not in CUSTOMER_KINDS:
        customer_kind = "individual"
    account_kind = payload["accountKind"]
    if account_kind not in ACCOUNT_KINDS:
        account_kind = "postpaid"

    payment_kind = payload.get("paymentMethodKind")
    if payment_kind and payment_kind not in PAYMENT_METHOD_KINDS:
        payment_kind = None

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("customerAccount", account_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_customer_account", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "account_id": account_id,
        "customer_kind": customer_kind,
        "account_kind": account_kind,
        "party_name": _hash_pii(payload.get('partyName')),
        "party_contact": _hash_pii(payload.get('partyContact')),
        "party_tax_id": _hash_pii(payload.get('partyTaxId')),
        "billing_address": _hash_pii(payload.get('billingAddress')),
        "currency": payload.get('currency'),
        "payment_method_kind": payment_kind,
        "payment_method_ref": payload.get('paymentMethodRef'),
        "parent_subscriber_id": payload.get('parentSubscriberId'),
        "jurisdiction": payload.get('jurisdiction'),
        "observed_at": observed_at,
        "status": 'active',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "accountId": account_id, "status": "active"}


# ─── TMF678: issueCustomerBill ────────────────────────────────────────────────

def handle_issue_customer_bill(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["billId", "accountId", "periodStart", "periodEnd"])

    bill_id = payload["billId"]
    delivery = payload.get("deliveryChannel")
    if delivery and delivery not in DELIVERY_CHANNELS:
        delivery = "portal"

    # total_amount is computed by the downstream billing engine; default 0.0 for skeleton
    total_amount: float = payload.get("totalAmount", 0.0)
    created_at = _now_iso()
    vertex_id = _vid("customerBill", bill_id)

    get_kotoba_client().insert_row("vertex_telecom_tmf_customer_bill", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "bill_id": bill_id,
        "account_id": payload['accountId'],
        "period_start": payload['periodStart'],
        "period_end": payload['periodEnd'],
        "currency": payload.get('currency'),
        "source_invoice_vids": _join(payload.get('sourceInvoiceVids')),
        "due_at": payload.get('dueAt'),
        "delivery_channel": delivery,
        "bill_document_ref": payload.get('billDocumentRef'),
        "total_amount": total_amount,
        "status": 'issued',
        "created_at": created_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {
        "vertexId": vertex_id,
        "billId": bill_id,
        "totalAmount": total_amount,
        "status": "issued",
    }


# ─── Worker registration ──────────────────────────────────────────────────────

def register(worker: Any, timeout_ms: int = 30_000) -> None:
    @worker.task(task_type="telecom.tmf.product.offering", timeout_ms=timeout_ms)
    def _offering(payload: dict) -> dict:
        return handle_publish_product_offering(payload)

    @worker.task(task_type="telecom.tmf.product.order", timeout_ms=timeout_ms)
    def _product_order(payload: dict) -> dict:
        return handle_submit_product_order(payload)

    @worker.task(task_type="telecom.tmf.product.inventory", timeout_ms=timeout_ms)
    def _product_inventory(payload: dict) -> dict:
        return handle_record_product_inventory_item(payload)

    @worker.task(task_type="telecom.tmf.service.order", timeout_ms=timeout_ms)
    def _service_order(payload: dict) -> dict:
        return handle_submit_service_order(payload)

    @worker.task(task_type="telecom.tmf.service.activate", timeout_ms=timeout_ms)
    def _activate(payload: dict) -> dict:
        return handle_activate_service_instance(payload)

    @worker.task(task_type="telecom.tmf.service.inventory", timeout_ms=timeout_ms)
    def _service_inventory(payload: dict) -> dict:
        return handle_record_service_inventory_item(payload)

    @worker.task(task_type="telecom.tmf.account.register", timeout_ms=timeout_ms)
    def _account(payload: dict) -> dict:
        return handle_register_customer_account(payload)

    @worker.task(task_type="telecom.tmf.bill.issue", timeout_ms=60_000)
    def _bill(payload: dict) -> dict:
        return handle_issue_customer_bill(payload)
