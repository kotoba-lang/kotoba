"""Pure tests for MoneyForward replacement handlers.

These tests pin the contract at the SQL boundary without requiring
RisingWave. DB helpers are monkeypatched so the assertions focus on argument
normalization, target tables, and returned XRPC payload shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from kotodama.ingest import moneyforward_ops as mf


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, tuple[Any, ...]]] = []
    seq: dict[str, int] = {}

    def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
        calls.append((sql, params))
        return 1

    def next_seq(table: str) -> int:
        seq[table] = seq.get(table, 0) + 1
        return seq[table]

    monkeypatch.setattr(mf, "_execute", execute)
    monkeypatch.setattr(mf, "_next_seq", next_seq)
    monkeypatch.setattr(mf, "now_iso", lambda: "2026-05-08T00:00:00Z")
    return calls


def test_issue_invoice_writes_draft_invoice(fake_db: list[tuple[str, tuple[Any, ...]]]):
    result = mf.issue_invoice(
        owner="works",
        customerDid="did:plc:customer",
        invoiceNumber="INV-001",
        issuedAt="2026-05-08T00:00:00Z",
        dueAt="2026-06-07T00:00:00Z",
        lineItems=[{"description": "retainer", "amount": 1000}],
        taxRate=0.1,
    )

    assert result["invoiceDid"] == "did:plc:etzhayyim-works|com.etzhayyim.apps.seikyu.invoice|inv-001"
    assert result["subtotal"] == 1000
    assert result["taxAmount"] == 100
    assert result["total"] == 1100
    assert result["status"] == "draft"
    assert "vertex_atrecord_seikyu_invoice" in fake_db[0][0]


def test_record_payment_updates_invoice_status(monkeypatch: pytest.MonkeyPatch, fake_db: list[tuple[str, tuple[Any, ...]]]):
    def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if "FROM vertex_atrecord_seikyu_invoice" in sql:
            return {"owner_did": "did:plc:etzhayyim-works", "total": 1100}
        if "SUM(amount)" in sql:
            return {"paid": 1100}
        return None

    monkeypatch.setattr(mf, "_fetch_one", fetch_one)

    result = mf.record_payment_received(
        invoiceDid="did:plc:etzhayyim-works|com.etzhayyim.apps.seikyu.invoice|inv-001",
        paymentDate="2026-05-09",
        amount=1100,
        reference="bank-1",
    )

    assert result["ok"] is True
    assert result["status"] == "paid"
    assert any("vertex_atrecord_seikyu_payment_received" in sql for sql, _ in fake_db)
    assert any("UPDATE vertex_atrecord_seikyu_invoice" in sql for sql, _ in fake_db)


def test_draft_agreement_creates_recurring_schedule_when_amount_present(fake_db: list[tuple[str, tuple[Any, ...]]]):
    result = mf.draft_agreement(
        owner="works",
        counterpartyDid="did:plc:customer",
        title="MSA",
        agreementType="msa",
        effectiveFrom="2026-05-08",
        pdfCid="bafy-contract",
        recurringAmount=5000,
        recurringFrequency="monthly",
    )

    assert result["agreementDid"].startswith("did:plc:etzhayyim-works|com.etzhayyim.apps.keiyaku.agreement|msa-")
    assert any("vertex_atrecord_keiyaku_agreement" in sql for sql, _ in fake_db)
    assert any("vertex_atrecord_seikyu_recurring_schedule" in sql for sql, _ in fake_db)


def test_validate_moneyforward_parity_marks_match(monkeypatch: pytest.MonkeyPatch, fake_db: list[tuple[str, tuple[Any, ...]]]):
    monkeypatch.setattr(mf, "_fetch_one", lambda _sql, _params=(): {"total": 12345})

    result = mf.validate_moneyforward_parity(
        owner="works",
        periodFrom="2026-04-01",
        periodTo="2026-04-30",
        mfExportCid="bafy-mf",
        mfTotal=12345,
    )

    assert result["ok"] is True
    assert result["status"] == "matched"
    assert result["diffAmount"] == 0
    assert any("vertex_kaikei_moneyforward_parity_run" in sql for sql, _ in fake_db)


def test_t3_handlers_store_only_encrypted_refs(fake_db: list[tuple[str, tuple[Any, ...]]]):
    payroll = mf.complete_payroll_run(
        owner="works",
        payrollMonth="2026-05",
        grossTotalEncrypted="signal:v1:gross",
        statutoryTotalEncrypted="signal:v1:tax",
        netTotalEncrypted="signal:v1:net",
    )
    vault = mf.register_mynumber_vault_ref(
        owner="works",
        employeeDid="did:plc:emp",
        vaultRefEncrypted="signal:v1:vault-ref",
        declarationHash="sha256:abc",
    )

    assert payroll["status"] == "completed"
    assert payroll["kaikeiSourceType"] == "com.etzhayyim.apps.jinji.payrollRun.completed"
    assert vault["ok"] is True
    flattened_params = " ".join(str(v) for _, params in fake_db for v in params)
    assert "signal:v1:" in flattened_params
    assert "123456789012" not in flattened_params


def test_register_saas_asset_targets_kaisya_inventory(fake_db: list[tuple[str, tuple[Any, ...]]]):
    result = mf.register_saas_asset(
        owner="works",
        provider="box",
        assetType="folder",
        externalId="folder-1",
        displayName="Finance",
        metadata={"path": "/Finance"},
    )

    assert result["ok"] is True
    assert result["assetDid"] == "did:plc:etzhayyim-works|com.etzhayyim.apps.kaisya.saasAsset|box-folder-folder-1"
    assert any("vertex_kaisya_saas_asset" in sql for sql, _ in fake_db)
