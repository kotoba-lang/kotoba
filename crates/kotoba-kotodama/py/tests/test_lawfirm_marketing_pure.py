"""
Pure tests for lawfirm_marketing_ops LangGraph + lawfirm_marketing primitive.
"""

from __future__ import annotations

import unittest


def _make_state(**kw):
    from kotodama.langgraph_graphs.lawfirm_marketing_ops import MarketingState
    s: MarketingState = {}  # type: ignore[assignment]
    s.update(kw)
    return s


class TestSupervisorPrefixRouting(unittest.TestCase):
    def _call(self, task_type: str) -> dict:
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import supervisor
        return supervisor(_make_state(task_type=task_type))

    def test_blog_routes_content(self):
        self.assertEqual(self._call("marketing.blogDraft")["kind"], "content")

    def test_linkedin_routes_social(self):
        self.assertEqual(self._call("marketing.linkedinPost")["kind"], "social")

    def test_outreach_routes_outreach(self):
        self.assertEqual(self._call("marketing.outreachMail")["kind"], "outreach")

    def test_platform_routes_platform(self):
        self.assertEqual(self._call("marketing.platformCopy")["kind"], "platform")

    def test_kpi_routes_analytics(self):
        self.assertEqual(self._call("marketing.kpiReport")["kind"], "analytics")

    def test_event_routes_event(self):
        self.assertEqual(self._call("marketing.eventPrep")["kind"], "event")

    def test_keyword_fallback(self):
        self.assertEqual(self._call("write a blog post")["kind"], "content")
        self.assertEqual(self._call("send linkedin update")["kind"], "social")


class TestComplianceGate(unittest.TestCase):
    def test_platform_with_disclaimer_approved(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import compliance_gate
        state = _make_state(brand="platform", body_md="Our platform operator etzhayyim does not provide legal advice.")
        out = compliance_gate(state)
        self.assertEqual(out["compliance_check"], "approved")

    def test_platform_without_disclaimer_needs_review(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import compliance_gate
        state = _make_state(brand="platform", body_md="Buy our SaaS now best price.")
        out = compliance_gate(state)
        self.assertEqual(out["compliance_check"], "needs_review")

    def test_advocate_empty_body_rejected(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import compliance_gate
        state = _make_state(brand="advocate", body_md="", asset_kind="blog_article")
        out = compliance_gate(state)
        self.assertEqual(out["compliance_check"], "rejected")


class TestRouterFunction(unittest.TestCase):
    def test_route_returns_kind(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import _route_kind
        for k in ("content", "social", "outreach", "platform", "analytics", "event"):
            self.assertEqual(_route_kind(_make_state(kind=k)), k)

    def test_route_default_unknown(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import _route_kind
        self.assertEqual(_route_kind(_make_state()), "unknown")


class TestGraphStructure(unittest.TestCase):
    def setUp(self):
        import kotodama.langgraph_graphs.lawfirm_marketing_ops as mod
        self._orig_md = mod._llm_md
        self._orig_json = mod._llm_json
        self._orig_insert = mod._db_insert
        self._orig_query = mod._db_query
        mod._llm_md = lambda *a, **k: "stub markdown"
        mod._llm_json = lambda *a, **k: {"compliance_check": "approved", "compliance_score": 1.0, "compliance_notes": "stub"}
        mod._db_insert = lambda *a, **k: True
        mod._db_query = lambda *a, **k: []

    def tearDown(self):
        import kotodama.langgraph_graphs.lawfirm_marketing_ops as mod
        mod._llm_md = self._orig_md
        mod._llm_json = self._orig_json
        mod._db_insert = self._orig_insert
        mod._db_query = self._orig_query

    def test_graph_compiles(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import build_graph
        g = build_graph()
        self.assertIsNotNone(g)

    def test_graph_has_nodes(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import build_graph
        g = build_graph()
        nodes = list(g.nodes)
        for expected in ("supervisor", "content", "social", "outreach", "platform",
                         "analytics", "event", "compliance_gate", "emit_audit"):
            self.assertIn(expected, nodes, f"node {expected!r} missing")


class TestStripeSignatureVerify(unittest.TestCase):
    def test_valid_signature(self):
        import hmac, hashlib
        from kotodama.primitives.lawfirm_marketing import _verify_stripe_signature
        secret = "whsec_test"
        ts = "1700000000"
        body = '{"id":"evt_x"}'
        sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        header = f"t={ts},v1={sig}"
        self.assertTrue(_verify_stripe_signature(body, header, secret))

    def test_invalid_signature(self):
        from kotodama.primitives.lawfirm_marketing import _verify_stripe_signature
        self.assertFalse(_verify_stripe_signature('{"id":"evt"}', "t=1,v1=deadbeef", "whsec_test"))

    def test_missing_secret(self):
        from kotodama.primitives.lawfirm_marketing import _verify_stripe_signature
        self.assertFalse(_verify_stripe_signature("body", "t=1,v1=x", ""))


class TestPrimitiveRegistration(unittest.TestCase):
    def test_marketing_module_importable(self):
        import kotodama.primitives.lawfirm_marketing as m
        self.assertTrue(callable(m.task_lawfirm_marketing_submit))
        self.assertTrue(callable(m.task_lawfirm_payment_stripe_webhook))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.lawfirm_marketing as m
        m.register("not_a_worker")  # silent no-op


class TestVidFormat(unittest.TestCase):
    def test_vid(self):
        from kotodama.langgraph_graphs.lawfirm_marketing_ops import _vid
        v = _vid("marketingAsset")
        self.assertTrue(v.startswith("at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.marketingAsset/"))


if __name__ == "__main__":
    unittest.main()
