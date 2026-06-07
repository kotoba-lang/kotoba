"""Pure tests for lawfirm_checkout primitive (Stripe Checkout Session)."""

from __future__ import annotations

import asyncio
import os
import unittest


class _Stub:
    def install(self):
        import kotodama.primitives.lawfirm_checkout as p
        self._orig_exec = p._execute
        p._execute = lambda *a, **k: True

    def uninstall(self):
        import kotodama.primitives.lawfirm_checkout as p
        p._execute = self._orig_exec


class TestAccountRouting(unittest.TestCase):
    def test_inr_routes_india(self):
        from kotodama.primitives.lawfirm_checkout import _select_stripe_account
        os.environ["STRIPE_IN_API_KEY"] = "sk_test_in"
        os.environ.pop("STRIPE_US_API_KEY", None)
        try:
            key, label = _select_stripe_account("INR")
            self.assertEqual(key, "sk_test_in")
            self.assertEqual(label, "stripe_india")
        finally:
            os.environ.pop("STRIPE_IN_API_KEY", None)

    def test_usd_routes_us(self):
        from kotodama.primitives.lawfirm_checkout import _select_stripe_account
        os.environ["STRIPE_US_API_KEY"] = "sk_test_us"
        os.environ.pop("STRIPE_IN_API_KEY", None)
        try:
            key, label = _select_stripe_account("USD")
            self.assertEqual(key, "sk_test_us")
            self.assertEqual(label, "stripe_us")
        finally:
            os.environ.pop("STRIPE_US_API_KEY", None)

    def test_unknown_currency_falls_to_us(self):
        from kotodama.primitives.lawfirm_checkout import _select_stripe_account
        os.environ.pop("STRIPE_IN_API_KEY", None)
        os.environ.pop("STRIPE_US_API_KEY", None)
        key, label = _select_stripe_account("EUR")
        self.assertEqual(label, "stripe_us")  # default route
        self.assertEqual(key, "")  # no env → empty key triggers dry_run


class TestCheckoutCreate(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()
        os.environ.pop("STRIPE_US_API_KEY", None)
        os.environ.pop("STRIPE_IN_API_KEY", None)

    def tearDown(self):
        self.stub.uninstall()

    def test_dry_run_when_no_api_key(self):
        from kotodama.primitives.lawfirm_checkout import task_lawfirm_checkout_create
        out = asyncio.run(task_lawfirm_checkout_create(
            product_kind="legal-consult-30min",
            amount_minor=5000,
            currency="USD",
            matter_uri="at://test/matter/1",
            client_email="client@example.com",
            client_name="Test Client",
            stream="consult",
        ))
        self.assertTrue(out["ok"])
        self.assertTrue(out["dry_run"])
        self.assertTrue(out["checkout_url"].startswith("https://checkout.stripe.com/c/pay/"))
        self.assertTrue(out["session_id"].startswith("cs_dry_"))
        self.assertEqual(out["stripe_account"], "stripe_us")

    def test_inr_account_selected(self):
        from kotodama.primitives.lawfirm_checkout import task_lawfirm_checkout_create
        out = asyncio.run(task_lawfirm_checkout_create(
            product_kind="engagement-fixed",
            amount_minor=200000,  # INR 2,000
            currency="INR",
            matter_uri="at://test/matter/2",
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["stripe_account"], "stripe_india")
        self.assertTrue(out["dry_run"])

    def test_negative_amount_rejected(self):
        from kotodama.primitives.lawfirm_checkout import task_lawfirm_checkout_create
        out = asyncio.run(task_lawfirm_checkout_create(
            product_kind="engagement-fixed",
            amount_minor=-100,
            currency="USD",
            matter_uri="at://x/y/z",
        ))
        self.assertFalse(out["ok"])

    def test_metadata_merge(self):
        from kotodama.primitives.lawfirm_checkout import task_lawfirm_checkout_create
        out = asyncio.run(task_lawfirm_checkout_create(
            product_kind="saas-pro",
            amount_minor=500000,
            currency="USD",
            matter_uri="at://test/m/3",
            client_did="did:web:nishith-test.etzhayyim.com",
            stream="saas-pilot",
            metadata='{"campaign":"y1-pilot","logo":"nishith"}',
        ))
        self.assertTrue(out["ok"])

    def test_zero_amount_allowed(self):
        from kotodama.primitives.lawfirm_checkout import task_lawfirm_checkout_create
        # Zero amount = pilot conversion ceremony (free, but tracked)
        out = asyncio.run(task_lawfirm_checkout_create(
            product_kind="saas-pro",
            amount_minor=0,
            currency="USD",
            matter_uri="at://x/m/4",
            stream="saas-pilot",
        ))
        self.assertTrue(out["ok"])


class TestRegistration(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.lawfirm_checkout as p
        self.assertTrue(callable(p.task_lawfirm_checkout_create))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.lawfirm_checkout as p
        p.register("not_a_worker")  # silent no-op


if __name__ == "__main__":
    unittest.main()
