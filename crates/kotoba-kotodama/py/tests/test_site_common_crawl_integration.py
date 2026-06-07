import asyncio
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import site_common_crawl as S
from kotodama.langgraph_graphs import site_common_crawl_ingest as LG


REPO_ROOT = Path(__file__).resolve().parents[4]
BPMN_PATH = REPO_ROOT / "00-contracts/bpmn/com/etzhayyim/ingest/siteCommonCrawlDelta.bpmn"


def _bpmn_task_types() -> list[str]:
    root = ET.parse(BPMN_PATH).getroot()
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "zeebe": "http://camunda.org/schema/zeebe/1.0",
    }
    task_types: list[str] = []
    for task in root.findall(".//bpmn:serviceTask", ns):
        task_def = task.find("./bpmn:extensionElements/zeebe:taskDefinition", ns)
        if task_def is not None:
            task_types.append(str(task_def.attrib["type"]))
    return task_types


def _bpmn_phase_inputs() -> list[str]:
    root = ET.parse(BPMN_PATH).getroot()
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "zeebe": "http://camunda.org/schema/zeebe/1.0",
    }
    phases: list[str] = []
    for input_el in root.findall(".//zeebe:input[@target='phase']", ns):
        phases.append(input_el.attrib["source"].removeprefix('="').removesuffix('"'))
    return phases


def test_site_common_crawl_bpmn_task_contract() -> None:
    root = ET.parse(BPMN_PATH).getroot()
    process = root.find("{http://www.omg.org/spec/BPMN/20100524/MODEL}process")

    assert process is not None
    assert process.attrib["id"] == S.BPMN_PROCESS_ID
    assert process.attrib["isExecutable"] == "true"
    assert _bpmn_task_types() == [
        "site.commonCrawl.createRun",
        "rw.health.probe",
        "site.commonCrawl.plan",
        "site.commonCrawl.acquireCursor",
        "site.commonCrawl.runPhase",
        "site.commonCrawl.runPhase",
        "site.commonCrawl.runPhase",
        "site.commonCrawl.runPhase",
        "site.commonCrawl.recordArtifacts",
        "site.commonCrawl.verifyVisibility",
        "site.commonCrawl.advanceCursor",
        "site.commonCrawl.completeRun",
        "generic.audit.emit",
    ]
    assert _bpmn_phase_inputs() == ["download", "graph", "intel", "domain-ingest"]


def test_site_common_crawl_dry_run_worker_path_is_side_effect_free(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run integration path must not touch DB or subprocesses")

    monkeypatch.setattr(S, "upsert_run", fail_if_called)
    monkeypatch.setattr(S, "upsert_cursor", fail_if_called)
    monkeypatch.setattr(S, "upsert_artifact", fail_if_called)
    monkeypatch.setattr(S, "mark_run_finished", fail_if_called)
    monkeypatch.setattr(S, "_site_counts", fail_if_called)
    monkeypatch.setattr(S, "_run_command", fail_if_called)

    variables = {
        "runId": "site-common-crawl-delta-test",
        "sourceId": "common-crawl",
        "mode": "delta",
        "requestedBy": "pytest",
        "crawl": "CC-MAIN-2026-12",
        "domainFilter": "",
        "phases": "graph,intel,domain-ingest",
        "limit": 1,
        "minPages": 0,
        "batchSize": 200,
        "dryRun": True,
        "ccDataDir": str(tmp_path),
        "allowSubprocess": False,
    }

    async def run_path() -> None:
        variables.update(await S.task_site_cc_create_run(**variables))
        variables.update(S.task_site_cc_plan(**variables))
        variables.update(await S.task_site_cc_acquire_cursor(**variables))

        for phase in _bpmn_phase_inputs():
            phase_variables = {k: v for k, v in variables.items() if k != "phase"}
            variables.update(await S.task_site_cc_run_phase(phase=phase, **phase_variables))
            assert variables["ok"] is True
            assert variables["skipped"] is True

        variables.update(await S.task_site_cc_record_artifacts(**variables))
        variables.update(await S.task_site_cc_verify_visibility(**variables))
        variables.update(await S.task_site_cc_advance_cursor(**variables))
        variables.update(await S.task_site_cc_complete_run(**variables))

    asyncio.run(run_path())

    assert variables["status"] == "completed"
    assert variables["verified"] is True
    assert variables["artifactRecords"] == 0
    assert variables["cursorVertexId"].startswith("dry-run:")
    assert variables["runVertexId"].startswith("dry-run:")


def test_site_common_crawl_langgraph_dry_run_nodes_do_not_touch_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("LangGraph dry-run path must not touch DB or subprocesses")

    monkeypatch.setattr(S, "upsert_run", fail_if_called)
    monkeypatch.setattr(S, "upsert_cursor", fail_if_called)
    monkeypatch.setattr(S, "_run_command", fail_if_called)

    state = {
        "crawl": "CC-MAIN-2026-12",
        "phases": "graph,intel,domain-ingest",
        "dryRun": True,
        "ccDataDir": str(tmp_path),
    }

    async def run_path() -> None:
        state.update(await LG.create_run(state))
        state.update(await LG.plan(state))
        state.update(await LG.acquire_cursor(state))
        state.update(await LG.run_graph(state))

    asyncio.run(run_path())

    assert state["runVertexId"].startswith("dry-run:")
    assert state["cursorVertexId"].startswith("dry-run:")
    assert state["graphResult"]["skipped"] is True
