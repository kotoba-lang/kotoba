"""Dedicated Zeebe worker for NDL (国立国会図書館) OAI-PMH metadata ingest.

Keeps NDL harvest isolated from the generic worker so unrelated heavy job types
cannot starve NDL BPMN tokens. Slice 1 = OAI-PMH metadata only (no IIIF / OCR /
blob path). Domain-fact persistence is the single ``ingest.ndl._persist_items``
seam; the RW→kotoba-datomic refactor (ADR-2605302130) is performed kotoba-side.
"""

from __future__ import annotations

import asyncio
import logging
import os

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.ingest.ndl import (
    task_ndl_acquire_cursor,
    task_ndl_advance_cursor,
    task_ndl_complete_run,
    task_ndl_create_run,
    task_ndl_oai_fetch_window,
    task_ndl_oai_plan,
    task_ndl_verify_visibility,
)
from kotodama.zeebe_worker_main import task_rw_health_probe

LOG = logging.getLogger("ndl_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")

GRPC_CHANNEL_OPTIONS = (
    ("grpc.keepalive_time_ms", 20_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
    ("grpc.http2.min_time_between_pings_ms", 10_000),
    ("grpc.http2.min_ping_interval_without_data_ms", 5_000),
    ("grpc.initial_reconnect_backoff_ms", 1_000),
    ("grpc.min_reconnect_backoff_ms", 1_000),
    ("grpc.max_reconnect_backoff_ms", 10_000),
)


def register_ndl_tasks(worker: LangServerWorker) -> None:
    short_timeout_ms = 120_000
    long_timeout_ms = 300_000
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(
        task_rw_health_probe
    )
    worker.task(task_type="ndl.createRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_create_run
    )
    worker.task(task_type="ndl.oai.plan", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_oai_plan
    )
    worker.task(task_type="ndl.acquireCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_acquire_cursor
    )
    worker.task(task_type="ndl.oai.fetchWindow", single_value=False, timeout_ms=long_timeout_ms)(
        task_ndl_oai_fetch_window
    )
    worker.task(task_type="ndl.verifyVisibility", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_verify_visibility
    )
    worker.task(task_type="ndl.advanceCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_advance_cursor
    )
    worker.task(task_type="ndl.completeRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_ndl_complete_run
    )


async def main() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_ndl_tasks(worker)
    LOG.info("ndl_worker starting, gateway=%s", GATEWAY)
    LOG.info(
        "registered tasks: rw.health.probe, ndl.{createRun,oai.plan,acquireCursor,oai.fetchWindow,verifyVisibility,advanceCursor,completeRun}"
    )
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
