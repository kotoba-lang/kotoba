"""Pure tests for lawfirm_esign_kpi primitive (esign.request / esign.webhook / kpi.snapshot)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    """Mock _execute / _query / _provider_create_envelope."""

    def __init__(self, query_returns=None, envelope_return=None):
        self.query_returns = query_returns or []
        self.envelope_return = envelope_return or {
            "ok": True, "envelope_id": "test_env_id",
            "expires_at": "2026-06-01 00:00:00", "signing_urls": [],
        }
        self.executes: list[tuple[str, dict]] = []
        self.envelope_calls: list[tuple] = []

    def install(self):
        import kotodama.primitives.lawfirm_esign_kpi as p
        self._orig_exec = p._execute
        self._orig_q = p._query
        self._orig_env = p._provider_create_envelope

        executes = self.executes
        def _exec(sql_str, params):
            executes.append((sql_str, params))
            return True
        p._execute = _exec

        responses = list(self.query_returns)
        def _q(sql_str, params=None):
            return responses.pop(0) if responses else []
        p._query = _q

        env_ret = self.envelope_return
        env_calls = self.envelope_calls
        def _env(provider, document_kind, matter_uri, recipients,
                document_pdf_b64, template_id, tvars, expires_in_days, callback_url):
            env_calls.append((provider, document_kind, matter_uri,
                              len(recipients), bool(document_pdf_b64),
                              template_id, expires_in_days))
            return env_ret
        p._provider_create_envelope = _env

    def uninstall(self):
        import kotodama.primitives.lawfirm_esign_kpi as p
        p._execute = self._orig_exec
        p._query = self._orig_q
        p._provider_create_envelope = self._orig_env


# ── lawfirm.esign.request tests ────────────────────────────────────────────


class TestEsignRequestHappyPath(unittest.TestCase):
    def test_creates_envelope_and_persists_row(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_request,
            )
            out = asyncio.run(task_lawfirm_esign_request(
                document_kind="pilotSOW",
                matter_uri="at://test/matter-1",
                recipients=[
                    {"email": "vyapak@nishithdesai.com", "name": "Vyapak Desai", "role": "client"},
                    {"email": "j-kawasaki@etzhayyim.com", "name": "Jun Kawasaki", "role": "advocate"},
                ],
                document_pdf_b64="JVBERi0xLjMKJeLjz9MK",
                provider="docusign",
                expires_in_days=14,
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["envelope_id"], "test_env_id")
            # Provider envelope create called once
            self.assertEqual(len(stub.envelope_calls), 1)
            provider, dk, _, recipient_count, has_pdf, _, exp_days = stub.envelope_calls[0]
            self.assertEqual(provider, "docusign")
            self.assertEqual(dk, "pilotSOW")
            self.assertEqual(recipient_count, 2)
            self.assertTrue(has_pdf)
            self.assertEqual(exp_days, 14)
            # DB persist fired once
            self.assertEqual(len(stub.executes), 1)
            self.assertIn("INSERT INTO vertex_lawfirm_esign_request", stub.executes[0][0])
        finally:
            stub.uninstall()


class TestEsignRequestRejectsEmptyRecipients(unittest.TestCase):
    def test_no_recipients_returns_error(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_request,
            )
            out = asyncio.run(task_lawfirm_esign_request(
                document_kind="pilotSOW", recipients=[],
            ))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "no_recipients")
            # No envelope create + no DB write
            self.assertEqual(len(stub.envelope_calls), 0)
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestEsignRequestProviderError(unittest.TestCase):
    def test_provider_error_propagates_no_db_write(self):
        stub = _Stub(envelope_return={"ok": False, "error": "docusign_api_401"})
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_request,
            )
            out = asyncio.run(task_lawfirm_esign_request(
                recipients=[{"email": "x@x.com", "name": "X", "role": "client"}],
                document_pdf_b64="data",
            ))
            self.assertFalse(out["ok"])
            self.assertIn("docusign_api_401", out["error"])
            # No DB write on provider failure
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestEsignRequestDryRun(unittest.TestCase):
    def test_dry_run_flag_propagates(self):
        stub = _Stub(envelope_return={
            "ok": True, "envelope_id": "dry_env",
            "expires_at": "2026-06-01 00:00:00", "dry_run": True,
        })
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_request,
            )
            out = asyncio.run(task_lawfirm_esign_request(
                recipients=[{"email": "x@x.com", "name": "X", "role": "client"}],
            ))
            self.assertTrue(out["ok"])
            self.assertTrue(out["dry_run"])
        finally:
            stub.uninstall()


# ── lawfirm.esign.webhook tests ────────────────────────────────────────────


class TestEsignWebhookHappyPath(unittest.TestCase):
    def test_envelope_completed_updates_status(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_webhook,
            )
            out = asyncio.run(task_lawfirm_esign_webhook(
                envelope_id="env_xyz",
                status="completed",
                completed_at="2026-05-15 10:00:00",
                provider="docusign",
                raw_payload='{"envelope":{"status":"completed"}}',
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["envelope_id"], "env_xyz")
            self.assertEqual(out["status"], "completed")
            self.assertEqual(len(stub.executes), 1)
            self.assertIn("UPDATE vertex_lawfirm_esign_request", stub.executes[0][0])
            params = stub.executes[0][1]
            self.assertEqual(params["status"], "completed")
            self.assertEqual(params["eid"], "env_xyz")
        finally:
            stub.uninstall()


class TestEsignWebhookMissingEnvelope(unittest.TestCase):
    def test_no_envelope_id_returns_error(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_webhook,
            )
            out = asyncio.run(task_lawfirm_esign_webhook(envelope_id=""))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "missing_envelope_id")
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestEsignWebhookCompletedAtAutoFill(unittest.TestCase):
    def test_completed_status_without_completed_at_uses_now(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_webhook,
            )
            out = asyncio.run(task_lawfirm_esign_webhook(
                envelope_id="env_abc", status="completed", completed_at="",
            ))
            self.assertTrue(out["ok"])
            params = stub.executes[0][1]
            # completed_at auto-filled with now timestamp (non-empty)
            self.assertTrue(len(params["completed"]) > 0)
        finally:
            stub.uninstall()

    def test_other_status_without_completed_at_stays_empty(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_esign_webhook,
            )
            out = asyncio.run(task_lawfirm_esign_webhook(
                envelope_id="env_def", status="sent", completed_at="",
            ))
            self.assertTrue(out["ok"])
            params = stub.executes[0][1]
            self.assertEqual(params["completed"], "")
        finally:
            stub.uninstall()


# ── lawfirm.kpi.snapshot tests ─────────────────────────────────────────────


class TestKpiSnapshotRlsAllowsAuthorizedDid(unittest.TestCase):
    def test_kpi_readers_get_data(self):
        stub = _Stub(query_returns=[
            [{"month": "2026-04", "currency": "USD", "stream": "advocate-fee",
              "amount_minor_total": 1500000, "payment_count": 3}],
            [{"cnt": 2, "total_minor": 800000}],
            [{"compliance_check": "ok", "cnt": 5}],
            [{"cnt": 12}],
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_kpi_snapshot,
            )
            out = asyncio.run(task_lawfirm_kpi_snapshot(
                window_months=6, currency="USD",
                requester_did="did:web:j-kawasaki.etzhayyim.com",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(len(out["revenue_by_month"]), 1)
            self.assertEqual(out["outstanding_invoices"]["cnt"], 2)
            self.assertEqual(len(out["marketing_pipeline"]), 1)
            self.assertEqual(out["active_matter_count"], 12)
        finally:
            stub.uninstall()


class TestKpiSnapshotRlsBlocksUnauthorizedDid(unittest.TestCase):
    def test_random_did_rejected(self):
        stub = _Stub()
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_kpi_snapshot,
            )
            out = asyncio.run(task_lawfirm_kpi_snapshot(
                requester_did="did:web:random-attacker.example.com",
            ))
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "rls_denied")
        finally:
            stub.uninstall()


class TestKpiSnapshotEmptyRequesterAllowed(unittest.TestCase):
    def test_empty_requester_did_skips_rls_check(self):
        # Empty requester_did = system-internal call (e.g. cron), bypasses RLS
        stub = _Stub(query_returns=[[], [], [], []])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_kpi_snapshot,
            )
            out = asyncio.run(task_lawfirm_kpi_snapshot(requester_did=""))
            self.assertTrue(out["ok"])
            self.assertEqual(out["active_matter_count"], 0)
        finally:
            stub.uninstall()


class TestKpiSnapshotEmptyDataSafe(unittest.TestCase):
    def test_no_data_returns_safe_defaults(self):
        stub = _Stub(query_returns=[[], [], [], []])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_esign_kpi import (
                task_lawfirm_kpi_snapshot,
            )
            out = asyncio.run(task_lawfirm_kpi_snapshot(
                requester_did="did:web:k-bakshi.etzhayyim.com",
            ))
            self.assertTrue(out["ok"])
            self.assertEqual(out["revenue_by_month"], [])
            self.assertEqual(out["outstanding_invoices"], {"cnt": 0, "total_minor": 0})
            self.assertEqual(out["marketing_pipeline"], [])
            self.assertEqual(out["active_matter_count"], 0)
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
