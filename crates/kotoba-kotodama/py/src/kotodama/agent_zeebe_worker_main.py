"""Dedicated Zeebe worker for the local active-inference agent loop."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.primitives.agent_economy import task_agent_runtime_autopilot_tick
from kotodama.zeebe_worker_main import (
    task_agent_adapt_policy,
    task_agent_build_dispatch_receipt_observation,
    task_agent_classify_real_world_effect,
    task_agent_evaluate_expected_free_energy,
    task_agent_evaluate_viability,
    task_agent_inbound_email_to_observation,
    task_agent_plan_real_world_dispatch,
    task_agent_record_active_inference_tick,
    task_agent_record_dispatch_receipt,
    task_agent_record_homeostasis_metric_observation,
    task_agent_record_homeostasis_snapshot,
    task_generic_audit_emit,
    task_generic_db_insert,
    task_generic_hash_json,
)

LOG = logging.getLogger("agent_zeebe_worker")


async def task_mailer_send_email(**kwargs):
    from kotodama.ingest import mailer

    return await asyncio.to_thread(mailer.send_email, **kwargs)


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("AGENT_ZEEBE_TASK_TIMEOUT_MS", "120000"))
    registrations = {
        "agent.evaluateExpectedFreeEnergy": task_agent_evaluate_expected_free_energy,
        "agent.recordActiveInferenceTick": task_agent_record_active_inference_tick,
        "agent.classifyRealWorldEffect": task_agent_classify_real_world_effect,
        "agent.planRealWorldDispatch": task_agent_plan_real_world_dispatch,
        "agent.buildDispatchReceiptObservation": task_agent_build_dispatch_receipt_observation,
        "agent.recordDispatchReceipt": task_agent_record_dispatch_receipt,
        "agent.inboundEmailToObservation": task_agent_inbound_email_to_observation,
        "agent.evaluateViability": task_agent_evaluate_viability,
        "agent.recordHomeostasisSnapshot": task_agent_record_homeostasis_snapshot,
        "agent.recordHomeostasisMetricObservation": task_agent_record_homeostasis_metric_observation,
        "agent.runtime.autopilotTick": task_agent_runtime_autopilot_tick,
        "agent.adaptPolicy": task_agent_adapt_policy,
        "generic.db.insert": task_generic_db_insert,
        "generic.audit.emit": task_generic_audit_emit,
        "generic.hash.json": task_generic_hash_json,
        "mailer.sendEmail": task_mailer_send_email,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)
    LOG.info("agent zeebe worker registered %d task types via %s", len(registrations), gateway)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    task = asyncio.create_task(worker.work())
    await stop.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    load_env_file()
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    os.environ.setdefault("RW_SYNC_POOL", "0")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
