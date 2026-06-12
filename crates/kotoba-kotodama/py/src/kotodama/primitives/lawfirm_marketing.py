"""
lawfirm.* — LangServer handlers for marketing dispatch + Stripe webhook.

Task types:
  lawfirm.marketing.submit       Submit to LangGraph lawfirm-marketing-ops
  lawfirm.payment.stripeWebhook  Verify + persist Stripe event

ADR-2605080600 LangGraph Server L3.
ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import datetime as _dt
import hmac
import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.primitives")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")


def _vid(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


# ── Marketing dispatch (LangGraph submit) ──────────────────────────────────────

async def task_lawfirm_marketing_submit(
    task_type: str = "marketing.kpiReport",
    brand: str = "advocate",
    audience: str = "",
    topic: str = "",
    payload: str = "",
    schedule_at: str = "",
    requester_did: str = "",
) -> dict:
    """Run lawfirm marketing LangGraph in-process."""
    import asyncio

    thread_id = f"lawfirm-mkt-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

    def _run() -> dict:
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import build_graph
        graph = build_graph()
        state_in = {
            "task_type":     task_type,
            "brand":         brand,
            "audience":      audience,
            "topic":         topic,
            "payload":       payload,
            "schedule_at":   schedule_at,
            "requester_did": requester_did,
            "thread_id":     thread_id,
        }
        return dict(graph.invoke(state_in))

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
    except Exception as exc:
        LOG.error("lawfirm.marketing.submit failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    return {
        "ok":               True,
        "asset_uris":       result.get("asset_uris", []),
        "compliance_check": result.get("compliance_check", "skipped"),
        "compliance_notes": result.get("compliance_notes", ""),
        "summary":          result.get("summary", ""),
    }


# ── Stripe webhook handler ────────────────────────────────────────────────────

def _verify_stripe_signature(payload_str: str, sig_header: str, secret: str) -> bool:
    """RFC: Stripe-Signature: t=<ts>,v1=<hex_sig>"""
    if not sig_header or not secret:
        return False
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(","))
        ts = parts.get("t", "")
        sig = parts.get("v1", "")
        if not ts or not sig:
            return False
        signed = f"{ts}.{payload_str}".encode()
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


async def task_lawfirm_payment_stripe_webhook(
    event_id: str = "",
    type: str = "",
    livemode: bool = False,
    stripe_account: str = "",
    data: str = "",
    signature_header: str = "",
) -> dict:
    """Verify Stripe webhook + persist invoice/payment row."""
    secret_in = os.environ.get("STRIPE_WEBHOOK_SECRET_IN", "")
    secret_us = os.environ.get("STRIPE_WEBHOOK_SECRET_US", "")
    secret = secret_us if "US" in stripe_account.upper() else secret_in

    if secret and signature_header:
        if not _verify_stripe_signature(data, signature_header, secret):
            LOG.warning("Stripe signature mismatch event_id=%s", event_id)
            return {"ok": False, "error": "signature_mismatch"}

    try:
        evt = json.loads(data) if isinstance(data, str) else data
    except Exception as exc:
        return {"ok": False, "error": f"data_parse_failed: {exc}"}

    matter_uri = ""
    amount_minor = 0
    currency = "USD"

    try:



        if type in ("invoice.paid", "invoice.payment_succeeded", "invoice.created", "invoice.finalized"):
            inv = evt.get("object") or evt
            stripe_invoice_id = str(inv.get("id", ""))
            amount_minor = int(inv.get("amount_paid") or inv.get("amount_due") or 0)
            currency = str(inv.get("currency", "usd")).upper()
            metadata = inv.get("metadata") or {}
            matter_uri = str(metadata.get("matter_uri", ""))
            stream = str(metadata.get("stream", "advocate-fee"))
            paid_at = _now_iso() if type == "invoice.paid" else ""
            get_kotoba_client().insert_row(
                "vertex_lawfirm_invoice",
                {
                    "vertex_id":    _vid("invoice"),
                    "stripe_invoice_id":    stripe_invoice_id,
                    "matter_uri":   matter_uri,
                    "client_did":   str(metadata.get("client_did", "")),
                    "stream": stream,
                    "amount_minor":    amount_minor,
                    "currency":    currency,
                    "total_minor":    int(inv.get("total") or amount_minor),
                    "status": "paid" if type == "invoice.paid" else "open",
                    "issued_at": _now_iso(),
                    "paid_at":   paid_at,
                    "hosted_invoice_url":    str(inv.get("hosted_invoice_url", "")),
                    "raw_json":    json.dumps(evt, ensure_ascii=False)[:60_000],
                    "created_at":    _now_iso(),
                    "owner_did":  _FIRM_DID,
                },
            )

        elif type in ("charge.succeeded", "payment_intent.succeeded"):
            ch = evt.get("object") or evt
            stripe_charge_id = str(ch.get("id", ""))
            amount_minor = int(ch.get("amount_received") or ch.get("amount") or 0)
            currency = str(ch.get("currency", "usd")).upper()
            metadata = ch.get("metadata") or {}
            matter_uri = str(metadata.get("matter_uri", ""))
            stream = str(metadata.get("stream", "advocate-fee"))
            get_kotoba_client().insert_row(
                "vertex_lawfirm_payment",
                {
                    "vertex_id":     _vid("payment"),
                    "stripe_charge_id":     stripe_charge_id,
                    "stripe_invoice_id":     str(ch.get("invoice", "")),
                    "matter_uri":    matter_uri,
                    "client_did":    str(metadata.get("client_did", "")),
                    "stream":  stream,
                    "amount_minor":     amount_minor,
                    "currency":     currency,
                    "paid_at":    _now_iso(),
                    "receipt_url": str(ch.get("receipt_url", "")),
                    "payment_method":      str(ch.get("payment_method_details", {}).get("type", "")),
                    "raw_json":     json.dumps(evt, ensure_ascii=False)[:60_000],
                    "created_at":     _now_iso(),
                    "owner_did":   _FIRM_DID,
                },
            )

        else:
            LOG.info("Stripe event %s ignored (no handler)", type)
            return {"ok": True, "matter_uri": "", "amount_minor": 0, "currency": currency}

    except Exception as exc:
        LOG.error("Stripe persist failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    # Delegate to tenant-centric handler for SaaS subscription invoices
    # (Mode A flat / Mode B rev-share). Matter-centric path above handles
    # advocate-fee invoices; this delegation handles the W11-W12 conversion
    # path (vertex_lawfirm_tenant.stripe_customer_id → lead.stage='paid').
    # Idempotent on (event_id, customer_id) — safe even when the same event
    # produced both a matter-level and a tenant-level row.
    tenant_result: dict = {}
    if type == "invoice.paid":
        try:
            from kotodama.primitives.lawfirm_billing import (
                task_billing_process_webhook_invoice_paid,
            )
            inv = (evt.get("object") or evt) if isinstance(evt, dict) else {}
            customer_id = str(inv.get("customer", ""))
            if customer_id:
                tenant_result = await task_billing_process_webhook_invoice_paid(
                    event_id=str(event_id),
                    invoice_id=str(inv.get("id", "")),
                    subscription_id=str(inv.get("subscription", "")),
                    customer_id=customer_id,
                    amount_paid_minor=int(inv.get("amount_paid") or 0),
                    currency=str(inv.get("currency", "usd")),
                    application_fee_minor=int(inv.get("application_fee_amount") or 0),
                    paid_at_unix=int(inv.get("status_transitions", {}).get("paid_at") or 0),
                )
        except Exception as exc:
            LOG.warning("tenant-billing delegation failed (non-fatal): %s", exc)

    return {
        "ok":           True,
        "matter_uri":   matter_uri,
        "amount_minor": amount_minor,
        "currency":     currency,
        "tenant_billing": tenant_result,
    }


# ── Worker registration ────────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 120_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.marketing.submit",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _mkt(task_type: str = "marketing.kpiReport",
                   brand: str = "advocate", audience: str = "",
                   topic: str = "", payload: str = "",
                   schedule_at: str = "", requester_did: str = "") -> dict:
        return await task_lawfirm_marketing_submit(
            task_type=task_type, brand=brand, audience=audience, topic=topic,
            payload=payload, schedule_at=schedule_at, requester_did=requester_did,
        )

    @app.task(task_type="lawfirm.payment.stripeWebhook",
              timeout_ms=60_000, max_jobs_to_activate=8)
    async def _stripe(event_id: str = "", type: str = "", livemode: bool = False,
                      stripe_account: str = "", data: str = "",
                      signature_header: str = "") -> dict:
        return await task_lawfirm_payment_stripe_webhook(
            event_id=event_id, type=type, livemode=livemode,
            stripe_account=stripe_account, data=data,
            signature_header=signature_header,
        )

    LOG.info("Registered tasks: lawfirm.marketing.submit, lawfirm.payment.stripeWebhook")
