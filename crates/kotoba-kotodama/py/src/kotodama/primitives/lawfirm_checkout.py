"""
lawfirm.checkout.* — LangServer handler for Stripe Checkout Session creation.

Task type:
  lawfirm.checkout.create

Account routing:
  USD → Stripe US sole-prop (env STRIPE_US_API_KEY)
  INR → Stripe India k-bakshi PAN (env STRIPE_IN_API_KEY)

Dry-run when API key not provisioned (Day-0 state, returns mock URL).

ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client # <-- New import

LOG = logging.getLogger("lawfirm.checkout")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vid(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


# ── Account routing ──────────────────────────────────────────────────────────

def _select_stripe_account(currency: str) -> tuple[str, str]:
    """Return (api_key, account_label) for the given currency."""
    cur_upper = (currency or "").upper()
    if cur_upper == "INR":
        return os.environ.get("STRIPE_IN_API_KEY", ""), "stripe_india"
    # Default USD + everything else routes to US sole-prop (Stripe Atlas)
    return os.environ.get("STRIPE_US_API_KEY", ""), "stripe_us"


# ── Stripe API call ──────────────────────────────────────────────────────────

def _create_session_real(
    api_key: str, product_kind: str, amount_minor: int, currency: str,
    description: str, client_email: str, client_name: str, success_url: str,
    cancel_url: str, expires_at_unix: int, metadata: dict,
) -> dict:
    """POST /v1/checkout/sessions on api.stripe.com."""
    body = {
        "mode": "payment",
        "currency": currency.lower(),
        "line_items[0][price_data][currency]": currency.lower(),
        "line_items[0][price_data][unit_amount]": str(amount_minor),
        "line_items[0][price_data][product_data][name]": product_kind,
        "line_items[0][price_data][product_data][description]": description[:500],
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "expires_at": str(expires_at_unix),
    }
    if client_email:
        body["customer_email"] = client_email
    for k, v in metadata.items():
        body[f"metadata[{k}]"] = str(v)[:500]

    encoded = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=encoded,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


# ── Task: lawfirm.checkout.create ────────────────────────────────────────────

async def task_lawfirm_checkout_create(
    product_kind: str = "legal-consult-30min",
    amount_minor: int = 0,
    currency: str = "USD",
    matter_uri: str = "",
    client_did: str = "",
    client_email: str = "",
    client_name: str = "",
    stream: str = "advocate-fee",
    description: str = "",
    success_url: str = "",
    cancel_url: str = "",
    expires_in_minutes: int = 1440,
    metadata: str = "",
) -> dict:
    if amount_minor < 0 or not currency:
        return {"ok": False, "error": "amount_minor + currency required"}

    api_key, account_label = _select_stripe_account(currency)

    expires_at = _dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(minutes=int(expires_in_minutes))
    expires_at_unix = int(expires_at.timestamp())
    expires_at_iso = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    success_url = success_url or "https://lawfirm.etzhayyim.com/checkout/success?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = cancel_url or "https://lawfirm.etzhayyim.com/checkout/cancel"

    try:
        meta = json.loads(metadata) if metadata else {}
    except Exception:
        meta = {}
    meta.update({
        "matter_uri": matter_uri,
        "client_did": client_did,
        "stream": stream,
        "product_kind": product_kind,
    })

    if not api_key:
        # Dry-run mode (Day-0 state until Stripe accounts provisioned)
        session_id = f"cs_dry_{uuid.uuid4().hex[:24]}"
        checkout_url = (
            f"https://checkout.stripe.com/c/pay/{session_id}"
            f"?dry_run=true&amt={amount_minor}&ccy={currency}"
        )
        dry_run = True
    else:
        try:
            resp = _create_session_real(
                api_key, product_kind, amount_minor, currency, description,
                client_email, client_name, success_url, cancel_url,
                expires_at_unix, meta,
            )
            session_id = resp.get("id", "")
            checkout_url = resp.get("url", "")
            dry_run = False
        except Exception as exc:
            return {"ok": False, "error": f"stripe_call_failed: {exc}"}

    # Persist intent row to kotoba (mirrors invoice for pre-payment tracking) # <-- Comment updated
    get_kotoba_client().insert_row( # <-- Direct insert_row call
        "vertex_lawfirm_invoice",
        {
            "vertex_id":    _vid("checkoutIntent"),
            "stripe_invoice_id":    session_id,
            "matter_uri":   matter_uri,
            "client_did":   client_did,
            "stream": stream,
            "amount_minor":    amount_minor,
            "currency":    currency.upper(),
            "total_minor":    amount_minor,
            "status": "checkout_pending",
            "issued_at": _now_iso(),
            "hosted_invoice_url":    checkout_url,
            "raw_json":    json.dumps({"product_kind": product_kind, "metadata": meta, "dry_run": dry_run}, ensure_ascii=False)[:30_000],
            "created_at":    _now_iso(),
            "owner_did":  _FIRM_DID,
        },
    )

    LOG.info(
        "checkout session created kind=%s amt=%s %s acct=%s session=%s dry=%s",
        product_kind, amount_minor, currency, account_label, session_id, dry_run,
    )
    return {
        "ok":             True,
        "checkout_url":   checkout_url,
        "session_id":     session_id,
        "stripe_account": account_label,
        "expires_at":     expires_at_iso,
        "dry_run":        dry_run,
    }


# ── Worker registration ──────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 30_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.checkout.create",
              timeout_ms=timeout_ms, max_jobs_to_activate=8)
    async def _ck(product_kind: str = "legal-consult-30min",
                  amount_minor: int = 0, currency: str = "USD",
                  matter_uri: str = "", client_did: str = "",
                  client_email: str = "", client_name: str = "",
                  stream: str = "advocate-fee", description: str = "",
                  success_url: str = "", cancel_url: str = "",
                  expires_in_minutes: int = 1440, metadata: str = "") -> dict:
        return await task_lawfirm_checkout_create(
            product_kind=product_kind, amount_minor=amount_minor,
            currency=currency, matter_uri=matter_uri, client_did=client_did,
            client_email=client_email, client_name=client_name, stream=stream,
            description=description, success_url=success_url,
            cancel_url=cancel_url, expires_in_minutes=expires_in_minutes,
            metadata=metadata,
        )

    LOG.info("Registered task: lawfirm.checkout.create")
