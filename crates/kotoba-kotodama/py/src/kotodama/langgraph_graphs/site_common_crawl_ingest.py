"""site.commonCrawl.ingest - LangGraph resident ingest wrapper.

Runs the same site Common Crawl ingest task sequence previously owned by the
Zeebe BPMN process ``ingest_site_common_crawl_delta``.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from kotodama.ingest import site_common_crawl as SCC


class SiteCommonCrawlIngestState(TypedDict, total=False):
    runId: str
    sourceId: str
    mode: str
    requestedBy: str
    crawl: str
    domainFilter: str
    phases: str
    limit: int
    minPages: int
    batchSize: int
    dryRun: bool
    ccDataDir: str
    allowSubprocess: bool
    timeoutSec: int
    ok: bool
    error: str | None
    siteCcPlan: dict[str, Any]
    shardKey: str
    artifactStats: dict[str, Any]
    verified: bool


def _input_json(state: SiteCommonCrawlIngestState) -> str:
    payload = {
        "crawl": state.get("crawl", "CC-MAIN-2026-12"),
        "domainFilter": state.get("domainFilter", ""),
        "phases": state.get("phases", "graph,intel,domain-ingest"),
        "limit": state.get("limit", 0),
        "minPages": state.get("minPages", 0),
        "batchSize": state.get("batchSize", 200),
        "dryRun": state.get("dryRun", False),
    }
    return json.dumps(payload, sort_keys=True)


async def create_run(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_create_run(
        runId=state.get("runId", ""),
        sourceId=state.get("sourceId", SCC.SOURCE_ID),
        mode=state.get("mode", "delta"),
        requestedBy=state.get("requestedBy", "langgraph-resident"),
        inputJson=_input_json(state),
        crawl=state.get("crawl", "CC-MAIN-2026-12"),
        dryRun=bool(state.get("dryRun", False)),
    )


async def plan(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return SCC.task_site_cc_plan(
        crawl=state.get("crawl", "CC-MAIN-2026-12"),
        domainFilter=state.get("domainFilter", ""),
        phases=state.get("phases", "graph,intel,domain-ingest"),
        limit=int(state.get("limit", 0) or 0),
        minPages=int(state.get("minPages", 0) or 0),
        batchSize=int(state.get("batchSize", 200) or 200),
        dryRun=bool(state.get("dryRun", False)),
        ccDataDir=state.get("ccDataDir", ""),
    )


async def acquire_cursor(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_acquire_cursor(
        runId=str(state["runId"]),
        sourceId=state.get("sourceId", SCC.SOURCE_ID),
        shardKey=state.get("shardKey", ""),
        crawl=state.get("crawl", "CC-MAIN-2026-12"),
        domainFilter=state.get("domainFilter", ""),
        dryRun=bool(state.get("dryRun", False)),
        siteCcPlan=state.get("siteCcPlan"),
    )


async def run_download(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await _run_phase(state, "download")


async def run_graph(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await _run_phase(state, "graph")


async def run_intel(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await _run_phase(state, "intel")


async def run_domain_ingest(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await _run_phase(state, "domain-ingest")


async def _run_phase(state: SiteCommonCrawlIngestState, phase: str) -> dict[str, Any]:
    result = await SCC.task_site_cc_run_phase(
        phase=phase,
        siteCcPlan=state.get("siteCcPlan"),
        timeoutSec=int(state.get("timeoutSec", 21600) or 21600),
        allowSubprocess=bool(state.get("allowSubprocess", False)),
    )
    return {f"{phase.replace('-', '_')}Result": result, "ok": bool(result.get("ok"))}


async def record_artifacts(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_record_artifacts(
        runId=str(state["runId"]),
        sourceId=state.get("sourceId", SCC.SOURCE_ID),
        siteCcPlan=state.get("siteCcPlan"),
    )


async def verify_visibility(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_verify_visibility(
        crawl=state.get("crawl", "CC-MAIN-2026-12"),
        artifactStats=state.get("artifactStats"),
        dryRun=bool(state.get("dryRun", False)),
        siteCcPlan=state.get("siteCcPlan"),
    )


async def advance_cursor(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_advance_cursor(
        runId=str(state["runId"]),
        sourceId=state.get("sourceId", SCC.SOURCE_ID),
        shardKey=state.get("shardKey", ""),
        verified=bool(state.get("verified", False)),
        artifactStats=state.get("artifactStats"),
        dryRun=bool(state.get("dryRun", False)),
        siteCcPlan=state.get("siteCcPlan"),
    )


async def complete_run(state: SiteCommonCrawlIngestState) -> dict[str, Any]:
    return await SCC.task_site_cc_complete_run(
        runId=str(state["runId"]),
        verified=bool(state.get("verified", False)),
        artifactStats=state.get("artifactStats"),
        dryRun=bool(state.get("dryRun", False)),
        siteCcPlan=state.get("siteCcPlan"),
    )


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(SiteCommonCrawlIngestState)
    builder.add_node("create_run", create_run)
    builder.add_node("plan", plan)
    builder.add_node("acquire_cursor", acquire_cursor)
    builder.add_node("download", run_download)
    builder.add_node("graph", run_graph)
    builder.add_node("intel", run_intel)
    builder.add_node("domain_ingest", run_domain_ingest)
    builder.add_node("record_artifacts", record_artifacts)
    builder.add_node("verify_visibility", verify_visibility)
    builder.add_node("advance_cursor", advance_cursor)
    builder.add_node("complete_run", complete_run)
    builder.set_entry_point("create_run")
    builder.add_edge("create_run", "plan")
    builder.add_edge("plan", "acquire_cursor")
    builder.add_edge("acquire_cursor", "download")
    builder.add_edge("download", "graph")
    builder.add_edge("graph", "intel")
    builder.add_edge("intel", "domain_ingest")
    builder.add_edge("domain_ingest", "record_artifacts")
    builder.add_edge("record_artifacts", "verify_visibility")
    builder.add_edge("verify_visibility", "advance_cursor")
    builder.add_edge("advance_cursor", "complete_run")
    builder.add_edge("complete_run", END)
    return builder.compile()
