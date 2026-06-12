"""Explicit Zeebe task registrations for decommissioned standalone actors.

The BPMN contract gate requires every covered task type to resolve to a worker
registration. These task types used to be owned by standalone k8s actors; after
the deployment cleanup, the shared worker registers them as unavailable so old
process definitions fail with a clear terminal result instead of hanging.
"""

from __future__ import annotations

from typing import Any


async def task_decommissioned(**kwargs: Any) -> dict[str, Any]:
    task_type = str(kwargs.get("taskType") or kwargs.get("task_type") or "")
    return {
        "result": {
            "ok": False,
            "error": "legacy standalone Zeebe actor is decommissioned",
            "taskType": task_type,
        }
    }


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    def unavailable(task_type: str) -> Any:
        async def _task(**kwargs: Any) -> dict[str, Any]:
            return await task_decommissioned(taskType=task_type, **kwargs)

        _task.__name__ = "task_" + task_type.replace(".", "_")
        return _task

    worker.task(task_type="comfyui.openai.editImage", single_value=False, timeout_ms=timeout_ms)(unavailable("comfyui.openai.editImage"))
    worker.task(task_type="comfyui.openai.generateImage", single_value=False, timeout_ms=timeout_ms)(unavailable("comfyui.openai.generateImage"))
    worker.task(task_type="livecam.vision.analyzeCamera", single_value=False, timeout_ms=timeout_ms)(unavailable("livecam.vision.analyzeCamera"))
    worker.task(task_type="mediaGamers.eval.models", single_value=False, timeout_ms=timeout_ms)(unavailable("mediaGamers.eval.models"))
    worker.task(task_type="mediaGamers.guide.generate", single_value=False, timeout_ms=timeout_ms)(unavailable("mediaGamers.guide.generate"))
    worker.task(task_type="mediaGamers.guide.resolveTargets", single_value=False, timeout_ms=timeout_ms)(unavailable("mediaGamers.guide.resolveTargets"))
    worker.task(task_type="mediaGamers.knowledge.generateGuide", single_value=False, timeout_ms=timeout_ms)(unavailable("mediaGamers.knowledge.generateGuide"))
    worker.task(task_type="news.liveAudio.transcribeWindow", single_value=False, timeout_ms=timeout_ms)(unavailable("news.liveAudio.transcribeWindow"))
    worker.task(task_type="news.rss.ingestSource", single_value=False, timeout_ms=timeout_ms)(unavailable("news.rss.ingestSource"))
    worker.task(task_type="news.rss.resolveSources", single_value=False, timeout_ms=timeout_ms)(unavailable("news.rss.resolveSources"))
    worker.task(task_type="news.socialArbitrage.discover", single_value=False, timeout_ms=timeout_ms)(unavailable("news.socialArbitrage.discover"))
    worker.task(task_type="news.socialArbitrage.draft", single_value=False, timeout_ms=timeout_ms)(unavailable("news.socialArbitrage.draft"))
    worker.task(task_type="shigotoba.jobs.ingest", single_value=False, timeout_ms=timeout_ms)(unavailable("shigotoba.jobs.ingest"))
    worker.task(task_type="smishing.message.classify", single_value=False, timeout_ms=timeout_ms)(unavailable("smishing.message.classify"))
    worker.task(task_type="smishing.message.deepAnalyze", single_value=False, timeout_ms=timeout_ms)(unavailable("smishing.message.deepAnalyze"))
