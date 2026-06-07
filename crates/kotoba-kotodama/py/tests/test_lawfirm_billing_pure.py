"""Pure tests for lawfirm_billing primitive (4 task types)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    """Mock _execute / _query / _stripe_post."""
    def __init__(self, query_returns=None, stripe_returns=None):
        self.query_returns = query_returns or []
        self.stripe_returns = stripe_returns or []
        self.executes: list[tuple[str, dict]] = []
        self.stripe_calls: list[tuple[str, dict]] = []

    def install(self):
        import kotodama.primitives.lawfirm_billing as p
        self._orig_exec = p._execute
        self._orig_q = p._query
        self._orig_stripe = p._stripe_post

        executes = self.executes
        def _exec(sql_str, params):
            executes.append((sql_str, params))
            return True
        p._execute = _exec

        responses = list(self.query_returns)
        def _q(sql_str, params=None):
            return responses.pop(0) if responses else []
        p._query = _q

        stripe_responses = list(self.stripe_returns)
        stripe_calls = self.stripe_calls
        def _sp(api_key, path, body):
            stripe_calls.append((path, body))
            return stripe_responses.pop(0) if stripe_responses else {"id": "test_default"}
        p._stripe_post = _sp

    def uninstall(self):
        import kotodama.primitives.lawfirm_billing as p
        p._execute = self._orig_exec
        p._query = self._orig_q
        p._stripe_post = self._orig_stripe


class TestModeAStartSubscription(unittest.TestCase):
    def test_happy_path(self):
        stub = _Stub(stripe_returns=[
            {"id": "cus_abc"},
            {"id": "prod_abc"},
            {"id": "price_abc"},
            {"id": "sub_abc"},
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_a_start_subscription
            out = asyncio.run(task_billing_mode_a_start_subscription(
                tenant_id="prod-nishith",
                legal_name="Nishith Desai Associates",
                admin_email="vyapak@nishithdesai.com",
                monthly_amount_minor=500_000,
                currency="usd",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["stripe_customer_id"], "cus_abc")
            self.assertEqual(out["stripe_subscription_id"], "sub_abc")
            self.assertEqual(out["stripe_price_id"], "price_abc")
            # 4 Stripe calls + 1 UPDATE on tenant
            self.assertEqual(len(stub.stripe_calls), 4)
            self.assertEqual(stub.stripe_calls[0][0], "customers")
            self.assertEqual(stub.stripe_calls[1][0], "products")
            self.assertEqual(stub.stripe_calls[2][0], "prices")
            self.assertEqual(stub.stripe_calls[3][0], "subscriptions")
            self.assertEqual(len(stub.executes), 1)
        finally:
            stub.uninstall()

    def test_missing_required_fields(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_a_start_subscription
            out = asyncio.run(task_billing_mode_a_start_subscription(
                tenant_id="", legal_name="", admin_email="",
            ))
            self.assertFalse(out["ok"])
            self.assertIn("required", out["error"])
            self.assertEqual(len(stub.stripe_calls), 0)
        finally:
            stub.uninstall()

    def test_invalid_amount(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_a_start_subscription
            out = asyncio.run(task_billing_mode_a_start_subscription(
                tenant_id="t", legal_name="X", admin_email="x@x.com",
                monthly_amount_minor=0,
            ))
            self.assertFalse(out["ok"])
            self.assertIn("> 0", out["error"])
        finally:
            stub.uninstall()


class TestModeBOnboardConnect(unittest.TestCase):
    def test_happy_path(self):
        stub = _Stub(stripe_returns=[
            {"id": "acct_abc"},
            {"url": "https://connect.stripe.com/setup/abc"},
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_b_onboard_connect
            out = asyncio.run(task_billing_mode_b_onboard_connect(
                tenant_id="prod-induslaw",
                country="IN",
                admin_email="avimukt@induslaw.com",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["stripe_connect_account_id"], "acct_abc")
            self.assertEqual(out["onboarding_url"], "https://connect.stripe.com/setup/abc")
            self.assertEqual(stub.stripe_calls[0][0], "accounts")
            self.assertEqual(stub.stripe_calls[1][0], "account_links")
            # account_links has return_url derived from default origin
            self.assertIn("stripe-onboarded", stub.stripe_calls[1][1]["return_url"])
            self.assertEqual(len(stub.executes), 1)
        finally:
            stub.uninstall()


class TestModeBSubTenantSubscription(unittest.TestCase):
    def test_y1_application_fee_85(self):
        stub = _Stub(
            query_returns=[[{"stripe_connect_account_id": "acct_advisor",
                             "slug": "induslaw"}]],
            stripe_returns=[
                {"id": "cus_acme"},
                {"id": "prod_acme"},
                {"id": "price_acme"},
                {"id": "sub_acme"},
            ],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_b_start_subscription
            out = asyncio.run(task_billing_mode_b_start_subscription(
                sub_tenant_id="acme-startup",
                sub_tenant_name="Acme Startup Inc",
                sub_tenant_email="cfo@acmestartup.com",
                advisor_tenant_id="prod-induslaw",
                monthly_amount_minor=200_000,
                currency="usd",
                revshare_year=1,
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["application_fee_pct"], 85)
            self.assertEqual(out["advisor_connect_account"], "acct_advisor")
            # Subscription body should carry application_fee_percent + transfer_data
            sub_body = stub.stripe_calls[3][1]
            self.assertEqual(sub_body["application_fee_percent"], 85)
            self.assertEqual(sub_body["transfer_data"]["destination"], "acct_advisor")
        finally:
            stub.uninstall()

    def test_y2_application_fee_90(self):
        stub = _Stub(
            query_returns=[[{"stripe_connect_account_id": "acct_x", "slug": "x"}]],
            stripe_returns=[{"id": "c"}, {"id": "p"}, {"id": "pr"}, {"id": "s"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_b_start_subscription
            out = asyncio.run(task_billing_mode_b_start_subscription(
                sub_tenant_id="s", sub_tenant_name="S", sub_tenant_email="s@s.com",
                advisor_tenant_id="prod-x", revshare_year=2,
            ))
            self.assertEqual(out["application_fee_pct"], 90)
        finally:
            stub.uninstall()

    def test_y3_application_fee_95(self):
        stub = _Stub(
            query_returns=[[{"stripe_connect_account_id": "acct_x", "slug": "x"}]],
            stripe_returns=[{"id": "c"}, {"id": "p"}, {"id": "pr"}, {"id": "s"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_b_start_subscription
            out = asyncio.run(task_billing_mode_b_start_subscription(
                sub_tenant_id="s", sub_tenant_name="S", sub_tenant_email="s@s.com",
                advisor_tenant_id="prod-x", revshare_year=3,
            ))
            self.assertEqual(out["application_fee_pct"], 95)
        finally:
            stub.uninstall()

    def test_advisor_not_onboarded(self):
        stub = _Stub(query_returns=[[{"stripe_connect_account_id": None}]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_mode_b_start_subscription
            out = asyncio.run(task_billing_mode_b_start_subscription(
                sub_tenant_id="s", sub_tenant_name="S", sub_tenant_email="s@s.com",
                advisor_tenant_id="prod-x",
            ))
            self.assertFalse(out["ok"])
            self.assertIn("Connect-onboarded", out["error"])
        finally:
            stub.uninstall()


class TestWebhookInvoicePaid(unittest.TestCase):
    def test_happy_path(self):
        stub = _Stub(query_returns=[
            [{"tenant_id": "prod-nishith", "billing_mode": "flat", "slug": "nishith"}],  # tenant lookup
            [],  # existing invoice check (empty)
            [],  # existing payment idempotency check (empty)
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_process_webhook_invoice_paid
            out = asyncio.run(task_billing_process_webhook_invoice_paid(
                event_id="evt_abc",
                invoice_id="in_abc",
                subscription_id="sub_abc",
                customer_id="cus_abc",
                amount_paid_minor=500_000,
                currency="usd",
                paid_at_unix=1_715_000_000,
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["tenant_id"], "prod-nishith")
            self.assertTrue(out["matched"])
            self.assertFalse(out["duplicate"])
            self.assertTrue(out["invoice_uri"].startswith("at://"))
            self.assertTrue(out["payment_uri"].startswith("at://"))
            # 3 _execute: invoice INSERT + payment INSERT + lead UPDATE
            self.assertEqual(len(stub.executes), 3)
        finally:
            stub.uninstall()

    def test_idempotent_duplicate_event(self):
        stub = _Stub(query_returns=[
            [{"tenant_id": "prod-x", "billing_mode": "flat", "slug": "x"}],
            [],  # invoice check
            [{"vertex_id": "at://existing-payment"}],  # payment already exists
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_process_webhook_invoice_paid
            out = asyncio.run(task_billing_process_webhook_invoice_paid(
                event_id="evt_dup", invoice_id="in_x",
                customer_id="cus_x",
            ))
            self.assertTrue(out["ok"])
            self.assertTrue(out["duplicate"])
        finally:
            stub.uninstall()

    def test_unknown_tenant_graceful(self):
        stub = _Stub(query_returns=[[]])  # no tenant match
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_process_webhook_invoice_paid
            out = asyncio.run(task_billing_process_webhook_invoice_paid(
                event_id="evt_orphan", invoice_id="in_o", customer_id="cus_o",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["tenant_id"], "unknown")
            self.assertFalse(out["matched"])
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()

    def test_invoice_idempotency_reuses_existing(self):
        stub = _Stub(query_returns=[
            [{"tenant_id": "prod-x", "billing_mode": "flat", "slug": "x"}],
            [{"vertex_id": "at://existing-invoice"}],  # invoice already there
            [],  # payment check empty
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_process_webhook_invoice_paid
            out = asyncio.run(task_billing_process_webhook_invoice_paid(
                event_id="evt_n", invoice_id="in_x",
                customer_id="cus_x", amount_paid_minor=100,
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["invoice_uri"], "at://existing-invoice")
            # 2 _execute: payment INSERT + lead UPDATE (no new invoice)
            self.assertEqual(len(stub.executes), 2)
        finally:
            stub.uninstall()

    def test_missing_required(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_billing import task_billing_process_webhook_invoice_paid
            out = asyncio.run(task_billing_process_webhook_invoice_paid(
                event_id="", invoice_id="", customer_id="",
            ))
            self.assertFalse(out["ok"])
            self.assertIn("required", out["error"])
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
