"""Oshinobi payment primitives.

Zeebe task type:
  oshinobi.payment.charge - Stripe PaymentIntent confirm (tip + subscription).

Input variables (BPMN process variables):
  paymentToken    str   Stripe payment method id (pm_xxx)
  amountUsdCents  int   Charge amount in USD cents (min 50)
  currency        str   ISO 4217 lower-case, default "usd"
  kind            str   "tip" | "subscription" (stored as metadata)

Output variables merged into process scope:
  chargeResult    dict  {status, tokenRef, reason}
                        status: "captured" | "failed"
                        tokenRef: Stripe PaymentIntent id (pi_xxx) or ""
                        reason: human-readable failure reason or ""

Env vars:
  STRIPE_SECRET_KEY   or SS_STRIPE_SECRET_KEY   Stripe secret key (sk_live_* / sk_test_*)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


# ─── Stripe HTTP helper (mirrors ingest/stripe.py, minimal copy) ──────────────


def _stripe_form(data: dict[str, Any]) -> bytes:
    parts: list[str] = []

    def add(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                add(f"{prefix}[{k}]", v)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                add(f"{prefix}[{i}]", v)
        elif isinstance(value, bool):
            parts.append(f"{urllib.parse.quote(prefix)}={urllib.parse.quote('true' if value else 'false')}")
        else:
            parts.append(f"{urllib.parse.quote(prefix)}={urllib.parse.quote(str(value))}")

    import urllib.parse
    for k, v in data.items():
        add(k, v)
    return "&".join(parts).encode("utf-8")


def _stripe(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("SS_STRIPE_SECRET_KEY") or ""
    if not key:
        return {"error": "stripeNotConfigured"}
    req = urllib.request.Request(
        f"https://api.stripe.com/v1{path}",
        method=method,
        data=None if method == "GET" else _stripe_form(body or {}),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "etzhayyim-oshinobi-zeebe/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw[:500]}
        return {"error": "stripeApiError", "status": e.code, "detail": data}


# ─── Task ─────────────────────────────────────────────────────────────────────


def task_oshinobi_payment_charge(
    *,
    paymentToken: str = "",
    amountUsdCents: int = 0,
    currency: str = "usd",
    kind: str = "tip",
    **_: Any,
) -> dict[str, Any]:
    """Confirm a Stripe PaymentIntent for oshinobi tip or subscription.

    Creates a PaymentIntent with confirm=true and automatic_payment_methods
    restricted to non-redirect flows (safe for server-side confirm).
    Returns chargeResult dict directly into the BPMN process scope.
    """
    amount = int(amountUsdCents)
    if amount < 50:
        return {"chargeResult": {"status": "failed", "tokenRef": "",
                                  "reason": f"amount too small: {amount} cents (min 50)"}}

    if not paymentToken:
        return {"chargeResult": {"status": "failed", "tokenRef": "",
                                  "reason": "paymentToken is required"}}

    result = _stripe("POST", "/payment_intents", {
        "amount": amount,
        "currency": currency.lower() or "usd",
        "payment_method": paymentToken,
        "confirm": "true",
        "automatic_payment_methods[enabled]": "true",
        "automatic_payment_methods[allow_redirects]": "never",
        "metadata[kind]": kind,
        "metadata[platform]": "oshinobi.etzhayyim.com",
    })

    if result.get("error"):
        reason = str(result.get("error", "stripe_error"))
        if result.get("detail") and isinstance(result["detail"], dict):
            err = result["detail"].get("error", {})
            reason = err.get("message", reason) if isinstance(err, dict) else reason
        return {"chargeResult": {"status": "failed", "tokenRef": "", "reason": reason}}

    pi_status = result.get("status", "")
    pi_id = result.get("id", "")

    if pi_status == "succeeded":
        return {"chargeResult": {"status": "captured", "tokenRef": pi_id, "reason": ""}}

    # requires_action, requires_payment_method, processing, canceled, etc.
    lpe = result.get("last_payment_error")
    reason = ""
    if isinstance(lpe, dict):
        reason = lpe.get("message", pi_status)
    else:
        reason = pi_status

    return {"chargeResult": {"status": "failed", "tokenRef": pi_id, "reason": reason}}


# ─── Registration ─────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 30_000) -> None:
    worker.task(
        task_type="oshinobi.payment.charge",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_oshinobi_payment_charge)


__all__ = ["register", "task_oshinobi_payment_charge"]
