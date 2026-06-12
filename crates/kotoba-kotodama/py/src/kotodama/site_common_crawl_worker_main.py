"""Dedicated Zeebe worker for site.etzhayyim.com Common Crawl ingest tasks."""

from __future__ import annotations

import asyncio
import logging
import os

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.ingest.site_common_crawl import (
    task_site_cc_acquire_cursor,
    task_site_cc_advance_cursor,
    task_site_cc_complete_run,
    task_site_cc_create_run,
    task_site_cc_plan,
    task_site_cc_record_artifacts,
    task_site_cc_run_phase,
    task_site_cc_verify_visibility,
)
from kotodama.zeebe_worker_main import task_rw_health_probe

LOG = logging.getLogger("site_common_crawl_worker")
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


def register_site_common_crawl_tasks(worker: LangServerWorker) -> None:
    short_timeout_ms = 120_000
    medium_timeout_ms = 300_000
    long_timeout_ms = int(os.environ.get("SITE_CC_ZEEBE_TASK_TIMEOUT_MS", "21600000"))
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(
        task_rw_health_probe
    )
    worker.task(task_type="site.commonCrawl.createRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_create_run
    )
    worker.task(task_type="site.commonCrawl.plan", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_plan
    )
    worker.task(task_type="site.commonCrawl.acquireCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_acquire_cursor
    )
    worker.task(task_type="site.commonCrawl.runPhase", single_value=False, timeout_ms=long_timeout_ms)(
        task_site_cc_run_phase
    )
    worker.task(task_type="site.commonCrawl.recordArtifacts", single_value=False, timeout_ms=medium_timeout_ms)(
        task_site_cc_record_artifacts
    )
    worker.task(task_type="site.commonCrawl.verifyVisibility", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_verify_visibility
    )
    worker.task(task_type="site.commonCrawl.advanceCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_advance_cursor
    )
    worker.task(task_type="site.commonCrawl.completeRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_site_cc_complete_run
    )


async def main() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_site_common_crawl_tasks(worker)
    LOG.info("site_common_crawl_worker starting, gateway=%s", GATEWAY)
    LOG.info(
        "registered tasks: rw.health.probe, site.commonCrawl.{createRun,plan,acquireCursor,runPhase,recordArtifacts,verifyVisibility,advanceCursor,completeRun}"
    )
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
