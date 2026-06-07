"""Cron entrypoint for the Hume text distillation LangGraph pipeline."""

from __future__ import annotations

import asyncio
import json
import os
import time

from kotodama.primitives.hume_distillation import task_hume_distill_run_text_pipeline


async def main() -> None:
    process_id = os.environ.get("HUME_DISTILLATION_PROCESS_ID", "hume_text_distillation_daily")
    variables = {
        "perEmotion": int(os.environ.get("HUME_DISTILLATION_PER_EMOTION", "2")),
        "maxSamples": int(os.environ.get("HUME_DISTILLATION_MAX_SAMPLES", "24")),
        "timeoutMs": int(os.environ.get("HUME_DISTILLATION_TEACHER_TIMEOUT_MS", "120000")),
        "pollIntervalMs": int(os.environ.get("HUME_DISTILLATION_POLL_MS", "1000")),
        "concurrency": int(os.environ.get("HUME_DISTILLATION_CONCURRENCY", "2")),
        "artifactDir": os.environ.get("HUME_DISTILLATION_ARTIFACT_DIR", "/tmp/hume-distillation"),
        "writeArtifacts": os.environ.get("HUME_DISTILLATION_WRITE_ARTIFACTS", "1") != "0",
    }
    started = time.monotonic()
    result = await task_hume_distill_run_text_pipeline(**variables)
    print(
        json.dumps(
            {
                "ok": not bool(result.get("error")),
                "latencyMs": int((time.monotonic() - started) * 1000),
                "processId": process_id,
                "runtimeKind": "langgraph-pregel",
                "variables": result,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
