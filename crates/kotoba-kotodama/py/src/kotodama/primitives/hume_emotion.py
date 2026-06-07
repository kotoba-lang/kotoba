"""Hume emotion teacher + distilled student primitives.

This module is the Python/Zeebe replacement for the temporary Cloudflare
Worker path. It keeps long-running Hume batch polling and student fallback in
the Kubernetes worker plane where Zeebe can own retries and timeouts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from kotodama.primitives.hume_student_model_data import MODEL

HUME_API_BASE = os.environ.get("HUME_API_BASE", "https://api.hume.ai").rstrip("/")
EXPRESSION_SUNSET = "2026-06-14"
CAUTION = "Expression scores estimate perceived expression, not a direct claim about internal emotional state."
NON_EMOTION_LABELS = {
    "toxic",
    "severe_toxic",
    "obscene",
    "threat",
    "insult",
    "identity_hate",
}
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "if",
    "in", "is", "it", "of", "on", "or", "so", "that", "the", "this", "to", "we", "what",
    "when", "why", "with", "you",
}


def _api_key() -> str:
    key = (
        os.environ.get("HUME_API_KEY")
        or os.environ.get("HUME_API_251209")
        or os.environ.get("SS_HUME_API_KEY")
        or ""
    ).strip()
    if not key:
        raise RuntimeError("missing HUME_API_KEY")
    return key


def _has_api_key() -> bool:
    try:
        _api_key()
        return True
    except RuntimeError:
        return False


def _http_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{HUME_API_BASE}{path}",
        method=method,
        data=body,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-hume-api-key": _api_key(),
            "user-agent": "etzhayyim-hume-zeebe/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"hume {method} {path} failed {e.code}: {detail}") from e


def _multipart_job_payload(
    job: dict[str, Any],
    files: list[dict[str, Any]] | None = None,
) -> tuple[bytes, str]:
    boundary = f"----etzhayyim-hume-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(b'Content-Disposition: form-data; name="json"\r\n')
    chunks.append(b"Content-Type: application/json\r\n\r\n")
    chunks.append(json.dumps(job).encode("utf-8"))
    chunks.append(b"\r\n")
    for part in files or []:
        chunks.append(f"--{boundary}\r\n".encode())
        filename = str(part.get("name") or part.get("filename") or "input.bin").replace('"', "")
        content_type = str(part.get("mimeType") or part.get("contentType") or "application/octet-stream")
        chunks.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(bytes(part["bytes"]))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _file_bytes(part: dict[str, Any]) -> bytes:
    if "bytes" in part and isinstance(part["bytes"], (bytes, bytearray)):
        return bytes(part["bytes"])
    encoded = (
        part.get("dataBase64")
        or part.get("base64")
        or part.get("contentBase64")
        or part.get("data")
        or ""
    )
    if isinstance(encoded, str) and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[-1]
    if encoded:
        return base64.b64decode(str(encoded), validate=False)
    path = str(part.get("path") or "")
    if path:
        return open(path, "rb").read()
    raise ValueError("file part requires bytes, base64/dataBase64/contentBase64, data URL, or path")


def _normalize_file_parts(files: list[dict[str, Any]] | None = None, fileBase64: str = "") -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for index, item in enumerate(files or []):
        if not isinstance(item, dict):
            continue
        data = _file_bytes(item)
        parts.append(
            {
                "name": item.get("name") or item.get("filename") or f"input-{index + 1}.bin",
                "mimeType": item.get("mimeType") or item.get("contentType") or "application/octet-stream",
                "bytes": data,
                "size": len(data),
            }
        )
    if fileBase64:
        data = _file_bytes({"base64": fileBase64})
        parts.append({"name": "input.bin", "mimeType": "application/octet-stream", "bytes": data, "size": len(data)})
    return parts


def _infer_modality(text: str = "", urls: list[str] | None = None, modality: str = "") -> str:
    selected = (modality or "").strip().lower()
    if selected:
        return selected
    if text and urls:
        return "multimodal"
    if text:
        return "text"
    joined = " ".join(urls or []).lower()
    if any(joined.endswith(ext) or f"{ext}?" in joined for ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm")):
        return "audio"
    if any(joined.endswith(ext) or f"{ext}?" in joined for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "image"
    if urls:
        return "url-media"
    return "unknown"


def _default_models(modality: str) -> dict[str, Any]:
    if modality == "audio":
        return {"prosody": {}}
    if modality == "image":
        return {"face": {}}
    if modality in {"multimodal", "url-media"}:
        return {"language": {"sentiment": {}, "toxicity": {}}, "prosody": {}, "face": {}}
    return {"language": {"sentiment": {}, "toxicity": {}}}


def _submit_expression_job(
    text: str | list[str] = "",
    urls: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    models: dict[str, Any] | None = None,
    modality: str = "",
) -> str:
    texts = _as_string_list(text)
    media_urls = _as_string_list(urls)
    file_parts = _normalize_file_parts(files)
    inferred = _infer_modality(text=" ".join(texts), urls=media_urls, modality=modality)
    job: dict[str, Any] = {
        "models": models or _default_models(inferred),
        "notify": False,
    }
    if texts:
        job["text"] = texts
    if media_urls:
        job["urls"] = media_urls
    body, boundary = _multipart_job_payload(job, file_parts)
    req = urllib.request.Request(
        f"{HUME_API_BASE}/v0/batch/jobs",
        method="POST",
        data=body,
        headers={
            "accept": "application/json",
            "content-type": f"multipart/form-data; boundary={boundary}",
            "x-hume-api-key": _api_key(),
            "user-agent": "etzhayyim-hume-zeebe/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"hume expression job failed {e.code}: {detail}") from e
    job_id = str(data.get("job_id") or "")
    if not job_id:
        raise RuntimeError(f"hume expression job missing job_id: {data}")
    return job_id


def _submit_expression_text_job(text: str | list[str], models: dict[str, Any] | None = None) -> str:
    return _submit_expression_job(text=text, models=models, modality="text")


def _get_expression_job(job_id: str) -> dict[str, Any]:
    return _http_json("GET", f"/v0/batch/jobs/{job_id}", timeout=20)


def _get_expression_predictions(job_id: str) -> Any:
    return _http_json("GET", f"/v0/batch/jobs/{job_id}/predictions", timeout=30)


def _job_state(job: dict[str, Any]) -> str:
    state = job.get("state") if isinstance(job.get("state"), dict) else {}
    status = state.get("status") or state.get("type") or state.get("name") or job.get("status")
    return str(status or "").upper()


def _walk_scores(value: Any, out: list[dict[str, float]]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_scores(item, out)
        return
    if not isinstance(value, dict):
        return
    name = value.get("name") or value.get("emotion") or value.get("label")
    score = value.get("score", value.get("value", value.get("probability")))
    if (
        isinstance(name, str)
        and not re.match(r"^\d+$", name)
        and name.lower() not in NON_EMOTION_LABELS
        and isinstance(score, (int, float))
        and math.isfinite(float(score))
        and 0 <= float(score) <= 1
    ):
        out.append({"name": name, "score": float(score)})
    for nested in value.values():
        _walk_scores(nested, out)


def normalize_expression(predictions: Any, provider: str = "hume") -> dict[str, Any]:
    scores: list[dict[str, float]] = []
    _walk_scores(predictions, scores)
    best: dict[str, float] = {}
    for item in scores:
        name = item["name"]
        score = item["score"]
        if score > best.get(name, -1):
            best[name] = score
    top = [
        {"name": name, "score": score}
        for name, score in sorted(best.items(), key=lambda item: item[1], reverse=True)[:12]
    ]
    primary = top[0] if top else None
    teacher: dict[str, Any]
    if provider == "student":
        teacher = {
            "provider": "student",
            "api": "distilled-expression",
            "distilledFrom": "hume-expression-measurement",
        }
    else:
        teacher = {"provider": "hume", "api": "expression-measurement", "sunset": EXPRESSION_SUNSET}
    return {
        "schema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "primary": primary,
        "topEmotions": top,
        "confidence": primary["score"] if primary else 0,
        "caution": CAUTION,
        "teacher": teacher,
    }


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z']{1,}", (text or "").lower()) if t not in STOP]


def _vectorize(text: str) -> dict[str, float]:
    vocab = set(MODEL["vocab"])
    counts: dict[str, float] = {}
    for token in _tokenize(text):
        if token in vocab:
            counts[token] = counts.get(token, 0.0) + 1.0
    norm = 0.0
    for token, count in list(counts.items()):
        value = count * float(MODEL["idf"].get(token, 1.0))
        counts[token] = value
        norm += value * value
    norm = math.sqrt(norm) or 1.0
    return {token: value / norm for token, value in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * float(b.get(token, 0.0)) for token, value in a.items())


def predict_student_text(text: str) -> dict[str, Any]:
    vec = _vectorize(text)
    scored: list[dict[str, float]] = []
    for name, centroid in MODEL["emotionCentroids"].items():
        if str(name).lower() in NON_EMOTION_LABELS:
            continue
        similarity = _cosine(vec, centroid)
        prior = float(MODEL["primaryPriors"].get(name, 0.0))
        score = max(0.0, min(1.0, similarity * 0.82 + prior * 0.18))
        if score > 0:
            scored.append({"name": name, "score": score})
    fallback = [
        {"name": item["name"], "score": min(0.35, float(item["score"]))}
        for item in MODEL["globalTopEmotions"]
        if str(item.get("name", "")).lower() not in NON_EMOTION_LABELS
    ]
    seen: set[str] = set()
    top: list[dict[str, float]] = []
    for item in sorted(scored + fallback, key=lambda x: x["score"], reverse=True):
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        top.append(item)
        if len(top) >= 12:
            break
    primary = top[0] if top else None
    return {
        "schema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "primary": primary,
        "topEmotions": top,
        "confidence": primary["score"] if primary else 0,
        "caution": CAUTION,
        "teacher": {
            "provider": "student",
            "api": "distilled-expression",
            "distilledFrom": "hume-expression-measurement",
        },
    }


def predict_student_multimodal(
    text: str = "",
    urls: list[str] | None = None,
    modality: str = "",
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inferred = _infer_modality(text=text, urls=urls or [], modality=modality)
    if text:
        normalized = predict_student_text(text)
        normalized["evidence"] = {"modality": inferred, "text": True, "urlCount": len(urls or [])}
        return normalized

    # Try audio head when audio files are present
    if files:
        for part in files:
            if not isinstance(part, dict):
                continue
            mt = str(part.get("mimeType") or part.get("contentType") or "").lower()
            is_audio = mt.startswith("audio/") or "wav" in mt or "mpeg" in mt
            is_image = mt.startswith("image/")
            if not (is_audio or is_image):
                continue
            try:
                raw = _file_bytes(part)
            except Exception:  # noqa: BLE001
                continue

            if is_audio:
                from kotodama.primitives.hume_audio_head import predict_audio_emotion
                result = predict_audio_emotion(raw, caution=CAUTION)
                if result is not None:
                    result["evidence"]["urlCount"] = len(urls or [])
                    return result

            if is_image:
                from kotodama.primitives.hume_image_head import predict_image_emotion
                result = predict_image_emotion(raw, mime_type=mt, caution=CAUTION)
                result["evidence"]["urlCount"] = len(urls or [])
                return result

    # Global-prior fallback (no audio/image bytes available — e.g. URL-only media)
    fallback = [
        {"name": item["name"], "score": min(0.20, float(item["score"]))}
        for item in MODEL["globalTopEmotions"]
        if str(item.get("name", "")).lower() not in NON_EMOTION_LABELS
    ][:12]
    primary = fallback[0] if fallback else None
    return {
        "schema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "primary": primary,
        "topEmotions": fallback,
        "confidence": primary["score"] if primary else 0,
        "caution": CAUTION,
        "teacher": {
            "provider": "student",
            "api": "distilled-expression",
            "distilledFrom": "hume-expression-measurement",
            "note": "url-only media; supply file bytes for audio/image feature inference",
        },
        "evidence": {"modality": inferred, "text": False, "urlCount": len(urls or [])},
    }


async def task_hume_expression_predict_student(
    text: str = "",
    urls: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    modality: str = "",
) -> dict[str, Any]:
    media_urls = _as_string_list(urls)
    file_count = len(files or [])
    if not text and not media_urls and not file_count:
        return {"error": "text, urls, or files are required"}
    inferred = _infer_modality(text=text, urls=media_urls, modality=modality)
    normalized = predict_student_multimodal(text=text, urls=media_urls, modality=inferred, files=files)
    if file_count and not text:
        normalized["evidence"] = {"modality": inferred, "text": False, "urlCount": len(media_urls), "fileCount": file_count}
    return {
        "mode": "student",
        "modality": inferred,
        "model": {
            "schema": MODEL["schema"],
            "rows": MODEL["training"]["rows"],
            "dataHash": MODEL["training"]["dataHash"],
            "algorithm": MODEL["algorithm"],
        },
        "normalized": normalized,
    }


async def task_hume_expression_analyze_teacher(
    text: str = "",
    urls: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    fileBase64: str = "",
    modality: str = "",
    waitForResult: bool = True,
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 5_000,
    models: dict[str, Any] | None = None,
) -> dict[str, Any]:
    media_urls = _as_string_list(urls)
    try:
        file_parts = _normalize_file_parts(files, fileBase64=fileBase64)
    except Exception as e:  # noqa: BLE001
        return {"mode": "teacher", "error": f"invalid files: {e}"}
    if not text and not media_urls and not file_parts:
        return {"error": "text, urls, or files are required"}
    inferred = _infer_modality(text=text, urls=media_urls, modality=modality)
    try:
        job_id = await asyncio.to_thread(_submit_expression_job, text, media_urls, file_parts, models, inferred)
        if not waitForResult:
            return {
                "mode": "teacher",
                "modality": inferred,
                "fileCount": len(file_parts),
                "jobId": job_id,
                "status": "submitted",
                "sunset": EXPRESSION_SUNSET,
            }
        started = time.monotonic()
        while (time.monotonic() - started) * 1000 < int(timeoutMs or 120_000):
            job = await asyncio.to_thread(_get_expression_job, job_id)
            state = _job_state(job)
            if state in {"COMPLETED", "SUCCEEDED", "SUCCESS"}:
                predictions = await asyncio.to_thread(_get_expression_predictions, job_id)
                return {
                    "mode": "teacher",
                    "modality": inferred,
                    "fileCount": len(file_parts),
                    "jobId": job_id,
                    "normalized": normalize_expression(predictions),
                    "raw": predictions,
                }
            if state in {"FAILED", "ERROR", "CANCELED", "CANCELLED"}:
                return {"mode": "teacher", "modality": inferred, "fileCount": len(file_parts), "jobId": job_id, "error": f"hume job failed: {state}"}
            await asyncio.sleep(max(int(pollIntervalMs or 5_000), 500) / 1000)
        return {"mode": "teacher", "modality": inferred, "fileCount": len(file_parts), "jobId": job_id, "pending": True, "error": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"mode": "teacher", "modality": inferred, "error": str(e)}


async def task_hume_expression_analyze(
    text: str = "",
    urls: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    fileBase64: str = "",
    modality: str = "",
    mode: str = "auto",
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 5_000,
) -> dict[str, Any]:
    """Unified Zeebe task.

    mode=teacher: require Hume teacher
    mode=student: local student only
    mode=auto: try teacher when HUME_API_KEY is present, fallback to student
    """
    media_urls = _as_string_list(urls)
    selected = (mode or "auto").lower()
    if selected == "student":
        return await task_hume_expression_predict_student(text=text, urls=media_urls, files=files, modality=modality)
    if selected == "teacher" or (selected == "auto" and _has_api_key()):
        teacher = await task_hume_expression_analyze_teacher(
            text=text,
            urls=media_urls,
            files=files,
            fileBase64=fileBase64,
            modality=modality,
            waitForResult=True,
            timeoutMs=timeoutMs,
            pollIntervalMs=pollIntervalMs,
        )
        if not teacher.get("error") and not teacher.get("pending"):
            return teacher
        if selected == "teacher":
            return teacher
        student = await task_hume_expression_predict_student(text=text, urls=media_urls, files=files, modality=modality)
        return {"mode": "auto", "fallbackReason": teacher.get("error") or "teacher_pending", **student}
    return await task_hume_expression_predict_student(text=text, urls=media_urls, files=files, modality=modality)


async def task_hume_tts_synthesize(
    text: str = "",
    description: str = "Natural, clear, emotionally appropriate delivery.",
    voice: dict[str, Any] | None = None,
    format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not text:
        return {"error": "text is required"}
    payload: dict[str, Any] = {
        "utterances": [{"text": text, "description": description, "voice": voice}],
        "format": format or {"type": "mp3"},
        "num_generations": 1,
        "split_utterances": True,
        "strip_headers": False,
    }
    try:
        data = await asyncio.to_thread(_http_json, "POST", "/v0/tts", payload, 120)
        return {"mode": "hume-tts", "response": data}
    except Exception as e:  # noqa: BLE001
        return {"mode": "hume-tts", "error": str(e)}


def register(worker: Any, timeout_ms: int = 180_000) -> None:
    worker.task(task_type="hume.expression.predictStudent", single_value=False, timeout_ms=30_000)(
        task_hume_expression_predict_student
    )
    worker.task(task_type="hume.expression.analyzeTeacher", single_value=False, timeout_ms=timeout_ms)(
        task_hume_expression_analyze_teacher
    )
    worker.task(task_type="hume.expression.analyze", single_value=False, timeout_ms=timeout_ms)(
        task_hume_expression_analyze
    )
    worker.task(task_type="hume.expression.analyzeMultimodal", single_value=False, timeout_ms=timeout_ms)(
        task_hume_expression_analyze
    )
    worker.task(task_type="hume.expression.analyzeUploaded", single_value=False, timeout_ms=timeout_ms)(
        task_hume_expression_analyze
    )
    worker.task(task_type="hume.tts.synthesize", single_value=False, timeout_ms=timeout_ms)(
        task_hume_tts_synthesize
    )
