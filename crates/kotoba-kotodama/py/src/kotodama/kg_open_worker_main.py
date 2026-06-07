"""Dedicated Zeebe worker for open-data KG ingest (public internet sources).

Slice = wikidata + crossref (live-grounded clean-public). Entities persist through
the single `ingest.kg_open._persist_entities` seam; the RW→kotoba-datomic refactor
(vendor ADR-2605302130) is performed kotoba-side. See ADR-2605312100.
"""

from __future__ import annotations

import asyncio
import logging
import os

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.ingest.kg_open import (
    task_kgopen_acquire_cursor,
    task_kgopen_advance_cursor,
    task_kgopen_complete_run,
    task_kgopen_create_run,
    task_kgopen_fetch_source,
    task_kgopen_plan,
    task_kgopen_verify_visibility,
)
from kotodama.zeebe_worker_main import task_rw_health_probe

LOG = logging.getLogger("kg_open_worker")
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


def register_kg_open_tasks(worker: LangServerWorker) -> None:
    short_timeout_ms = 120_000
    long_timeout_ms = 300_000
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(
        task_rw_health_probe
    )
    worker.task(task_type="kgOpen.createRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_create_run
    )
    worker.task(task_type="kgOpen.plan", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_plan
    )
    worker.task(task_type="kgOpen.acquireCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_acquire_cursor
    )
    worker.task(task_type="kgOpen.fetchSource", single_value=False, timeout_ms=long_timeout_ms)(
        task_kgopen_fetch_source
    )
    worker.task(task_type="kgOpen.verifyVisibility", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_verify_visibility
    )
    worker.task(task_type="kgOpen.advanceCursor", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_advance_cursor
    )
    worker.task(task_type="kgOpen.completeRun", single_value=False, timeout_ms=short_timeout_ms)(
        task_kgopen_complete_run
    )


async def main() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_kg_open_tasks(worker)
    LOG.info("kg_open_worker starting, gateway=%s", GATEWAY)
    LOG.info(
        "registered tasks: rw.health.probe, kgOpen.{createRun,plan,acquireCursor,fetchSource,verifyVisibility,advanceCursor,completeRun}"
    )
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
