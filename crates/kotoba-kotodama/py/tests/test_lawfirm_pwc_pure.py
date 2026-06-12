"""Pure tests for lawfirm_pwc primitive (PwC clearance workflow)."""

from __future__ import annotations

import asyncio
import unittest


class TestPwcPersistRequest(unittest.TestCase):
    def setUp(self):
        import kotodama.primitives.lawfirm_pwc as p
        self._orig_exec = p._execute
        p._execute = lambda *a, **k: True

    def tearDown(self):
        import kotodama.primitives.lawfirm_pwc as p
        p._execute = self._orig_exec

    def test_returns_clearance_uri(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_persist_request
        out = asyncio.run(task_lawfirm_pwc_persist_request(
            matter_uri="at://x/matter/1", client_name="Tata Elxsi",
            matter_summary="advisory", sla_hours=72,
        ))
        self.assertTrue(out["ok"])
        self.assertTrue(out["clearance_uri"].startswith(
            "at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.pwcClearance/"
        ))
        self.assertIn("sla_deadline", out)

    def test_missing_matter_uri_rejected(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_persist_request
        out = asyncio.run(task_lawfirm_pwc_persist_request(
            matter_uri="", client_name="x",
        ))
        self.assertFalse(out["ok"])


class TestPwcApplyDecision(unittest.TestCase):
    def setUp(self):
        import kotodama.primitives.lawfirm_pwc as p
        self._orig_exec = p._execute
        p._execute = lambda *a, **k: True

    def tearDown(self):
        import kotodama.primitives.lawfirm_pwc as p
        p._execute = self._orig_exec

    def test_no_conflict_clears(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_apply_decision
        out = asyncio.run(task_lawfirm_pwc_apply_decision(
            clearance_uri="at://x/c/1", clearance_decision="no_conflict",
            pwc_response_text="No overlap with PwC engagements.",
            matter_uri="at://x/matter/1",
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["clearance_status"], "cleared")

    def test_conflict_declines(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_apply_decision
        out = asyncio.run(task_lawfirm_pwc_apply_decision(
            clearance_uri="at://x/c/2", clearance_decision="conflict",
            matter_uri="at://x/matter/2",
        ))
        self.assertEqual(out["clearance_status"], "declined")

    def test_need_more_info(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_apply_decision
        out = asyncio.run(task_lawfirm_pwc_apply_decision(
            clearance_uri="at://x/c/3", clearance_decision="need_more_info",
        ))
        self.assertEqual(out["clearance_status"], "pending_more_info")

    def test_missing_uri_rejected(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_apply_decision
        out = asyncio.run(task_lawfirm_pwc_apply_decision(
            clearance_uri="", clearance_decision="no_conflict",
        ))
        self.assertFalse(out["ok"])


class TestPwcNotifyCEO(unittest.TestCase):
    def test_log_only_when_dispatcher_unreachable(self):
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_notify_ceo
        # Default env has no dispatcher reachable in unit test env →
        # should fall back to log_only without raising.
        out = asyncio.run(task_lawfirm_pwc_notify_ceo(
            clearance_uri="at://x/c/1", client_name="Tata",
            matter_summary="advisory", sla_deadline="2026-05-11 10:00:00",
        ))
        self.assertTrue(out["ok"])
        self.assertIn(out["notified_via"], ("log_only", "microsoft_teams_email"))


class TestPwcRegistration(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.lawfirm_pwc as p
        for fn in (
            p.task_lawfirm_pwc_persist_request,
            p.task_lawfirm_pwc_notify_ceo,
            p.task_lawfirm_pwc_apply_decision,
        ):
            self.assertTrue(callable(fn))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.lawfirm_pwc as p
        p.register("not_a_worker")  # silent no-op


if __name__ == "__main__":
    unittest.main()
