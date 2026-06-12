"""Dedicated Zeebe worker for curpus2skill evidence extraction.

Keep corpus-skill evidence extraction isolated from the generic worker so
periodic BPMN tokens do not depend on the broad shared subscription set.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.ingest.curpus2skill import task_curpus2skill_extract_evidence

LOG = logging.getLogger("curpus2skill_worker")
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


def register_curpus2skill_tasks(worker: LangServerWorker) -> None:
    worker.task(task_type="curpus2skill.extractEvidence", single_value=False, timeout_ms=300_000)(
        task_curpus2skill_extract_evidence
    )


async def main() -> None:
    LOG.info("curpus2skill_worker starting, gateway=%s", GATEWAY)
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)
    register_curpus2skill_tasks(worker)
    LOG.info("registered tasks: curpus2skill.extractEvidence")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    work_task = asyncio.create_task(worker.work())
    await stop.wait()
    work_task.cancel()
    try:
        await work_task
    except (asyncio.CancelledError, Exception):
        pass


if __name__ == "__main__":
    asyncio.run(main())
