"""Pure tests for lawfirm_cadence_dispatch primitive."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    """Mock _execute / _query / _dispatch_send_draft / _read_eml."""
    def __init__(self, query_returns=None, eml_returns=None, dispatch_returns=None):
        self.query_returns = query_returns or []
        self.eml_returns = eml_returns or {}        # rel_path -> parsed dict | None
        self.dispatch_returns = dispatch_returns or []
        self.executes: list[tuple[str, dict]] = []
        self.dispatches: list[tuple[dict, bool]] = []

    def install(self):
        import kotodama.primitives.lawfirm_cadence_dispatch as p
        self._orig_exec = p._execute
        self._orig_q = p._query
        self._orig_disp = p._dispatch_send_draft
        self._orig_eml = p._read_eml

        executes = self.executes
        def _exec(sql_str, params):
            executes.append((sql_str, params))
            return True
        p._execute = _exec

        responses = list(self.query_returns)
        def _q(sql_str, params=None):
            return responses.pop(0) if responses else []
        p._query = _q

        dispatch_resp = list(self.dispatch_returns)
        dispatches = self.dispatches
        def _disp(parsed, send_now=False):
            dispatches.append((parsed, send_now))
            return dispatch_resp.pop(0) if dispatch_resp else {"ok": True, "via": "test"}
        p._dispatch_send_draft = _disp

        eml_map = self.eml_returns
        def _eml(rel_path):
            return eml_map.get(rel_path)
        p._read_eml = _eml

    def uninstall(self):
        import kotodama.primitives.lawfirm_cadence_dispatch as p
        p._execute = self._orig_exec
        p._query = self._orig_q
        p._dispatch_send_draft = self._orig_disp
        p._read_eml = self._orig_eml


def _khaitan_parsed():
    return {
        "to": ["rabindra.jhunjhunwala@khaitanco.com"],
        "cc": ["haigreve.khaitan@khaitanco.com"],
        "subject": "AT-Protocol-native matter intake for Khaitan",
        "body_text": "Rabindra,\n\nHope you're well.",
        "x_lead_id": "khaitan-2026",
        "x_cadence_step": "T+0-warm-intro",
    }


class TestOutreachPathExtraction(unittest.TestCase):
    def test_extracts_outbox_path(self):
        from kotodama.primitives.lawfirm_cadence_dispatch import _outreach_path_from_notes
        notes = "Tier 2 #1, target Rabindra Jhunjhunwala. Outreach: outbox/08a-khaitan-warm-intro.eml"
        self.assertEqual(_outreach_path_from_notes(notes), "outbox/08a-khaitan-warm-intro.eml")

    def test_returns_none_when_missing(self):
        from kotodama.primitives.lawfirm_cadence_dispatch import _outreach_path_from_notes
        self.assertIsNone(_outreach_path_from_notes("just a free-text note"))
        self.assertIsNone(_outreach_path_from_notes(""))


class TestEmlParsing(unittest.TestCase):
    def test_parses_headers_and_body(self):
        from kotodama.primitives.lawfirm_cadence_dispatch import _parse_eml
        raw = (
            "From: k.bakshi@etzhayyim.com\n"
            "To: a@x.com, b@x.com\n"
            "Cc: c@x.com\n"
            "Subject: Hello\n"
            "X-Lead-Id: foo-2026\n"
            "X-Cadence-Step: T+0-warm-intro\n"
            "\n"
            "First line of body.\n"
            "Second line."
        )
        out = _parse_eml(raw)
        self.assertEqual(out["to"], ["a@x.com", "b@x.com"])
        self.assertEqual(out["cc"], ["c@x.com"])
        self.assertEqual(out["subject"], "Hello")
        self.assertEqual(out["x_lead_id"], "foo-2026")
        self.assertEqual(out["x_cadence_step"], "T+0-warm-intro")
        self.assertIn("First line", out["body_text"])
        self.assertIn("Second line", out["body_text"])


class TestDispatchHappyPath(unittest.TestCase):
    def test_dispatches_due_lead_and_bumps_stage(self):
        stub = _Stub(
            query_returns=[
                # rows = leads SELECT
                [{
                    "lead_id": "khaitan-2026",
                    "target_name": "Khaitan & Co",
                    "target_email": "rabindra.jhunjhunwala@khaitanco.com",
                    "notes": "Tier 2. Outreach: outbox/08a-khaitan-warm-intro.eml",
                    "next_action_at": "2026-05-26",
                }],
                # idempotency check: existing event = empty
                [],
            ],
            eml_returns={"outbox/08a-khaitan-warm-intro.eml": _khaitan_parsed()},
            dispatch_returns=[{"ok": True, "via": "com.etzhayyim.apps.microsoft.sendDraft"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails())
            self.assertTrue(out["ok"])
            self.assertEqual(out["dispatched_count"], 1)
            self.assertEqual(out["skipped_count"], 0)
            self.assertEqual(out["dispatched"][0]["lead_id"], "khaitan-2026")
            self.assertFalse(out["dispatched"][0]["send_now"])  # default = draft
            # Default send_now=False
            self.assertEqual(stub.dispatches[0][1], False)
            # 2 INSERTs: outreach_event + lead UPDATE
            self.assertEqual(len(stub.executes), 2)
        finally:
            stub.uninstall()

    def test_send_now_true_propagates(self):
        stub = _Stub(
            query_returns=[
                [{"lead_id": "x", "target_name": "X", "target_email": "x@x.com",
                  "notes": "Outreach: outbox/test.eml", "next_action_at": "2026-05-09"}],
                [],
            ],
            eml_returns={"outbox/test.eml": _khaitan_parsed()},
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails(send_now=True))
            self.assertTrue(out["ok"])
            self.assertEqual(stub.dispatches[0][1], True)
            self.assertTrue(out["dispatched"][0]["send_now"])
        finally:
            stub.uninstall()


class TestDispatchSkipReasons(unittest.TestCase):
    def test_skip_no_outreach_path(self):
        stub = _Stub(query_returns=[
            [{"lead_id": "lead-no-path", "target_name": "X",
              "target_email": "x@x.com", "notes": "free text only",
              "next_action_at": "2026-05-09"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails())
            self.assertEqual(out["dispatched_count"], 0)
            self.assertEqual(out["skipped_count"], 1)
            self.assertEqual(out["skipped"][0]["reason"], "no_outreach_path")
            # No state mutated
            self.assertEqual(len(stub.executes), 0)
            self.assertEqual(len(stub.dispatches), 0)
        finally:
            stub.uninstall()

    def test_skip_already_sent(self):
        stub = _Stub(query_returns=[
            [{"lead_id": "khaitan-2026", "target_name": "Khaitan",
              "target_email": "x@x.com",
              "notes": "Outreach: outbox/08a-khaitan-warm-intro.eml",
              "next_action_at": "2026-05-09"}],
            # idempotency check returns existing event
            [{"vertex_id": "at://existing-event"}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails())
            self.assertEqual(out["dispatched_count"], 0)
            self.assertEqual(out["skipped_count"], 1)
            self.assertEqual(out["skipped"][0]["reason"], "already_sent")
            self.assertEqual(len(stub.executes), 0)
            self.assertEqual(len(stub.dispatches), 0)
        finally:
            stub.uninstall()

    def test_skip_eml_unreadable(self):
        stub = _Stub(
            query_returns=[
                [{"lead_id": "ghost", "target_name": "G",
                  "target_email": "x@x.com",
                  "notes": "Outreach: outbox/missing.eml",
                  "next_action_at": "2026-05-09"}],
                [],  # idempotency empty
            ],
            eml_returns={},  # _read_eml returns None
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails())
            self.assertEqual(out["dispatched_count"], 0)
            self.assertEqual(out["skipped_count"], 1)
            self.assertEqual(out["skipped"][0]["reason"], "eml_unreadable")
        finally:
            stub.uninstall()


class TestDispatchMixedBatch(unittest.TestCase):
    def test_three_rows_mixed(self):
        stub = _Stub(
            query_returns=[
                # Three leads
                [
                    {"lead_id": "ok", "target_name": "OK", "target_email": "ok@x.com",
                     "notes": "Outreach: outbox/ok.eml", "next_action_at": "2026-05-09"},
                    {"lead_id": "dup", "target_name": "Dup", "target_email": "d@x.com",
                     "notes": "Outreach: outbox/ok.eml", "next_action_at": "2026-05-09"},
                    {"lead_id": "noeml", "target_name": "NoEml", "target_email": "n@x.com",
                     "notes": "free text", "next_action_at": "2026-05-09"},
                ],
                # ok lead idempotency: empty (will dispatch)
                [],
                # dup lead idempotency: already-sent
                [{"vertex_id": "at://dup-event"}],
                # noeml lead has no outreach path → no idempotency check
            ],
            eml_returns={"outbox/ok.eml": _khaitan_parsed()},
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_due_mails
            out = asyncio.run(task_cadence_dispatch_due_mails())
            self.assertEqual(out["dispatched_count"], 1)
            self.assertEqual(out["skipped_count"], 2)
            reasons = {s["reason"] for s in out["skipped"]}
            self.assertEqual(reasons, {"already_sent", "no_outreach_path"})
        finally:
            stub.uninstall()


def _followup_template():
    return {
        "to": [],  # template — recipient computed from lead row
        "cc": [],
        "subject": "Quick follow-up — pilot slot still held",
        "body_text": (
            "{{partner_first_name}},\n\n"
            "Following up on the note last week about the matter platform pilot\n"
            "for {{firm_short_name}}. No pressure — slot held through next week.\n"
        ),
    }


def _release_template():
    return {
        "to": [],
        "cc": [],
        "subject": "Closing the loop — and door stays open",
        "body_text": (
            "{{partner_first_name}},\n\n"
            "This will be my last note on the matter platform pilot. Door stays open.\n"
        ),
    }


class TestFollowUpT5d(unittest.TestCase):
    def test_drafts_followup_when_no_reply(self):
        # Step 1 (T+5d) returns 1 lead; Step 2 (T+12d) returns 0
        stub = _Stub(
            query_returns=[
                # T+5d step query
                [{"lead_id": "khaitan-2026", "target_name": "Khaitan & Co",
                  "target_email": "rabindra.jhunjhunwala@khaitanco.com",
                  "notes": "Tier 2 #1", "stage": "contacted"}],
                # T+12d step query
                [],
            ],
            eml_returns={
                "outbox/templates/cadence-touch2-d5-light-followup.eml": _followup_template(),
            },
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_follow_ups
            out = asyncio.run(task_cadence_dispatch_follow_ups())
            self.assertTrue(out["ok"])
            self.assertEqual(out["dispatched_count"], 1)
            self.assertEqual(out["dispatched"][0]["next_kind"], "followup_5d_sent")
            self.assertEqual(out["dispatched"][0]["lead_id"], "khaitan-2026")
            self.assertFalse(out["dispatched"][0]["send_now"])
            # Substitution applied: partner_first_name='Rabindra', firm_short_name='Khaitan'
            sent_body = stub.dispatches[0][0]["body_text"]
            self.assertIn("Rabindra", sent_body)
            self.assertIn("Khaitan", sent_body)
            # 2 _execute: outreach_event INSERT + lead UPDATE (no stage change)
            self.assertEqual(len(stub.executes), 2)
            update_sql = stub.executes[1][0]
            self.assertIn("UPDATE vertex_lawfirm_lead", update_sql)
            self.assertNotIn("stage = ", update_sql)  # touch-only, no stage change
        finally:
            stub.uninstall()


class TestFollowUpT12dStageLost(unittest.TestCase):
    def test_t12d_advances_stage_to_lost(self):
        stub = _Stub(
            query_returns=[
                [],  # T+5d step empty
                # T+12d step
                [{"lead_id": "ghost", "target_name": "Ghost Firm",
                  "target_email": "ghost@ghost.com",
                  "notes": "tier2", "stage": "contacted"}],
            ],
            eml_returns={
                "outbox/templates/cadence-touch3-d12-soft-release.eml": _release_template(),
            },
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_follow_ups
            out = asyncio.run(task_cadence_dispatch_follow_ups())
            self.assertEqual(out["dispatched_count"], 1)
            self.assertEqual(out["dispatched"][0]["next_kind"], "soft_release_sent")
            self.assertEqual(out["dispatched"][0]["stage_after"], "lost")
            # Update SQL must include stage = 'lost'
            update_sql = stub.executes[1][0]
            update_params = stub.executes[1][1]
            self.assertIn("stage = :stage", update_sql)
            self.assertEqual(update_params["stage"], "lost")
        finally:
            stub.uninstall()


class TestFollowUpEmptyState(unittest.TestCase):
    def test_no_eligible_leads_returns_zero(self):
        stub = _Stub(query_returns=[[], []])  # both step queries empty
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_follow_ups
            out = asyncio.run(task_cadence_dispatch_follow_ups())
            self.assertTrue(out["ok"])
            self.assertEqual(out["dispatched_count"], 0)
            self.assertEqual(out["skipped_count"], 0)
            self.assertEqual(len(stub.executes), 0)
            self.assertEqual(len(stub.dispatches), 0)
        finally:
            stub.uninstall()


class TestFollowUpTemplateUnreadable(unittest.TestCase):
    def test_skip_when_template_missing(self):
        # T+5d returns a row, but template is missing
        stub = _Stub(
            query_returns=[
                [{"lead_id": "x", "target_name": "X",
                  "target_email": "x@x.com", "notes": "n", "stage": "contacted"}],
                [],  # T+12d empty
            ],
            eml_returns={},  # _read_eml returns None for the template
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_follow_ups
            out = asyncio.run(task_cadence_dispatch_follow_ups())
            self.assertEqual(out["dispatched_count"], 0)
            self.assertEqual(out["skipped_count"], 1)
            self.assertEqual(out["skipped"][0]["reason"], "template_unreadable")
            self.assertEqual(out["skipped"][0]["step"], "T+5d-light-followup")
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestFollowUpSendNowPropagation(unittest.TestCase):
    def test_send_now_true_passed_through(self):
        stub = _Stub(
            query_returns=[
                [{"lead_id": "x", "target_name": "X Firm",
                  "target_email": "p@x.com", "notes": "n", "stage": "contacted"}],
                [],
            ],
            eml_returns={
                "outbox/templates/cadence-touch2-d5-light-followup.eml": _followup_template(),
            },
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_cadence_dispatch import task_cadence_dispatch_follow_ups
            out = asyncio.run(task_cadence_dispatch_follow_ups(send_now=True))
            self.assertEqual(stub.dispatches[0][1], True)
            self.assertTrue(out["dispatched"][0]["send_now"])
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
