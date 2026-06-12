"""
lawfirm.billing.* — LangServer handlers for the W11-W12 conversion path.

Task types:
  lawfirm.billing.modeAStartSubscription   Mode A flat tier: customer + price + sub
  lawfirm.billing.modeBOnboardConnect      Mode B rev-share: Express account + onboarding link
  lawfirm.billing.modeBStartSubscription   Sub-tenant subscription with platform-fee split
  lawfirm.billing.processWebhookInvoicePaid Webhook handler: persist payment + bump lead.stage='paid'

Paired with `_working/etzhayyim-revenue/stripe-connect-onboarding-runbook.md`.

Account routing reuses _select_stripe_account convention from lawfirm_checkout.
Falls back to dry-run when STRIPE_*_API_KEY env vars are unset (Day-0 safe).

ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import datetime
from datetime import datetime, timezone
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.billing")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"
_STRIPE_API_BASE = "https://api.stripe.com/v1"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vid(kind: str) -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"








def _select_stripe_key(currency: str) -> tuple[str, str]:
    cur_upper = (currency or "").upper()
    if cur_upper == "INR":
        return os.environ.get("STRIPE_IN_API_KEY", ""), "stripe_india"
    if cur_upper == "JPY":
        return os.environ.get("STRIPE_JP_API_KEY", ""), "stripe_japan"
    return os.environ.get("STRIPE_US_API_KEY", ""), "stripe_us"


def _stripe_post(api_key: str, path: str, body: dict) -> dict:
    if not api_key:
        return {"_dry_run": True, "id": f"dry_{uuid.uuid4().hex[:24]}"}
    encoded = urllib.parse.urlencode(_flatten_body(body)).encode()
    req = urllib.request.Request(
        f"{_STRIPE_API_BASE}/{path}",
        data=encoded,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _flatten_body(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict to Stripe form-urlencoded keys (a[b][c]=v)."""
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}[{k}]" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_body(v, key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    out.update(_flatten_body(item, f"{key}[{i}]"))
                else:
                    out[f"{key}[{i}]"] = str(item)
        elif v is None:
            continue
        elif isinstance(v, bool):
            out[key] = "true" if v else "false"
        else:
            out[key] = str(v)
    return out


# ── Task: lawfirm.billing.modeAStartSubscription ──────────────────────────────

async def task_billing_mode_a_start_subscription(
    tenant_id: str = "",
    legal_name: str = "",
    admin_email: str = "",
    monthly_amount_minor: int = 500_000,
    currency: str = "usd",
) -> dict:
    if not tenant_id or not legal_name or not admin_email:
        return {"ok": False, "error": "tenant_id, legal_name, admin_email required"}
    if monthly_amount_minor <= 0:
        return {"ok": False, "error": "monthly_amount_minor must be > 0"}

    api_key, account_label = _select_stripe_key(currency)

    customer = _stripe_post(api_key, "customers", {
        "name": legal_name,
        "email": admin_email,
        "description": f"tenant_id={tenant_id}",
        "metadata": {"tenant_id": tenant_id},
    })
    customer_id = customer.get("id", "")

    product = _stripe_post(api_key, "products", {
        "name": f"lawfirm.etzhayyim.com SaaS — {legal_name}",
        "metadata": {"product_kind": "lawfirm-saas-flat", "tenant_id": tenant_id},
    })
    product_id = product.get("id", "")

    price = _stripe_post(api_key, "prices", {
        "product": product_id,
        "currency": currency.lower(),
        "unit_amount": monthly_amount_minor,
        "recurring": {"interval": "month"},
        "metadata": {"tier": "flat"},
    })
    price_id = price.get("id", "")

    subscription = _stripe_post(api_key, "subscriptions", {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "collection_method": "send_invoice",
        "days_until_due": 30,
        "metadata": {"tenant_id": tenant_id, "billing_mode": "flat"},
    })
    subscription_id = subscription.get("id", "")

    client = get_kotoba_client()
    client.insert_row(
        "vertex_lawfirm_tenant",
        {
            "tenant_id": tenant_id,
            "stripe_customer_id": customer_id,
            "billing_mode": "flat",
            "platform_fee_pct": 100
        }
    )

    LOG.info(
        "Mode A subscription created tenant=%s customer=%s subscription=%s account=%s",
        tenant_id, customer_id, subscription_id, account_label,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_price_id": price_id,
        "account_label": account_label,
        "dry_run": bool(customer.get("_dry_run")),
    }


# ── Task: lawfirm.billing.modeBOnboardConnect ─────────────────────────────────

async def task_billing_mode_b_onboard_connect(
    tenant_id: str = "",
    country: str = "",
    admin_email: str = "",
    return_origin: str = "",
) -> dict:
    if not tenant_id or not country or not admin_email:
        return {"ok": False, "error": "tenant_id, country, admin_email required"}

    api_key, _ = _select_stripe_key("usd")  # Connect platform key = US

    account = _stripe_post(api_key, "accounts", {
        "type": "express",
        "country": country.upper(),
        "email": admin_email,
        "business_type": "company",
        "capabilities": {
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        "metadata": {"tenant_id": tenant_id},
    })
    account_id = account.get("id", "")

    return_origin = return_origin or f"https://{tenant_id}.lawfirm.etzhayyim.com"
    link = _stripe_post(api_key, "account_links", {
        "account": account_id,
        "refresh_url": f"{return_origin}/stripe-refresh",
        "return_url": f"{return_origin}/stripe-onboarded",
        "type": "account_onboarding",
    })
    onboarding_url = link.get("url", "")

    client = get_kotoba_client()
    client.insert_row(
        "vertex_lawfirm_tenant",
        {
            "tenant_id": tenant_id,
            "stripe_connect_account_id": account_id,
            "billing_mode": "rev_share_y1",
            "platform_fee_pct": 85
        }
    )

    LOG.info(
        "Mode B Connect account onboarded tenant=%s account=%s",
        tenant_id, account_id,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "stripe_connect_account_id": account_id,
        "onboarding_url": onboarding_url,
        "dry_run": bool(account.get("_dry_run")),
    }


# ── Task: lawfirm.billing.modeBStartSubscription (sub-tenant routed) ──────────

async def task_billing_mode_b_start_subscription(
    sub_tenant_id: str = "",
    sub_tenant_name: str = "",
    sub_tenant_email: str = "",
    advisor_tenant_id: str = "",
    monthly_amount_minor: int = 200_000,
    currency: str = "usd",
    revshare_year: int = 1,
) -> dict:
    if not (sub_tenant_id and sub_tenant_name and sub_tenant_email and advisor_tenant_id):
        return {"ok": False, "error": "sub_tenant_id, name, email, advisor_tenant_id required"}

    client = get_kotoba_client()
    advisor = client.select_first_where(
        "vertex_lawfirm_tenant", "tenant_id", advisor_tenant_id,
        columns=["stripe_connect_account_id", "slug"]
    )
    if not advisor or not advisor.get("stripe_connect_account_id"):
        return {"ok": False, "error": "advisor tenant not Connect-onboarded"}

    advisor_account = advisor["stripe_connect_account_id"]
    advisor_slug = advisor.get("slug", "")

    # Y1 = 85% etzhayyim / 15% firm; Y2 = 90/10; Y3 = 95/5
    fee_pct_map = {1: 85, 2: 90, 3: 95}
    application_fee_pct = fee_pct_map.get(revshare_year, 85)

    api_key, _ = _select_stripe_key(currency)

    customer = _stripe_post(api_key, "customers", {
        "name": sub_tenant_name,
        "email": sub_tenant_email,
        "metadata": {
            "sub_tenant_id": sub_tenant_id,
            "advisor_tenant_id": advisor_tenant_id,
            "advisor_slug": advisor_slug,
            "advisor_connect_account": advisor_account,
        },
    })
    customer_id = customer.get("id", "")

    product = _stripe_post(api_key, "products", {
        "name": f"lawfirm.etzhayyim.com sub-tenant — {sub_tenant_name}",
        "metadata": {"product_kind": "lawfirm-subtenant", "advisor": advisor_slug},
    })
    product_id = product.get("id", "")

    price = _stripe_post(api_key, "prices", {
        "product": product_id,
        "currency": currency.lower(),
        "unit_amount": monthly_amount_minor,
        "recurring": {"interval": "month"},
    })
    price_id = price.get("id", "")

    subscription = _stripe_post(api_key, "subscriptions", {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "application_fee_percent": application_fee_pct,
        "transfer_data": {"destination": advisor_account},
        "metadata": {
            "sub_tenant_id": sub_tenant_id,
            "advisor_tenant_id": advisor_tenant_id,
            "advisor_slug": advisor_slug,
            "platform_fee_pct": application_fee_pct,
            "revshare_year": revshare_year,
        },
    })
    subscription_id = subscription.get("id", "")

    LOG.info(
        "Mode B sub-tenant subscription created sub=%s advisor=%s sub=%s pct=%d Y%d",
        sub_tenant_id, advisor_tenant_id, subscription_id, application_fee_pct, revshare_year,
    )
    return {
        "ok": True,
        "sub_tenant_id": sub_tenant_id,
        "advisor_tenant_id": advisor_tenant_id,
        "advisor_connect_account": advisor_account,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "application_fee_pct": application_fee_pct,
        "revshare_year": revshare_year,
        "dry_run": bool(customer.get("_dry_run")),
    }


# ── Task: lawfirm.billing.processWebhookInvoicePaid ──────────────────────────

async def task_billing_process_webhook_invoice_paid(
    event_id: str = "",
    invoice_id: str = "",
    subscription_id: str = "",
    customer_id: str = "",
    amount_paid_minor: int = 0,
    currency: str = "usd",
    application_fee_minor: int = 0,
    paid_at_unix: int = 0,
) -> dict:
    """
    Webhook payload mapper for `invoice.paid`.
    Extracts: invoice_id, subscription_id, customer_id, amount_paid, currency,
    application_fee. Persists payment + invoice rows + bumps lead.stage.
    Idempotent on event_id.
    """
    if not event_id or not invoice_id or not customer_id:
        return {"ok": False, "error": "event_id, invoice_id, customer_id required"}

    # Resolve tenant_id by stripe customer or connect account
    client = get_kotoba_client()
    tenant_row = client.select_first_where(
        "vertex_lawfirm_tenant", "stripe_customer_id", customer_id,
        columns=["tenant_id", "billing_mode", "slug"]
    )
    if not tenant_row:
        # Sub-tenant case: lookup by advisor_connect_account in stripe metadata is host-side;
        # here we degrade to "unknown_tenant" and emit audit-only.
        LOG.warning("webhook: no tenant for customer=%s event=%s", customer_id, event_id)
        return {"ok": True, "tenant_id": "unknown", "event_id": event_id, "matched": False}

    row = tenant_row
    tenant_id = row["tenant_id"]
    billing_mode = row.get("billing_mode") or "flat"
    slug = row.get("slug") or ""

    paid_iso = (
        _dt.datetime.fromtimestamp(paid_at_unix, tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if paid_at_unix else _now_iso()
    )

    # Idempotency on (tenant_id, stripe_invoice_id)
    existing_inv = client.select_first_where(
        "vertex_lawfirm_invoice", "stripe_invoice_id", invoice_id, columns=["vertex_id"]
    )
    if not existing_inv:
        invoice_uri = _vid("invoice")
        client.insert_row(
            "vertex_lawfirm_invoice",
            {
                "vertex_id": invoice_uri, "tenant_id": tenant_id, "stripe_invoice_id": invoice_id,
                "stripe_subscription_id": subscription_id, "amount_minor": amount_paid_minor,
                "currency": currency.lower(), "status": "paid", "created_at": _now_iso(),
                "owner_did": _FIRM_DID,
            },
        )
    else:
        invoice_uri = existing_inv["vertex_id"]

    # Idempotency on (event_id) for payment
    existing_pay = client.select_first_where(
        "vertex_lawfirm_payment", "stripe_payment_intent_id", event_id, columns=["vertex_id"]
    )
    if existing_pay:
        return {
            "ok": True, "tenant_id": tenant_id, "event_id": event_id,
            "matched": True, "duplicate": True,
        }

    payment_uri = _vid("payment")
    client.insert_row(
        "vertex_lawfirm_payment",
        {
            "vertex_id": payment_uri, "tenant_id": tenant_id, "invoice_uri": invoice_uri,
            "amount_minor": amount_paid_minor, "platform_fee_minor": application_fee_minor,
            "currency": currency.lower(), "paid_at": paid_iso,
            "stripe_payment_intent_id": event_id, "stripe_charge_id": "",
            "status": "succeeded", "created_at": _now_iso(), "owner_did": _FIRM_DID,
        },
    )

    # Lead.stage promotion (sandbox or saas-prod first paid invoice)
    if slug:
        # R0: This complex query (LIKE and IN) needs q().
        leads_to_update = client.q(
            f"""
            [:find ?v ?assigned_to_did ?stage
             :where
             [?v "assigned_to_did" ?assigned_to_did]
             [(str ?assigned_to_did) ?pat-fn]
             [(.startsWith ?pat-fn ?pat)]
             [?v "stage" ?stage]
             (or
              [(= ?stage "sow_signed")]
              [(= ?stage "pilot_active")])]
            """,
            args={"?pat": f"%{slug}%"}
        )
        for lead_vertex_id, _, _ in leads_to_update:
            client.insert_row(
                "vertex_lawfirm_lead",
                {"vertex_id": lead_vertex_id, "stage": "paid", "last_touch_at": _now_iso()}
            )

    LOG.info(
        "webhook invoice.paid processed tenant=%s amount=%d %s billing_mode=%s",
        tenant_id, amount_paid_minor, currency.upper(), billing_mode,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "event_id": event_id,
        "invoice_uri": invoice_uri,
        "payment_uri": payment_uri,
        "matched": True,
        "duplicate": False,
    }


# ── LangServer registration ─────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.billing.modeAStartSubscription",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _a_start(tenant_id: str = "", legal_name: str = "",
                       admin_email: str = "", monthly_amount_minor: int = 500_000,
                       currency: str = "usd") -> dict:
        return await task_billing_mode_a_start_subscription(
            tenant_id=tenant_id, legal_name=legal_name, admin_email=admin_email,
            monthly_amount_minor=monthly_amount_minor, currency=currency,
        )

    @app.task(task_type="lawfirm.billing.modeBOnboardConnect",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _b_onboard(tenant_id: str = "", country: str = "",
                         admin_email: str = "", return_origin: str = "") -> dict:
        return await task_billing_mode_b_onboard_connect(
            tenant_id=tenant_id, country=country,
            admin_email=admin_email, return_origin=return_origin,
        )

    @app.task(task_type="lawfirm.billing.modeBStartSubscription",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _b_start(sub_tenant_id: str = "", sub_tenant_name: str = "",
                       sub_tenant_email: str = "", advisor_tenant_id: str = "",
                       monthly_amount_minor: int = 200_000,
                       currency: str = "usd", revshare_year: int = 1) -> dict:
        return await task_billing_mode_b_start_subscription(
            sub_tenant_id=sub_tenant_id, sub_tenant_name=sub_tenant_name,
            sub_tenant_email=sub_tenant_email, advisor_tenant_id=advisor_tenant_id,
            monthly_amount_minor=monthly_amount_minor, currency=currency,
            revshare_year=revshare_year,
        )

    @app.task(task_type="lawfirm.billing.processWebhookInvoicePaid",
              timeout_ms=timeout_ms, max_jobs_to_activate=8)
    async def _webhook(event_id: str = "", invoice_id: str = "",
                       subscription_id: str = "", customer_id: str = "",
                       amount_paid_minor: int = 0, currency: str = "usd",
                       application_fee_minor: int = 0,
                       paid_at_unix: int = 0) -> dict:
        return await task_billing_process_webhook_invoice_paid(
            event_id=event_id, invoice_id=invoice_id,
            subscription_id=subscription_id, customer_id=customer_id,
            amount_paid_minor=amount_paid_minor, currency=currency,
            application_fee_minor=application_fee_minor,
            paid_at_unix=paid_at_unix,
        )

    LOG.info(
        "Registered tasks: lawfirm.billing.{modeAStartSubscription, "
        "modeBOnboardConnect, modeBStartSubscription, processWebhookInvoicePaid}"
    )
