"""Pure tests for lawfirm_tenant primitive (bootstrap / suspend / promote)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    """Replace _execute / _query with controllable mocks."""
    def __init__(self, query_returns=None):
        self.query_returns = query_returns or []
        self.executes: list[tuple[str, dict]] = []

    def install(self):
        import kotodama.primitives.lawfirm_tenant as p
        self._orig_exec = p._execute
        self._orig_q = p._query

        executes = self.executes
        def _exec(sql_str, params):
            executes.append((sql_str, params))
            return True
        p._execute = _exec

        responses = list(self.query_returns)
        def _q(sql_str, params=None):
            return responses.pop(0) if responses else []
        p._query = _q

    def uninstall(self):
        import kotodama.primitives.lawfirm_tenant as p
        p._execute = self._orig_exec
        p._query = self._orig_q


class TestBootstrapHappyPath(unittest.TestCase):
    def setUp(self):
        # Two queries fire in happy path: existing-by-(slug,tier) + slug-collision check
        self.stub = _Stub(query_returns=[[], []])
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_sandbox_provision(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="nishith",
            legal_name="Nishith Desai Associates",
            country="IN",
            data_region="vultr-lax",
            tier="sandbox",
            pilot_lead_id="nishith-desai-2026",
            admin_email="vyapak@nishithdesai.com",
            consent_regions=["IN", "JP"],
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "created")
        self.assertEqual(out["tenantDid"], "did:web:nishith-sandbox-lawfirm.etzhayyim.com")
        self.assertEqual(out["pdsUrl"], "https://nishith-sandbox-lawfirm.etzhayyim.com")
        self.assertEqual(out["kpiDashboardUrl"], "https://kpi-lawfirm.etzhayyim.com/nishith")
        # 3 INSERTs: tenant row, audit event, lead edge
        self.assertEqual(len(self.stub.executes), 3)

    def test_saas_prod_provision_no_lead(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="acme",
            legal_name="Acme & Co",
            country="JP",
            data_region="vultr-lax",
            tier="saas-prod",
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["tenantDid"], "did:web:acme-lawfirm.etzhayyim.com")
        # 2 INSERTs: tenant row + audit (no lead edge for prod)
        self.assertEqual(len(self.stub.executes), 2)


class TestBootstrapValidation(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_invalid_slug_uppercase(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="Nishith", legal_name="X", country="IN", tier="saas-prod",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "InvalidSlug")

    def test_invalid_slug_too_long(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="a" * 17, legal_name="X", country="IN", tier="saas-prod",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "InvalidSlug")

    def test_missing_legal_name(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="xx", legal_name="", country="IN", tier="saas-prod",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "InvalidInput")

    def test_region_unavailable(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="xx", legal_name="X", country="IN",
            data_region="vultr-mum", tier="saas-prod",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "RegionUnavailable")

    def test_invalid_region(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="xx", legal_name="X", country="IN",
            data_region="aws-tokyo", tier="saas-prod",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "InvalidRegion")

    def test_invalid_tier(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="xx", legal_name="X", country="IN", tier="freemium",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "InvalidTier")

    def test_sandbox_requires_pilot_lead(self):
        from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
        out = asyncio.run(task_lawfirm_tenant_bootstrap(
            slug="xx", legal_name="X", country="IN", tier="sandbox",
            pilot_lead_id="",
        ))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "PilotLeadMissing")


class TestBootstrapIdempotency(unittest.TestCase):
    def test_already_exists_returns_existing(self):
        # First _query returns 1 existing row (slug+tier match)
        stub = _Stub(query_returns=[[
            {"vertex_id": "at://did:web:lawfirm.etzhayyim.com/.../sandbox-nishith",
             "status": "active", "tier": "sandbox"}
        ]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
            out = asyncio.run(task_lawfirm_tenant_bootstrap(
                slug="nishith", legal_name="Nishith Desai Associates",
                country="IN", tier="sandbox",
                pilot_lead_id="nishith-desai-2026",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["status"], "already_exists")
            self.assertEqual(out["existing_status"], "active")
            # No INSERTs on idempotent re-call
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()

    def test_slug_taken_by_different_firm(self):
        # First query (existing-by-slug+tier) returns empty,
        # second query (other-tier) returns row with different legal_name
        stub = _Stub(query_returns=[
            [],
            [{"tier": "saas-prod", "legal_name": "Other Firm", "country": "JP"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_bootstrap
            out = asyncio.run(task_lawfirm_tenant_bootstrap(
                slug="acme", legal_name="My Acme", country="IN",
                tier="sandbox", pilot_lead_id="lead-1",
            ))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "SlugTaken")
        finally:
            stub.uninstall()


class TestSuspend(unittest.TestCase):
    def test_suspend_active_tenant(self):
        stub = _Stub(query_returns=[[
            {"vertex_id": "at://...nishith", "tenant_id": "sandbox-nishith", "status": "active"}
        ]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_suspend
            out = asyncio.run(task_lawfirm_tenant_suspend(slug="nishith", reason="pilot-end"))
            self.assertTrue(out["ok"])
            self.assertEqual(out["suspended_count"], 1)
            # 2 _execute calls: UPDATE + INSERT audit event
            self.assertEqual(len(stub.executes), 2)
        finally:
            stub.uninstall()

    def test_suspend_already_suspended_skipped(self):
        stub = _Stub(query_returns=[[
            {"vertex_id": "at://...x", "tenant_id": "sandbox-x", "status": "suspended"}
        ]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_suspend
            out = asyncio.run(task_lawfirm_tenant_suspend(slug="xx"))
            self.assertTrue(out["ok"])
            self.assertEqual(out["suspended_count"], 0)
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()

    def test_suspend_missing_tenant(self):
        stub = _Stub(query_returns=[[]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_suspend
            out = asyncio.run(task_lawfirm_tenant_suspend(slug="ghost"))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "TenantNotFound")
        finally:
            stub.uninstall()


class TestPromote(unittest.TestCase):
    def test_promote_sandbox_to_prod(self):
        # Q1: active sandbox lookup → 1 row
        # Q2: meta lookup → 1 row
        # Q3 (inside bootstrap recursive call): existing-by-(slug,tier=saas-prod) → empty
        # Q4 (inside bootstrap): slug-collision check → returns the sandbox row (same firm, OK)
        stub = _Stub(query_returns=[
            [{"vertex_id": "at://...xx", "tenant_id": "sandbox-xx",
              "country": "IN", "data_region": "vultr-lax"}],
            [{"legal_name": "X Firm", "admin_email_ct": "signal:v1:x@x.com",
              "consent_regions": "IN,JP", "pilot_lead_id": "lead-1"}],
            [],
            [{"tier": "sandbox", "legal_name": "X Firm", "country": "IN"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_promote
            out = asyncio.run(task_lawfirm_tenant_promote(
                slug="xx", monthly_rate_usd=5000.0,
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["status"], "promoted")
            self.assertEqual(out["sandbox_tenant_id"], "sandbox-xx")
            self.assertEqual(out["prod_did"], "did:web:xx-lawfirm.etzhayyim.com")
            self.assertEqual(out["monthly_rate_usd"], 5000.0)
        finally:
            stub.uninstall()

    def test_promote_no_active_sandbox(self):
        stub = _Stub(query_returns=[[]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_tenant import task_lawfirm_tenant_promote
            out = asyncio.run(task_lawfirm_tenant_promote(slug="ghost"))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "ActiveSandboxNotFound")
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
