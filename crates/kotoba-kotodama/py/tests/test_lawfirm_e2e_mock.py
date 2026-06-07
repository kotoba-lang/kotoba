"""
End-to-end mock test for lawfirm.etzhayyim.com full revenue lifecycle.

Verifies the integrated flow with stubbed DB + LLM:
  1. matter intake
  2. PwC clearance request → CEO HITL → no_conflict → cleared
  3. mail outreach + reply received → stage advanced
  4. eSign request → envelope sent (dry_run)
  5. Stripe payment webhook → invoice + payment persisted
  6. KPI snapshot reflects revenue

This is a pure test: no live DB, no live LLM, no live Stripe.
Asserts that the SQL statements + control flow execute end-to-end.
"""

from __future__ import annotations

import asyncio
import json
import unittest


class TestLawfirmE2EMock(unittest.TestCase):
    def setUp(self):
        # Stub all DB writes/reads across the four primitive modules
        self.executes: list[tuple[str, dict]] = []
        self.queries: list[tuple[str, dict]] = []
        self._patches = []
        for name in ("lawfirm_pwc", "lawfirm_marketing", "lawfirm_esign_kpi", "lawfirm_sales"):
            mod = __import__(f"kotodama.primitives.{name}", fromlist=[name])
            for attr in ("_execute", "_query"):
                if hasattr(mod, attr):
                    self._patches.append((mod, attr, getattr(mod, attr)))
                    if attr == "_execute":
                        setattr(mod, attr, lambda sql, params, _e=self.executes: (_e.append((sql, params)), True)[1])
                    else:
                        setattr(mod, attr, lambda sql, params=None, _q=self.queries, _name=name: (_q.append((sql, params)), self._mock_query(_name, sql))[1])
        # Stub sa_rowcount globally (lawfirm_marketing uses it inline)
        from kotodama import db_alchemy
        self._orig_sa_rowcount = db_alchemy.sa_rowcount
        db_alchemy.sa_rowcount = lambda stmt, params: (self.executes.append(("sa_rowcount", params)), 1)[1]

    def tearDown(self):
        for mod, attr, orig in self._patches:
            setattr(mod, attr, orig)
        from kotodama import db_alchemy
        db_alchemy.sa_rowcount = self._orig_sa_rowcount

    def _mock_query(self, mod_name: str, sql: str) -> list[dict]:
        """Return canned rows based on which primitive is asking."""
        sql_lower = sql.lower()
        if "from vertex_lawfirm_lead" in sql_lower and "lead_id" in sql_lower and "stage" in sql_lower:
            # _query inside pipeline_transition or reply webhook lookup
            return [{"lead_id": "nishith-desai-2026", "stage": "contacted"}]
        if "from vertex_lawfirm_outreach_event" in sql_lower and "asset_uri" in sql_lower:
            # idempotency check returns nothing
            return []
        if "mv_lawfirm_revenue_monthly" in sql_lower:
            return [{
                "month": "2026-08",
                "currency": "USD",
                "stream": "advocate-fee",
                "amount_minor_total": 50000,
                "payment_count": 1,
            }]
        if "mv_lawfirm_outstanding_invoices" in sql_lower:
            return [{"cnt": 0, "total_minor": 0}]
        if "mv_lawfirm_marketing_publish_calendar" in sql_lower:
            return [{"compliance_check": "approved", "cnt": 5}]
        if "vertex_lawfirm_matter" in sql_lower and "active" in sql_lower:
            return [{"cnt": 1}]
        return []

    def test_full_pipeline(self):
        # 1. PwC clearance request
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_persist_request
        clearance = asyncio.run(task_lawfirm_pwc_persist_request(
            matter_uri="at://test/matter/nda-001",
            client_name="Nishith Desai Associates",
            matter_summary="SaaS pilot SOW review",
            requested_by_did="did:web:k-bakshi.etzhayyim.com",
            sla_hours=72,
        ))
        self.assertTrue(clearance["ok"])
        self.assertIn("clearance_uri", clearance)

        # 2. CEO clearance decision = no_conflict
        from kotodama.primitives.lawfirm_pwc import task_lawfirm_pwc_apply_decision
        decision = asyncio.run(task_lawfirm_pwc_apply_decision(
            clearance_uri=clearance["clearance_uri"],
            clearance_decision="no_conflict",
            pwc_response_text="Confirmed no overlap.",
            matter_uri="at://test/matter/nda-001",
        ))
        self.assertEqual(decision["clearance_status"], "cleared")

        # 3. Inbound mail reply received
        from kotodama.primitives.lawfirm_sales import task_lawfirm_mail_reply_webhook
        reply = asyncio.run(task_lawfirm_mail_reply_webhook(
            from_email="vyapak@nishithdesai.com",
            subject="Re: Pilot — happy to proceed",
            body_preview="Let's schedule the demo.",
            graph_event_id="evt-mock-1",
        ))
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["matched_lead_id"], "nishith-desai-2026")
        self.assertTrue(reply["stage_advanced"])

        # 4. Pipeline transition: engaged → meeting_set
        from kotodama.primitives.lawfirm_sales import task_lawfirm_pipeline_transition
        transition = asyncio.run(task_lawfirm_pipeline_transition(
            lead_id="nishith-desai-2026",
            to_stage="meeting_set",
            reason="confirmed slot",
            decided_by_did="did:web:k-bakshi.etzhayyim.com",
        ))
        self.assertTrue(transition["ok"])

        # 5. eSign request (dry_run since no DocuSign cred in test env)
        from kotodama.primitives.lawfirm_esign_kpi import task_lawfirm_esign_request
        esign = asyncio.run(task_lawfirm_esign_request(
            document_kind="pilotSOW",
            matter_uri="at://test/matter/nda-001",
            recipients=[{"email": "vyapak@nishithdesai.com", "name": "Vyapak Desai", "role": "client"}],
            document_pdf_b64="JVBERi0xLjQKJ...",
            provider="docusign",
        ))
        self.assertTrue(esign["ok"])
        self.assertTrue(esign.get("dry_run"))

        # 6. Stripe webhook: invoice paid event
        from kotodama.primitives.lawfirm_marketing import task_lawfirm_payment_stripe_webhook
        stripe_evt = asyncio.run(task_lawfirm_payment_stripe_webhook(
            event_id="evt_test_001",
            type="invoice.paid",
            livemode=False,
            stripe_account="acct_test_in",
            data=json.dumps({
                "object": {
                    "id": "in_test_001",
                    "amount_paid": 500000,
                    "currency": "usd",
                    "metadata": {
                        "matter_uri": "at://test/matter/nda-001",
                        "stream": "saas-pilot",
                        "client_did": "did:web:nishith-desai-test.etzhayyim.com",
                    },
                    "total": 500000,
                    "hosted_invoice_url": "https://invoice.stripe.com/test",
                }
            }),
            signature_header="",  # signature verify skipped without secret env
        ))
        self.assertTrue(stripe_evt["ok"])
        self.assertEqual(stripe_evt["amount_minor"], 500000)
        self.assertEqual(stripe_evt["currency"], "USD")

        # 7. KPI snapshot reflects revenue
        from kotodama.primitives.lawfirm_esign_kpi import task_lawfirm_kpi_snapshot
        kpi = asyncio.run(task_lawfirm_kpi_snapshot(
            window_months=6, currency="USD",
            requester_did="did:web:j-kawasaki.etzhayyim.com",
        ))
        self.assertTrue(kpi["ok"])
        self.assertEqual(len(kpi["revenue_by_month"]), 1)
        self.assertEqual(kpi["revenue_by_month"][0]["amount_minor_total"], 50000)
        self.assertEqual(kpi["active_matter_count"], 1)

        # Sanity: at least 6 INSERTs/UPDATEs across the lifecycle
        self.assertGreaterEqual(len(self.executes), 6)


if __name__ == "__main__":
    unittest.main()
