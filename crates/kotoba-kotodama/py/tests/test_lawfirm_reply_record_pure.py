"""Pure tests for lawfirm_reply_record primitive."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    def __init__(self, query_returns=None):
        self.query_returns = query_returns or []
        self.executes: list[tuple[str, dict]] = []

    def install(self):
        import kotodama.primitives.lawfirm_reply_record as p
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
        import kotodama.primitives.lawfirm_reply_record as p
        p._execute = self._orig_exec
        p._query = self._orig_q


class TestSentimentClassifier(unittest.TestCase):
    def test_positive_keyword(self):
        from kotodama.primitives.lawfirm_reply_record import _classify_sentiment
        score, label = _classify_sentiment("Happy to schedule a call next week.")
        self.assertGreater(score, 0)
        self.assertEqual(label, "positive")

    def test_negative_keyword(self):
        from kotodama.primitives.lawfirm_reply_record import _classify_sentiment
        score, label = _classify_sentiment("Not interested at this time, please remove.")
        self.assertLess(score, 0)
        self.assertEqual(label, "negative")

    def test_neutral_no_cues(self):
        from kotodama.primitives.lawfirm_reply_record import _classify_sentiment
        score, label = _classify_sentiment("Received your note. Will revert.")
        self.assertEqual(score, 0.0)
        self.assertEqual(label, "neutral")


class TestSubjectStripping(unittest.TestCase):
    def test_strips_re_prefix(self):
        from kotodama.primitives.lawfirm_reply_record import _strip_subject_prefix
        self.assertEqual(_strip_subject_prefix("Re: Original subject"), "Original subject")
        self.assertEqual(_strip_subject_prefix("RE: RE: Re: deep thread"), "deep thread")
        self.assertEqual(_strip_subject_prefix("Fwd: forwarded note"), "forwarded note")
        self.assertEqual(_strip_subject_prefix("plain subject"), "plain subject")


class TestRecordReplyHappyPath(unittest.TestCase):
    def test_match_by_email_advances_stage(self):
        stub = _Stub(query_returns=[
            # Idempotency check (graph_event_id) — no prior
            [],
            # from_email match — 1 row
            [{"lead_id": "khaitan-2026", "target_name": "Khaitan & Co", "stage": "contacted"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="rabindra.jhunjhunwala@khaitanco.com",
                subject="Re: AT-Protocol-native matter intake for Khaitan",
                body_preview="Happy to schedule a 30-min next week.",
                graph_event_id="evt_abc",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["matched_lead_id"], "khaitan-2026")
            self.assertTrue(out["stage_advanced"])
            self.assertEqual(out["new_stage"], "meeting_requested")
            self.assertEqual(out["sentiment_label"], "positive")
            # 2 _execute: outreach_event INSERT + lead UPDATE
            self.assertEqual(len(stub.executes), 2)
            update_params = stub.executes[1][1]
            self.assertEqual(update_params["st"], "meeting_requested")
        finally:
            stub.uninstall()


class TestRecordReplyNegativeSentiment(unittest.TestCase):
    def test_negative_sets_stage_lost(self):
        stub = _Stub(query_returns=[
            [],  # idempotency
            [{"lead_id": "azb-2026", "target_name": "AZB", "stage": "contacted"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="zia.mody@azbpartners.com",
                subject="Re: pilot",
                body_preview="Not interested. Please remove from your list.",
                graph_event_id="evt_neg",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["new_stage"], "lost")
            self.assertEqual(out["sentiment_label"], "negative")
            self.assertEqual(stub.executes[1][1]["st"], "lost")
        finally:
            stub.uninstall()


class TestRecordReplyIdempotent(unittest.TestCase):
    def test_duplicate_graph_event_skipped(self):
        stub = _Stub(query_returns=[
            # Idempotency: existing event found
            [{"vertex_id": "at://existing-reply"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="x@x.com", subject="Re: x",
                graph_event_id="evt_dup",
            ))
            self.assertTrue(out["ok"])
            self.assertTrue(out["duplicate"])
            self.assertEqual(out["outreach_event_uri"], "at://existing-reply")
            # No state mutated
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestRecordReplySubjectFallback(unittest.TestCase):
    def test_subject_thread_match_when_email_unmatched(self):
        # No graph_event_id → idempotency check skipped
        stub = _Stub(query_returns=[
            [],  # from_email returns empty
            # subject fallback finds match
            [{"lead_id": "trilegal-2026", "target_name": "Trilegal", "stage": "contacted"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="forwarded-by-assistant@trilegal.com",
                subject="Re: AT-Protocol matter intake",
                body_preview="Forwarding to Sridhar — he'll reply directly.",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["matched_lead_id"], "trilegal-2026")
            self.assertTrue(out["matched"])
        finally:
            stub.uninstall()


class TestRecordReplyUnmatched(unittest.TestCase):
    def test_unmatched_returns_ok_no_retry_storm(self):
        # No graph_event_id → idempotency check skipped
        stub = _Stub(query_returns=[
            [],  # from_email no match
            # no subject fallback (subject empty)
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="random@spam.com",
                subject="",
                body_preview="random",
            ))
            self.assertTrue(out["ok"])  # ok=true so Graph doesn't retry
            self.assertFalse(out["matched"])
            self.assertEqual(out["matched_lead_id"], "")
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestRecordReplyMissingFromEmail(unittest.TestCase):
    def test_missing_from_email_rejected(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(from_email=""))
            self.assertFalse(out["ok"])
            self.assertIn("from_email", out["error"])
        finally:
            stub.uninstall()


class TestRecordReplyAlreadyAdvancedStage(unittest.TestCase):
    def test_meeting_requested_does_not_re_advance(self):
        # Lead already at meeting_requested → reply should just bump last_reply_at
        # without overwriting the stage backwards.
        stub = _Stub(query_returns=[
            [],
            [{"lead_id": "ind-2026", "target_name": "IndusLaw", "stage": "meeting_requested"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_reply_record import task_lawfirm_record_reply
            out = asyncio.run(task_lawfirm_record_reply(
                from_email="avimukt@induslaw.com",
                subject="Re: pilot",
                body_preview="Looping in our paralegal.",
            ))
            self.assertTrue(out["ok"])
            self.assertFalse(out["stage_advanced"])
            self.assertEqual(out["new_stage"], "meeting_requested")
            # 2 executes: outreach_event INSERT + last_reply_at UPDATE only
            self.assertEqual(len(stub.executes), 2)
            update_sql = stub.executes[1][0]
            self.assertNotIn("stage = ", update_sql)  # stage NOT re-set
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
