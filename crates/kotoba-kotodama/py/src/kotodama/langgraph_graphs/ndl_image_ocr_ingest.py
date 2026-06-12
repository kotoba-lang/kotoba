"""ndl.imageOcrIngest — image-first NDL Digital Collections ingest.

Input:
  {
    providerId?: "ndl-dl-online" | "ndl-dl" | "ndl-dl-open",
    query?: string,
    startRecord?: int,
    maxRecords?: int,
    maxItems?: int,
    maxPagesPerItem?: int,
    imageWidth?: int,
    webpQuality?: int,
    ocr?: bool,
    pids?: string[],
    resume?: bool
  }

The graph is intentionally bounded. Full-corpus ingestion is achieved by
re-running with the returned nextStartRecord / persisted cursor policy, not by
holding a multi-million item crawl in one run.
"""

from __future__ import annotations

from typing import Any, TypedDict


class NdlImageOcrIngestState(TypedDict, total=False):
    providerId: str
    query: str
    startRecord: int
    maxRecords: int
    maxItems: int
    maxPagesPerItem: int
    imageWidth: int
    webpQuality: int
    ocr: bool
    pids: list[str]
    resume: bool
    ok: bool
    error: str


async def _run(state: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives.ndl_image_ocr import task_ndl_image_ocr_ingest

    return await task_ndl_image_ocr_ingest(
        providerId=str(state.get("providerId") or "ndl-dl-online"),
        query=str(state.get("query") or ""),
        startRecord=int(state.get("startRecord") or 1),
        maxRecords=int(state.get("maxRecords") or 50),
        maxItems=int(state.get("maxItems") or 10),
        maxPagesPerItem=int(state.get("maxPagesPerItem") or 3),
        imageWidth=int(state.get("imageWidth") or 1280),
        webpQuality=int(state.get("webpQuality") or 82),
        ocr=bool(state.get("ocr", True)),
        pids=[str(pid) for pid in (state.get("pids") or [])],
        resume=bool(state.get("resume", True)),
    )


def build_graph():
    from langgraph.func import entrypoint, task

    @task  # type: ignore[misc]
    async def ingest(state: NdlImageOcrIngestState) -> dict[str, Any]:
        return await _run(dict(state or {}))

    @entrypoint()  # type: ignore[misc]
    async def ndl_image_ocr_ingest(state: NdlImageOcrIngestState) -> dict[str, Any]:
        try:
            return await ingest(state)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    return ndl_image_ocr_ingest
