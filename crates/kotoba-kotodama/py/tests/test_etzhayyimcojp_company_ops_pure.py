"""
Pure (no DB, no LLM) tests for etzhayyim_company_ops LangGraph graph.
Tests supervisor routing, state shape, graph structure.
"""

from __future__ import annotations

import json
import types
import unittest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_state(**kw):
    from kotodama.langgraph_graphs.etzhayyim_company_ops import CompanyOpsState
    s: CompanyOpsState = {}  # type: ignore[assignment]
    s.update(kw)
    return s


class TestSupervisorPrefixRouting(unittest.TestCase):
    def _call(self, task_type: str, payload: dict | None = None) -> dict:
        from kotodama.langgraph_graphs.etzhayyim_company_ops import supervisor
        state = _make_state(task_type=task_type, payload=payload or {})
        return supervisor(state)

    def test_hr_prefix(self):
        out = self._call("hr.onboard")
        self.assertEqual(out["domain"], "hr")
        self.assertIn("prefix match", out["routing_reason"])

    def test_finance_prefix(self):
        out = self._call("finance.journal")
        self.assertEqual(out["domain"], "finance")

    def test_accounting_prefix(self):
        out = self._call("accounting.expense")
        self.assertEqual(out["domain"], "finance")

    def test_legal_prefix(self):
        out = self._call("legal.review")
        self.assertEqual(out["domain"], "legal")

    def test_contract_prefix(self):
        out = self._call("contract.sign")
        self.assertEqual(out["domain"], "legal")

    def test_sales_prefix(self):
        out = self._call("sales.proposal")
        self.assertEqual(out["domain"], "sales")

    def test_crm_prefix(self):
        out = self._call("crm.customer")
        self.assertEqual(out["domain"], "sales")

    def test_governance_prefix(self):
        out = self._call("governance.daily")
        self.assertEqual(out["domain"], "governance")

    def test_okr_prefix(self):
        out = self._call("okr.review")
        self.assertEqual(out["domain"], "governance")

    def test_omega_prefix(self):
        out = self._call("omega.evaluate")
        self.assertEqual(out["domain"], "governance")

    def test_personnel_prefix(self):
        out = self._call("personnel.list")
        self.assertEqual(out["domain"], "personnel")

    def test_role_prefix(self):
        out = self._call("role.assign")
        self.assertEqual(out["domain"], "personnel")

    def test_raci_prefix(self):
        out = self._call("raci.lookup")
        self.assertEqual(out["domain"], "personnel")

    def test_assignment_prefix(self):
        out = self._call("assignment.create")
        self.assertEqual(out["domain"], "personnel")


class TestRouterFunction(unittest.TestCase):
    def test_routes_all_domains(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import _route_domain
        for domain in ("hr", "finance", "legal", "sales", "governance", "personnel"):
            state = _make_state(domain=domain)
            self.assertEqual(_route_domain(state), domain)

    def test_default_governance(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import _route_domain
        state = _make_state()
        self.assertEqual(_route_domain(state), "governance")

    def test_unknown_routes_governance(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import _route_domain
        state = _make_state(domain="unknown")
        self.assertEqual(_route_domain(state), "unknown")


class TestGraphStructure(unittest.TestCase):
    def setUp(self):
        # Stub out DB and LLM to avoid real calls in build_graph
        import kotodama.langgraph_graphs.etzhayyim_company_ops as mod
        self._orig_db = mod._db_insert
        self._orig_query = mod._db_query
        self._orig_llm = mod._llm_structured
        mod._db_insert = lambda *a, **k: True
        mod._db_query = lambda *a, **k: []
        mod._llm_structured = lambda *a, **k: {"domain": "governance", "reason": "stub"}

    def tearDown(self):
        import kotodama.langgraph_graphs.etzhayyim_company_ops as mod
        mod._db_insert = self._orig_db
        mod._db_query = self._orig_query
        mod._llm_structured = self._orig_llm

    def test_build_graph_returns_compiled(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import build_graph
        g = build_graph()
        self.assertIsNotNone(g)

    def test_graph_has_nodes(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import build_graph
        g = build_graph()
        nodes = list(g.nodes)
        for expected in ("supervisor", "hr", "finance", "legal", "sales", "governance", "personnel", "emit_audit"):
            self.assertIn(expected, nodes, f"node {expected!r} missing from graph")


class TestStateTypedDict(unittest.TestCase):
    def test_state_fields_present(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import CompanyOpsState
        hints = CompanyOpsState.__annotations__
        for field in ("task_type", "payload", "domain", "result", "action_items",
                      "omega_score", "floor_violated", "ok", "error"):
            self.assertIn(field, hints, f"field {field!r} missing from CompanyOpsState")


class TestHelpers(unittest.TestCase):
    def test_vid_format(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import _vid
        v = _vid("test")
        self.assertTrue(v.startswith("at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.etzhayyim.test/"))

    def test_now_iso_format(self):
        from kotodama.langgraph_graphs.etzhayyim_company_ops import _now_iso
        ts = _now_iso()
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_llm_structured_error_fallback(self):
        import kotodama.langgraph_graphs.etzhayyim_company_ops as mod
        orig = mod.call_tier if hasattr(mod, "call_tier") else None

        # Patch call_tier inside the module's llm_structured to raise
        import kotodama.llm as llm_mod
        orig_call = llm_mod.call_tier

        def _raise(*a, **k):
            raise RuntimeError("test error")

        llm_mod.call_tier = _raise
        try:
            result = mod._llm_structured("system", "user")
            self.assertIn("error", result)
        finally:
            llm_mod.call_tier = orig_call


class TestetzhayyimcojpOpsPrimitive(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.etzhayyim_ops as ops
        self.assertTrue(callable(ops.task_etzhayyim_ops_submit))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.etzhayyim_ops as ops
        # Non-ZeebeWorker should not raise, just return
        ops.register("not_a_worker")


class TestetzhayyimcojpPersonnelPrimitive(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.etzhayyim_personnel as p
        for fn in (
            p.task_etzhayyim_personnel_load_profile,
            p.task_etzhayyim_personnel_minimax_score,
            p.task_etzhayyim_personnel_notify_deny,
            p.task_etzhayyim_personnel_write_assignment,
        ):
            self.assertTrue(callable(fn))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.etzhayyim_personnel as p
        p.register("not_a_worker")  # silent no-op

    def test_tier3_readers_membership(self):
        import kotodama.primitives.etzhayyim_personnel as p
        for did in (
            "did:web:j-kawasaki.etzhayyim.com",
            "did:web:a-nakamura.etzhayyim.com",
            "did:web:k-bakshi.etzhayyim.com",
        ):
            self.assertIn(did, p._TIER3_READERS)
        self.assertNotIn("did:web:t-chikada.etzhayyim.com", p._TIER3_READERS)

    def test_vid_format(self):
        import kotodama.primitives.etzhayyim_personnel as p
        v = p._vid("personMinimax")
        self.assertTrue(
            v.startswith("at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.etzhayyim.personMinimax/")
        )


if __name__ == "__main__":
    unittest.main()
