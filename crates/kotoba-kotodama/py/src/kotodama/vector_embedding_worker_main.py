"""Dedicated Zeebe worker for vector embedding backfill.

Keep embedding model loading isolated from the generic Zeebe worker. This
worker owns `vectorEmbedding.backfillBatch` and the shared `rw.health.probe`
gate used by the BPMN process.
"""

from __future__ import annotations

import asyncio
import logging
import os

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.primitives.vector_embedding import task_vector_embedding_backfill_batch
from kotodama.zeebe_worker_main import task_rw_health_probe

LOG = logging.getLogger("vector_embedding_worker")
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


def register_vector_embedding_tasks(worker: LangServerWorker) -> None:
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(
        task_rw_health_probe
    )
    worker.task(
        task_type="vectorEmbedding.backfillBatch",
        single_value=False,
        timeout_ms=600_000,
    )(task_vector_embedding_backfill_batch)


async def main() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_vector_embedding_tasks(worker)
    LOG.info("vector_embedding_worker starting, gateway=%s", GATEWAY)
    LOG.info("registered tasks: rw.health.probe, vectorEmbedding.backfillBatch")
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
