"""Dedicated Zeebe worker for houbun ingest tasks.

Keep law ingest isolated from the generic worker so unrelated heavy job types
cannot starve houbun BPMN tokens.
"""

from __future__ import annotations

import asyncio
import logging
import os

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.ingest.houbun import (
    task_houbun_acquire_cursor,
    task_houbun_advance_cursor,
    task_houbun_complete_run,
    task_houbun_create_run,
    task_houbun_fetch_egov_jpn,
    task_houbun_plan_egov_jpn,
    task_houbun_verify_visibility,
    task_houbun_write_graph,
)
from kotodama.zeebe_worker_main import task_rw_health_probe

LOG = logging.getLogger("houbun_worker")
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


def register_houbun_tasks(worker: LangServerWorker) -> None:
    short_timeout_ms = 120_000
    long_timeout_ms = 300_000
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(
        task_rw_health_probe
    )
    worker.task(task_type="houbun.createRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_create_run
    )
    worker.task(task_type="houbun.egovJpn.plan", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_plan_egov_jpn
    )
    worker.task(task_type="houbun.acquireCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_acquire_cursor
    )
    worker.task(task_type="houbun.egovJpn.fetch", single_value=False, timeout_ms=long_timeout_ms)(
        task_houbun_fetch_egov_jpn
    )
    worker.task(task_type="houbun.writeGraph", single_value=False, timeout_ms=long_timeout_ms)(
        task_houbun_write_graph
    )
    worker.task(task_type="houbun.verifyVisibility", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_verify_visibility
    )
    worker.task(task_type="houbun.advanceCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_advance_cursor
    )
    worker.task(task_type="houbun.completeRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_houbun_complete_run
    )


async def main() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_houbun_tasks(worker)
    LOG.info("houbun_worker starting, gateway=%s", GATEWAY)
    LOG.info(
        "registered tasks: rw.health.probe, houbun.{createRun,egovJpn.plan,acquireCursor,egovJpn.fetch,writeGraph,verifyVisibility,advanceCursor,completeRun}"
    )
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
