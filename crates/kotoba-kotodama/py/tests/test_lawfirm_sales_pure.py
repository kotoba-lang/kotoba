"""Pure tests for lawfirm_sales primitive (mail reply + pipeline transition)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    def __init__(self):
        self.executes: list[tuple[str, dict]] = []
        self.queries: list[tuple[str, dict]] = []
        self.next_query_result: list[dict] = []

    def install(self):
        import kotodama.primitives.lawfirm_sales as p
        self._orig_exec = p._execute
        self._orig_query = p._query
        p._execute = lambda sql, params: (self.executes.append((sql, params)), True)[1]
        p._query = lambda sql, params=None: (self.queries.append((sql, params)), self.next_query_result)[1]

    def uninstall(self):
        import kotodama.primitives.lawfirm_sales as p
        p._execute = self._orig_exec
        p._query = self._orig_query


class TestMailReplyWebhook(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_match_by_domain_advances_stage(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_mail_reply_webhook
        # First query (idempotency) returns nothing, second returns lead match
        self.stub.next_query_result = [{"lead_id": "nishith-desai-2026", "stage": "contacted"}]
        out = asyncio.run(task_lawfirm_mail_reply_webhook(
            from_email="vyapak@nishithdesai.com",
            subject="Re: Bakshi & Partners pilot",
            body_preview="Happy to discuss next week.",
            graph_event_id="",  # no idempotency key, no dup check
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["matched_lead_id"], "nishith-desai-2026")
        self.assertTrue(out["stage_advanced"])
        self.assertEqual(out["new_stage"], "engaged")

    def test_no_match_persists_inbound_event_anyway(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_mail_reply_webhook
        self.stub.next_query_result = []
        out = asyncio.run(task_lawfirm_mail_reply_webhook(
            from_email="random@unknown.com",
            subject="Hello",
            body_preview="...",
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["matched_lead_id"], "")
        self.assertFalse(out["stage_advanced"])
        # Should still have INSERTed the outreach event
        inserted_event = any("INSERT INTO vertex_lawfirm_outreach_event" in q for q, _ in self.stub.executes)
        self.assertTrue(inserted_event)

    def test_idempotency_dedup(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_mail_reply_webhook
        # idempotency check returns existing → duplicate
        self.stub.next_query_result = [{"vertex_id": "at://x/y/1"}]
        out = asyncio.run(task_lawfirm_mail_reply_webhook(
            from_email="vyapak@nishithdesai.com",
            subject="Re: ...",
            graph_event_id="evt-12345",
        ))
        self.assertTrue(out.get("duplicate"))

    def test_missing_from_email_rejected(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_mail_reply_webhook
        out = asyncio.run(task_lawfirm_mail_reply_webhook(from_email=""))
        self.assertFalse(out["ok"])


class TestPipelineTransition(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_valid_transition(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_pipeline_transition
        self.stub.next_query_result = [{"stage": "engaged"}]
        out = asyncio.run(task_lawfirm_pipeline_transition(
            lead_id="nishith-desai-2026",
            to_stage="meeting_set",
            reason="confirmed Tuesday slot",
            decided_by_did="did:web:k-bakshi.etzhayyim.com",
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["from_stage"], "engaged")
        self.assertEqual(out["to_stage"], "meeting_set")

    def test_invalid_stage_rejected(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_pipeline_transition
        out = asyncio.run(task_lawfirm_pipeline_transition(
            lead_id="x", to_stage="invalid_stage_name",
        ))
        self.assertFalse(out["ok"])

    def test_unknown_lead_rejected(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_pipeline_transition
        self.stub.next_query_result = []
        out = asyncio.run(task_lawfirm_pipeline_transition(
            lead_id="ghost-lead", to_stage="engaged",
        ))
        self.assertFalse(out["ok"])


class TestRecordOutreach(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_outbound_updates_last_touch(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_record_outreach
        out = asyncio.run(task_lawfirm_record_outreach(
            lead_id="nishith-desai-2026", event_kind="mail_sent",
            direction="out", subject="Pilot intro", body_preview="...",
            actor_did="did:web:k-bakshi.etzhayyim.com",
        ))
        self.assertTrue(out["ok"])
        # Should INSERT event + UPDATE lead.last_touch_at
        sqls = [q for q, _ in self.stub.executes]
        self.assertTrue(any("INSERT INTO vertex_lawfirm_outreach_event" in q for q in sqls))
        self.assertTrue(any("UPDATE vertex_lawfirm_lead SET last_touch_at" in q for q in sqls))

    def test_missing_lead_rejected(self):
        from kotodama.primitives.lawfirm_sales import task_lawfirm_record_outreach
        out = asyncio.run(task_lawfirm_record_outreach(lead_id=""))
        self.assertFalse(out["ok"])


class TestRegistration(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.lawfirm_sales as p
        for fn in (p.task_lawfirm_mail_reply_webhook,
                   p.task_lawfirm_pipeline_transition,
                   p.task_lawfirm_record_outreach):
            self.assertTrue(callable(fn))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.lawfirm_sales as p
        p.register("not_a_worker")  # silent no-op


if __name__ == "__main__":
    unittest.main()
