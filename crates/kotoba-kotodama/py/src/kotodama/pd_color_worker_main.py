"""Dedicated Zeebe worker for public-domain colorization.

The shared zeebe_worker_main subscribes to hundreds of task types. This small
worker keeps the pd-color demo path responsive while reusing the same generic
primitive implementations.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.primitives import ipfs_ingest
from kotodama.zeebe_worker_main import (
    task_generic_audit_emit,
    task_generic_db_bulk_insert,
    task_generic_comfyui_call,
    task_generic_db_insert,
    task_generic_pds_dispatch,
    task_generic_xrpc_invoke,
    task_pd_color_audio_extract_timed_text,
    task_pd_color_audio_generate_dubbed_audio,
    task_pd_color_localization_translate_subtitles,
    task_pd_color_video_colorize_frames,
    task_pd_color_video_encode_package,
    task_pd_color_video_enhance_quality,
    task_pd_color_video_mux_localized_packages,
    task_pd_color_video_restore_frames,
    task_pd_color_video_segment_shots,
)

LOG = logging.getLogger("pd_color_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")


async def main() -> None:
    LOG.info("pd_color_worker starting, gateway=%s", GATEWAY)
    channel = create_langserver_channel(grpc_address=GATEWAY)
    worker = LangServerWorker(channel)

    ipfs_ingest.register(worker, timeout_ms=3_600_000)
    worker.task(task_type="generic.xrpc.invoke", single_value=False, timeout_ms=120_000)(task_generic_xrpc_invoke)
    worker.task(task_type="generic.comfyui.call", single_value=False, timeout_ms=600_000)(task_generic_comfyui_call)
    worker.task(task_type="generic.db.insert", single_value=False, timeout_ms=120_000)(task_generic_db_insert)
    worker.task(task_type="generic.db.bulkInsert", single_value=False, timeout_ms=120_000)(task_generic_db_bulk_insert)
    worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=120_000)(task_generic_audit_emit)
    worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=120_000)(task_generic_pds_dispatch)
    worker.task(task_type="pdColor.video.segmentShots", single_value=False, timeout_ms=600_000)(task_pd_color_video_segment_shots)
    worker.task(task_type="pdColor.video.restoreFrames", single_value=False, timeout_ms=600_000)(task_pd_color_video_restore_frames)
    worker.task(task_type="pdColor.video.colorizeFrames", single_value=False, timeout_ms=600_000)(task_pd_color_video_colorize_frames)
    worker.task(task_type="pdColor.video.enhanceQuality", single_value=False, timeout_ms=600_000)(task_pd_color_video_enhance_quality)
    worker.task(task_type="pdColor.video.encodePackage", single_value=False, timeout_ms=600_000)(task_pd_color_video_encode_package)
    worker.task(task_type="pdColor.audio.extractTimedText", single_value=False, timeout_ms=600_000)(task_pd_color_audio_extract_timed_text)
    worker.task(task_type="pdColor.localization.translateSubtitles", single_value=False, timeout_ms=120_000)(task_pd_color_localization_translate_subtitles)
    worker.task(task_type="pdColor.audio.generateDubbedAudio", single_value=False, timeout_ms=600_000)(task_pd_color_audio_generate_dubbed_audio)
    worker.task(task_type="pdColor.video.muxLocalizedPackages", single_value=False, timeout_ms=600_000)(task_pd_color_video_mux_localized_packages)
    LOG.info(
        "registered pd-color tasks: pdColor.ipfs.ingestMovie, pdColor.video.{segmentShots,restoreFrames,colorizeFrames,enhanceQuality,encodePackage,muxLocalizedPackages}, pdColor.audio.{extractTimedText,generateDubbedAudio}, pdColor.localization.translateSubtitles, generic.{xrpc.invoke,comfyui.call,db.insert,db.bulkInsert,audit.emit,pds.dispatch}"
    )

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
