from __future__ import annotations

import asyncio
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import ma


def test_start_deal_bpmn_binds_ma_runtime_tasks() -> None:
    bpmn_path = (
        Path(__file__).resolve().parents[4]
        / "00-contracts/bpmn/com/etzhayyim/ma/startDealWorkflow.bpmn"
    )
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "zeebe": "http://camunda.org/schema/zeebe/1.0",
    }
    root = ET.parse(bpmn_path).getroot()

    process = root.find("bpmn:process", ns)
    assert process is not None
    assert process.attrib["id"] == "ma_start_deal_workflow"

    task_types = [
        task.find("bpmn:extensionElements/zeebe:taskDefinition", ns).attrib["type"]
        for task in process.findall("bpmn:serviceTask", ns)
    ]
    assert task_types == [
        "ma.salesOrigination.intake",
        "ma.targetScreening.score",
        "ma.investmentAdviser.valuation",
        "ma.buyerMatching.rank",
        "ma.tradeBroker.negotiate",
        "ma.outreach.composeDraft",
        "ma.outreach.prepareMailerSend",
        "ma.outreach.sendApproved",
        "ma.integration.closeAndHandoff",
        "rw.health.probe",
        "ma.writeGraph",
        "generic.audit.emit",
    ]

    write_graph = process.find("bpmn:serviceTask[@id='Task_WriteGraph']", ns)
    assert write_graph is not None
    dry_run = write_graph.find(
        "bpmn:extensionElements/zeebe:ioMapping/zeebe:input[@target='dryRun']",
        ns,
    )
    assert dry_run is not None
    assert dry_run.attrib["source"] == "=false"

    outreach = process.find("bpmn:serviceTask[@id='Task_Outreach']", ns)
    assert outreach is not None
    mailbox = outreach.find(
        "bpmn:extensionElements/zeebe:ioMapping/zeebe:input[@target='mailboxLocal']",
        ns,
    )
    assert mailbox is not None
    assert mailbox.attrib["source"] == '="ma"'

    approval = process.find("bpmn:userTask[@id='Task_ApproveOutreach']", ns)
    assert approval is not None
    group = approval.find(
        "bpmn:extensionElements/zeebe:assignmentDefinition",
        ns,
    )
    assert group is not None
    assert group.attrib["candidateGroups"] == "ma-operators"

    send_approved = process.find("bpmn:serviceTask[@id='Task_SendApproved']", ns)
    assert send_approved is not None
    dry_send = send_approved.find(
        "bpmn:extensionElements/zeebe:ioMapping/zeebe:input[@target='dryRun']",
        ns,
    )
    assert dry_send is not None
    assert dry_send.attrib["source"] == "=true"


def test_ma_deal_workflow_tasks_are_deterministic_enough() -> None:
    intake = asyncio.run(
        ma.task_ma_sales_origination_intake(
            side="sell-side",
            clientName="Acme Holdings",
            targetName="Acme Robotics",
            sector="robotics",
            jurisdiction="JP",
            expectedValueUsd=50_000_000,
        )
    )
    assert intake["dealId"].startswith("ma-deal-")
    assert intake["status"] == "intake-complete"
    assert intake["dealDid"].startswith("did:web:ma.etzhayyim.com:deal:")

    screen = asyncio.run(
        ma.task_ma_target_screening_score(
            dealId=intake["dealId"],
            side=intake["side"],
            sector=intake["sector"],
            jurisdiction=intake["jurisdiction"],
            targetName=intake["targetName"],
            expectedValueUsd=intake["expectedValueUsd"],
        )
    )
    assert 0.45 <= screen["screeningScore"] <= 0.9
    assert screen["screeningVerdict"] in {"advance", "hold-for-review"}

    valuation = asyncio.run(
        ma.task_ma_investment_adviser_valuation(
            dealId=intake["dealId"],
            expectedValueUsd=intake["expectedValueUsd"],
            screeningScore=screen["screeningScore"],
            sector=intake["sector"],
        )
    )
    assert valuation["valuationRangeLowUsd"] < valuation["valuationRangeHighUsd"]
    assert valuation["valuationId"].startswith("ma-valuation-")

    matches = asyncio.run(
        ma.task_ma_buyer_matching_rank(
            dealId=intake["dealId"],
            sector=intake["sector"],
            jurisdiction=intake["jurisdiction"],
            side=intake["side"],
        )
    )
    assert matches["matches"][0]["rank"] == 1
    assert matches["matchedBuyerCount"] >= 0

    negotiation = asyncio.run(
        ma.task_ma_trade_broker_negotiate(
            dealId=intake["dealId"],
            matches=matches["matches"],
            valuationRangeLowUsd=valuation["valuationRangeLowUsd"],
            valuationRangeHighUsd=valuation["valuationRangeHighUsd"],
        )
    )
    assert negotiation["status"] == "negotiation-ready"
    assert "compliance-review" in negotiation["requiredApprovals"]

    outreach = asyncio.run(
        ma.task_ma_outreach_compose_draft(
            **{**intake, **valuation, **matches, **negotiation},
            mailboxLocal="ma",
        )
    )
    assert outreach["status"] == "outreach-draft-ready"
    assert outreach["outreachDraft"]["provider"] == "mailer.etzhayyim.com"
    assert outreach["outreachDraft"]["outboundProvider"] == "resend"
    assert outreach["outreachDraft"]["inboundProvider"] == "cloudflare-email-routing"
    assert outreach["outreachDraft"]["sendNsid"] == "com.etzhayyim.apps.mailer.sendEmail"
    assert outreach["outreachDraft"]["from"] == "ma@etzhayyim.com"
    assert outreach["pendingApproval"]["status"] == "pending"

    blocked_send = asyncio.run(
        ma.task_ma_outreach_prepare_mailer_send(
            outreachDraft=outreach["outreachDraft"],
            outreachApproved=False,
        )
    )
    assert blocked_send["ok"] is False
    assert blocked_send["sendReady"] is False

    approved_send = asyncio.run(
        ma.task_ma_outreach_prepare_mailer_send(
            outreachDraft={
                **outreach["outreachDraft"],
                "recipientEmail": "corpdev@example.com",
            },
            outreachApproved=True,
            approvedBy="did:web:operator.etzhayyim.com",
            approvedAt="2026-04-27T00:00:00Z",
        )
    )
    assert approved_send["ok"] is True
    assert approved_send["sendReady"] is True
    assert approved_send["sendNsid"] == "com.etzhayyim.apps.mailer.sendEmail"
    assert approved_send["mailerSendPayload"]["to"] == "corpdev@example.com"
    assert approved_send["mailerSendPayload"]["from"] == "ma@etzhayyim.com"

    staged_send = asyncio.run(
        ma.task_ma_outreach_send_approved(
            mailerSendPayload=approved_send["mailerSendPayload"],
            sendReady=approved_send["sendReady"],
            dryRun=True,
            sendEnabled=False,
        )
    )
    assert staged_send["ok"] is True
    assert staged_send["sent"] is False
    assert staged_send["request"]["url"] == (
        "https://mailer.etzhayyim.com/xrpc/com.etzhayyim.apps.mailer.sendEmail"
    )

    handoff = asyncio.run(
        ma.task_ma_integration_close_and_handoff(
            dealId=intake["dealId"],
            status=negotiation["status"],
            preferredBuyerCandidateId=negotiation["preferredBuyerCandidateId"],
        )
    )
    assert handoff["status"] == "handoff-ready"
    assert handoff["closingStage"] == "pmi-handoff-ready"


def test_register_exposes_ma_task_types() -> None:
    registered: list[str] = []

    class FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            assert single_value is False
            assert timeout_ms == 123
            registered.append(task_type)

            def decorator(fn):
                return fn

            return decorator

    ma.register(FakeWorker(), timeout_ms=123)
    assert registered == [
        "ma.salesOrigination.intake",
        "ma.targetScreening.score",
        "ma.investmentAdviser.valuation",
        "ma.buyerMatching.rank",
        "ma.tradeBroker.negotiate",
        "ma.outreach.composeDraft",
        "ma.outreach.prepareMailerSend",
        "ma.outreach.sendApproved",
        "ma.integration.closeAndHandoff",
        "ma.writeGraph",
    ]


def _sample_workflow() -> dict:
    intake = asyncio.run(
        ma.task_ma_sales_origination_intake(
            side="sell-side",
            clientName="Acme Holdings",
            targetName="Acme Robotics",
            sector="robotics",
            jurisdiction="JP",
            expectedValueUsd=50_000_000,
        )
    )
    screen = asyncio.run(
        ma.task_ma_target_screening_score(
            dealId=intake["dealId"],
            side=intake["side"],
            sector=intake["sector"],
            jurisdiction=intake["jurisdiction"],
            targetName=intake["targetName"],
            expectedValueUsd=intake["expectedValueUsd"],
        )
    )
    valuation = asyncio.run(
        ma.task_ma_investment_adviser_valuation(
            dealId=intake["dealId"],
            expectedValueUsd=intake["expectedValueUsd"],
            screeningScore=screen["screeningScore"],
            sector=intake["sector"],
        )
    )
    matches = asyncio.run(
        ma.task_ma_buyer_matching_rank(
            dealId=intake["dealId"],
            sector=intake["sector"],
            jurisdiction=intake["jurisdiction"],
            side=intake["side"],
        )
    )
    return {**intake, **screen, **valuation, **matches}


def test_write_graph_dry_run_prepares_ma_rows() -> None:
    out = asyncio.run(ma.task_ma_write_graph(**_sample_workflow(), dryRun=True))

    assert out["ok"] is True
    assert out["dryRun"] is True
    assert out["recordsPrepared"] == 13
    assert len(out["tables"]["vertex_ma_deal"]) == 1
    assert len(out["tables"]["vertex_ma_candidate"]) == 4
    assert len(out["tables"]["vertex_ma_valuation"]) == 1
    assert len(out["tables"]["vertex_ma_match"]) == 3
    assert len(out["tables"]["edge_ma_deal_candidate"]) == 1
    assert len(out["tables"]["edge_ma_deal_buyer"]) == 3


def test_write_graph_requires_rw_health_when_not_dry_run() -> None:
    out = asyncio.run(ma.task_ma_write_graph(**_sample_workflow(), dryRun=False, healthy=False))

    assert out["ok"] is False
    assert out["degraded"] is True


class _Cursor:
    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1
        self._fetch_counts = [1, 4, 1, 3, 1, 3]

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.sqls.append(sql)
        self.params.append(params)

    def fetchone(self) -> tuple[int]:
        return (self._fetch_counts.pop(0),)


class _SyncCursorFactory:
    def __init__(self) -> None:
        self.cursor = _Cursor()

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                return factory.cursor

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_write_graph_writes_and_checks_visibility(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(ma, "sync_cursor", factory)

    out = asyncio.run(ma.task_ma_write_graph(**_sample_workflow(), dryRun=False, healthy=True))

    assert out["ok"] is True
    assert out["recordsPrepared"] == 13
    assert out["recordsVisible"] == 13
    sql_text = "\n".join(factory.cursor.sqls)
    assert "INSERT INTO vertex_ma_deal" in sql_text
    assert "INSERT INTO vertex_ma_candidate" in sql_text
    assert "INSERT INTO vertex_ma_valuation" in sql_text
    assert "INSERT INTO vertex_ma_match" in sql_text
    assert "INSERT INTO edge_ma_deal_candidate" in sql_text
    assert "INSERT INTO edge_ma_deal_buyer" in sql_text
