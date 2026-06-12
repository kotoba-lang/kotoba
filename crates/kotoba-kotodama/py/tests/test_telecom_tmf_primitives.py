"""Tests for telecom_tmf primitives (TM Forum Open APIs)."""

from __future__ import annotations

import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_tmf as TM  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_db():
    """Stub sync_cursor so tests don't need a real DB connection."""
    with patch("kotodama.primitives.telecom_tmf.sync_cursor") as m:
        m.return_value.__enter__ = MagicMock(return_value=MagicMock())
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield


# ─── telecom.tmf.product.offering ────────────────────────────────────────

def test_product_offering_returns_active():
    out = TM.handle_publish_product_offering({
        "offeringId": "offer_001", "name": "5G Unlimited",
        "lifecycleStatus": "Active",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "active"
    assert out["offeringId"] == "offer_001"
    assert out["vertexId"].startswith("at://")


def test_product_offering_defaults_invalid_lifecycle():
    out = TM.handle_publish_product_offering({
        "offeringId": "offer_002", "name": "4G Basic",
        "lifecycleStatus": "Draft",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "active"


def test_product_offering_raises_on_missing_fields():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_publish_product_offering({"name": "No ID"})


# ─── telecom.tmf.product.order ───────────────────────────────────────────

def test_product_order_returns_acknowledged():
    out = TM.handle_submit_product_order({
        "productOrderId": "po_001", "accountId": "acct_001",
        "orderKind": "add",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "acknowledged"
    assert out["productOrderId"] == "po_001"


def test_product_order_defaults_invalid_order_kind():
    out = TM.handle_submit_product_order({
        "productOrderId": "po_002", "accountId": "acct_001",
        "orderKind": "upgrade",
    })
    assert out["status"] == "acknowledged"


def test_product_order_raises_on_missing_account_id():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_submit_product_order({
            "productOrderId": "po_003", "orderKind": "add",
        })


# ─── telecom.tmf.product.inventory ───────────────────────────────────────

def test_product_inventory_returns_recorded():
    out = TM.handle_record_product_inventory_item({
        "recordId": "inv_001", "productId": "prod_001",
        "accountId": "acct_001", "lifecycleStatus": "Active",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "recorded"
    assert out["recordId"] == "inv_001"


def test_product_inventory_defaults_invalid_lifecycle():
    out = TM.handle_record_product_inventory_item({
        "recordId": "inv_002", "productId": "prod_001",
        "accountId": "acct_001", "lifecycleStatus": "Unknown",
    })
    assert out["status"] == "recorded"


def test_product_inventory_raises_on_missing_product_id():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_record_product_inventory_item({
            "recordId": "inv_003", "accountId": "acct_001",
            "lifecycleStatus": "Active",
        })


# ─── telecom.tmf.service.order ───────────────────────────────────────────

def test_service_order_returns_acknowledged():
    out = TM.handle_submit_service_order({
        "serviceOrderId": "so_001", "productOrderId": "po_001",
        "orderKind": "add",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "acknowledged"
    assert out["serviceOrderId"] == "so_001"


def test_service_order_defaults_invalid_order_kind():
    out = TM.handle_submit_service_order({
        "serviceOrderId": "so_002", "productOrderId": "po_001",
        "orderKind": "upgrade",
    })
    assert out["status"] == "acknowledged"


def test_service_order_raises_on_missing_product_order_id():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_submit_service_order({
            "serviceOrderId": "so_003", "orderKind": "add",
        })


# ─── telecom.tmf.service.activate ────────────────────────────────────────

def test_service_activate_returns_completed():
    out = TM.handle_activate_service_instance({
        "activationId": "act_001", "serviceOrderId": "so_001",
        "serviceInstanceKind": "mobile_voice", "action": "activate",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "completed"
    assert out["activationId"] == "act_001"


def test_service_activate_defaults_invalid_action():
    out = TM.handle_activate_service_instance({
        "activationId": "act_002", "serviceOrderId": "so_001",
        "serviceInstanceKind": "mobile_data", "action": "provision",
    })
    assert out["status"] == "completed"


def test_service_activate_raises_on_missing_service_instance_kind():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_activate_service_instance({
            "activationId": "act_003", "serviceOrderId": "so_001",
            "action": "activate",
        })


# ─── telecom.tmf.service.inventory ───────────────────────────────────────

def test_service_inventory_returns_recorded():
    out = TM.handle_record_service_inventory_item({
        "recordId": "sinv_001",
        "serviceInstanceKind": "broadband",
        "lifecycleStatus": "active",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "recorded"
    assert out["recordId"] == "sinv_001"


def test_service_inventory_defaults_invalid_lifecycle():
    out = TM.handle_record_service_inventory_item({
        "recordId": "sinv_002",
        "serviceInstanceKind": "iot",
        "lifecycleStatus": "unknown",
    })
    assert out["status"] == "recorded"


def test_service_inventory_raises_on_missing_service_instance_kind():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_record_service_inventory_item({
            "recordId": "sinv_003", "lifecycleStatus": "active",
        })


# ─── telecom.tmf.account.register ────────────────────────────────────────

def test_account_register_returns_active():
    out = TM.handle_register_customer_account({
        "accountId": "acct_001", "customerKind": "individual",
        "accountKind": "postpaid",
        "observedAt": "2026-04-29T10:00:00Z",
    })
    assert out["status"] == "active"
    assert out["accountId"] == "acct_001"


def test_account_register_defaults_invalid_customer_kind():
    out = TM.handle_register_customer_account({
        "accountId": "acct_002", "customerKind": "corporation",
        "accountKind": "prepaid",
    })
    assert out["status"] == "active"


def test_account_register_defaults_invalid_payment_method():
    out = TM.handle_register_customer_account({
        "accountId": "acct_003", "customerKind": "organization",
        "accountKind": "hybrid",
        "paymentMethodKind": "crypto",
    })
    assert out["status"] == "active"


def test_account_register_raises_on_missing_account_kind():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_register_customer_account({
            "accountId": "acct_004", "customerKind": "individual",
        })


# ─── telecom.tmf.bill.issue ──────────────────────────────────────────────

def test_bill_issue_returns_issued():
    out = TM.handle_issue_customer_bill({
        "billId": "bill_001", "accountId": "acct_001",
        "periodStart": "2026-04-01", "periodEnd": "2026-04-30",
        "currency": "JPY", "totalAmount": 9800.0,
    })
    assert out["status"] == "issued"
    assert out["billId"] == "bill_001"
    assert out["totalAmount"] == 9800.0


def test_bill_issue_defaults_invalid_delivery_channel():
    out = TM.handle_issue_customer_bill({
        "billId": "bill_002", "accountId": "acct_001",
        "periodStart": "2026-04-01", "periodEnd": "2026-04-30",
        "deliveryChannel": "fax",
    })
    assert out["status"] == "issued"


def test_bill_issue_raises_on_missing_period():
    with pytest.raises(ValueError, match="Missing required fields"):
        TM.handle_issue_customer_bill({
            "billId": "bill_003", "accountId": "acct_001",
            "periodStart": "2026-04-01",
        })


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    TM.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.tmf.product.offering",
        "telecom.tmf.product.order",
        "telecom.tmf.product.inventory",
        "telecom.tmf.service.order",
        "telecom.tmf.service.activate",
        "telecom.tmf.service.inventory",
        "telecom.tmf.account.register",
        "telecom.tmf.bill.issue",
    }
