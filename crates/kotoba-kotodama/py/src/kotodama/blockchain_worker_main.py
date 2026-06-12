"""Dedicated Zeebe worker for blockchain ingest tasks.

The generic zeebe worker subscribes to many domain task types. Blockchain
ingest needs RPC credentials and should not compete with the generic worker
for unrelated jobs, so this entrypoint registers only the task types used by
the blockchain ingest BPMN.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel


from kotodama.zeebe_worker_main import (
    _activation_monitor,
    _watchdog,
    task_blockchain_head_ingest,
    task_rw_health_probe,
)


LOG = logging.getLogger("blockchain_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")


async def main() -> None:
    LOG.info("blockchain_worker starting, gateway=%s", GATEWAY)
    channel_options: tuple[tuple[str, int], ...] = (
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
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=channel_options)
    worker = LangServerWorker(channel)

    max_running = int(os.environ.get("BLOCKCHAIN_TASK_MAX_RUNNING", "2"))
    worker.task(
        task_type="blockchain.head.ingest",
        single_value=False,
        timeout_ms=180_000,
        max_jobs_to_activate=1,
        max_running_jobs=max_running,
    )(task_blockchain_head_ingest)
    worker.task(
        task_type="rw.health.probe",
        single_value=False,
        timeout_ms=60_000,
        max_jobs_to_activate=2,
        max_running_jobs=4,
    )(task_rw_health_probe)
    LOG.info(
        "registered blockchain tasks: blockchain.head.ingest(max_running=%s), "
        "rw.health.probe",
        max_running,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    work_task = asyncio.create_task(worker.work())
    watchdog_task = asyncio.create_task(_watchdog(channel, stop))
    activation_task = asyncio.create_task(_activation_monitor(stop))
    await stop.wait()
    LOG.info("shutdown requested")
    for task in (work_task, watchdog_task, activation_task):
        task.cancel()
    for task in (work_task, watchdog_task, activation_task):
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    LOG.info("blockchain_worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
