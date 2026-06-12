"""Pure tests for lawfirm_intake primitive (intake + matter creation)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    def install(self):
        import kotodama.primitives.lawfirm_intake as p
        self._orig_exec = p._execute
        self._orig_q = p._query
        p._execute = lambda *a, **k: True
        p._query = lambda *a, **k: []

    def uninstall(self):
        import kotodama.primitives.lawfirm_intake as p
        p._execute = self._orig_exec
        p._query = self._orig_q


class TestIntakeSubmit(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_happy_path_english(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            client_name="Jane Doe", client_email="jane@example.com",
            summary="Need cross-border M&A advisory.",
            consent_status="accepted",
        ))
        self.assertTrue(out["ok"])
        self.assertTrue(out["intake_id"])
        self.assertTrue(out["intake_uri"].startswith(
            "at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.intake/"
        ))
        self.assertIn("Thank you", out["next_steps_message"])

    def test_hindi_returns_localized_message(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            lang="hi", client_name="राम कुमार",
            client_email="ram@example.in",
            summary="वैवाहिक सलाह चाहिए",
            consent_status="accepted",
        ))
        self.assertTrue(out["ok"])
        self.assertIn("धन्यवाद", out["next_steps_message"])

    def test_unknown_lang_falls_back_to_english(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            lang="qq",  # not in localization table
            client_name="X", client_email="x@example.com",
            summary="hello", consent_status="accepted",
        ))
        self.assertTrue(out["ok"])
        self.assertIn("Thank you", out["next_steps_message"])

    def test_consent_required(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            client_name="X", client_email="x@example.com",
            summary="hello", consent_status="declined",
        ))
        self.assertFalse(out["ok"])
        self.assertIn("DPDP", out["error"])

    def test_missing_required_fields(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            client_name="", client_email="", summary="",
            consent_status="accepted",
        ))
        self.assertFalse(out["ok"])

    def test_estimated_response_hours_default(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_intake_submit
        out = asyncio.run(task_lawfirm_intake_submit(
            client_name="X", client_email="x@x.com",
            summary="hello", consent_status="accepted",
        ))
        self.assertEqual(out["estimated_response_hours"], 48)


class TestMatterCreate(unittest.TestCase):
    def setUp(self):
        self.stub = _Stub()
        self.stub.install()

    def tearDown(self):
        self.stub.uninstall()

    def test_happy_path_pending_pwc(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="advisory",
            lead_advocate_did="did:web:k-bakshi.etzhayyim.com",
            subject="Cross-border M&A advisory for Indian acquirer",
            jurisdiction="IND",
            fee_structure="hourly",
            fee_amount_minor=25000,
            currency="USD",
        ))
        self.assertTrue(out["ok"])
        self.assertTrue(out["matter_id"])
        self.assertTrue(out["matter_uri"].startswith(
            "at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.matter/"
        ))
        self.assertEqual(out["status"], "pending_pwc")

    def test_skip_pwc_clearance_makes_active(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="ip",
            lead_advocate_did="did:web:k-bakshi.etzhayyim.com",
            subject="IP filing — out of PwC scope (k-bakshi attests)",
            skip_pwc_clearance=True,
        ))
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "active")

    def test_intake_uri_propagates(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="advisory",
            lead_advocate_did="did:web:k-bakshi.etzhayyim.com",
            subject="from intake",
            intake_uri="at://test/intake/abc-123",
        ))
        self.assertTrue(out["ok"])
        # The UPDATE on intake row is run; we can verify _execute was called twice
        # (1 INSERT matter + 1 UPDATE intake)

    def test_missing_required_fields(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="", lead_advocate_did="", subject="",
        ))
        self.assertFalse(out["ok"])

    def test_co_counsel_dids_serialized(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="litigation",
            lead_advocate_did="did:web:k-bakshi.etzhayyim.com",
            subject="multi-counsel matter",
            co_counsel_dids=["did:web:co1.etzhayyim.com", "did:web:co2.etzhayyim.com"],
        ))
        self.assertTrue(out["ok"])

    def test_currency_inr(self):
        from kotodama.primitives.lawfirm_intake import task_lawfirm_matter_create
        out = asyncio.run(task_lawfirm_matter_create(
            matter_type="advisory",
            lead_advocate_did="did:web:k-bakshi.etzhayyim.com",
            subject="Indian SMB engagement",
            fee_structure="fixed",
            fee_amount_minor=2_500_000,  # INR 25,000
            currency="INR",
        ))
        self.assertTrue(out["ok"])


class TestEncryptionField(unittest.TestCase):
    def test_signal_v1_prefix(self):
        from kotodama.primitives.lawfirm_intake import _enc_field
        self.assertEqual(_enc_field("hello"), "signal:v1:hello")
        self.assertEqual(_enc_field(""), "")

    def test_localization_table(self):
        from kotodama.primitives.lawfirm_intake import _NEXT_STEPS_MESSAGES
        for lang in ("en", "hi", "ta", "te", "bn", "ja"):
            self.assertIn(lang, _NEXT_STEPS_MESSAGES)
            self.assertTrue(_NEXT_STEPS_MESSAGES[lang])


class TestRegistration(unittest.TestCase):
    def test_module_importable(self):
        import kotodama.primitives.lawfirm_intake as p
        self.assertTrue(callable(p.task_lawfirm_intake_submit))
        self.assertTrue(callable(p.task_lawfirm_matter_create))

    def test_register_requires_zeebe_worker(self):
        import kotodama.primitives.lawfirm_intake as p
        p.register("not_a_worker")  # silent no-op


if __name__ == "__main__":
    unittest.main()
