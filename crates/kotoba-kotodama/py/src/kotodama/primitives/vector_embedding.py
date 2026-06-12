"""Vector embedding backfill primitives for actor profiles and posts.

Phase 1 writes only `etzhayyim-mm-768` rows into:

- vertex_vector_embedding_source
- vertex_vector_embedding_768

The model runtime is lazy-loaded. Production uses SentenceTransformer, while
tests and local dry-runs can set VECTOR_EMBEDDING_FAKE=1 for deterministic
hash vectors without importing torch/transformers.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


SPACE_ID = "etzhayyim-mm-768"
DIM = 768
DEFAULT_TEXT_MODEL_ID = "bge-m3"
DEFAULT_TEXT_MODEL_NAME = "BAAI/bge-m3"
DEFAULT_TEXT_PROJECTION_ID = "bge-m3-to-etzhayyim-mm-768"
HUME_EMOTION_MODEL_ID = "hume-emotional-language"
HUME_API_BASE = "https://api.hume.ai/v0"


@dataclass(frozen=True)
class EmbeddingCandidate:
    source_uri: str
    source_kind: str
    source_vertex_id: str
    modality: str
    tenant_id: str
    shard_id: int | None
    text: str
    text_preview: str
    repo: str | None = None
    rkey: str | None = None
    source_cid: str | None = None
    lang: str | None = None
    created_at: str | None = None


_MODEL: Any = None


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any, *, limit: int = 4096) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _actor_text(row: dict[str, Any]) -> str:
    return _clean_text(
        "\n".join(
            str(part or "")
            for part in (
                row.get("display_name"),
                row.get("handle"),
                row.get("description"),
                row.get("root_did"),
                row.get("facade_did"),
                row.get("kind"),
            )
        )
    )


def _post_text(row: dict[str, Any]) -> str:
    return _clean_text(
        "\n".join(
            str(part or "")
            for part in (
                row.get("text"),
                row.get("embed_alt_text"),
                row.get("handle"),
                row.get("source_uri"),
            )
        )
    )


def _row_dicts(cur: Any) -> list[dict[str, Any]]:
    names = [d[0] for d in []] if [] else []
    return [dict(zip(names, row)) for row in (_res or [])]


def normalize_768(vector: list[float]) -> list[float]:
    if len(vector) > DIM:
        vector = vector[:DIM]
    elif len(vector) < DIM:
        vector = [*vector, *([0.0] * (DIM - len(vector)))]
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    if norm <= 0:
        raise ValueError("embedding vector norm is zero")
    return [float(v) / norm for v in vector]


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8g}" for v in normalize_768(vector)) + "]"


def _fake_embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < DIM:
            block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
            for b in block:
                values.append((b / 127.5) - 1.0)
                if len(values) == DIM:
                    break
            counter += 1
        vectors.append(normalize_768(values))
    return vectors


def _load_sentence_transformer() -> Any:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    model_name = os.environ.get("VECTOR_EMBEDDING_TEXT_MODEL", DEFAULT_TEXT_MODEL_NAME)
    from sentence_transformers import SentenceTransformer  # type: ignore

    _MODEL = SentenceTransformer(model_name)
    return _MODEL


def embed_texts_768(texts: list[str]) -> list[list[float]]:
    if os.environ.get("VECTOR_EMBEDDING_FAKE", "").lower() in ("1", "true", "on", "yes"):
        return _fake_embed(texts)
    model = _load_sentence_transformer()
    raw = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=max(1, min(int(os.environ.get("VECTOR_EMBEDDING_MODEL_BATCH", "16")), 128)),
    )
    return [normalize_768([float(v) for v in vec]) for vec in raw]


def plan_actor_candidates(limit: int = 100, shard_id: int | None = None) -> list[EmbeddingCandidate]:
    batch = max(1, min(int(limit or 100), 1000))
    sql = f"""
        SELECT
          root_did, did AS facade_did, handle, display_name, description, performer_type
        FROM view_actor_unified v
        WHERE root_did LIKE 'did:erc725:etzhayyim:260425:%%'
          AND NOT EXISTS (
            SELECT 1 FROM vertex_vector_embedding_768 e
            WHERE e.source_uri = ('actor:' || v.root_did)
              AND e.space_id = %s
              AND e.model_id = %s
          )
        ORDER BY root_did ASC
        LIMIT {batch}
    """
    params: list[Any] = [SPACE_ID, DEFAULT_TEXT_MODEL_ID]
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _row_dicts(cur)
    out: list[EmbeddingCandidate] = []
    for row in rows:
        root_did = str(row.get("root_did") or "")
        facade_did = str(row.get("facade_did") or "")
        text = _actor_text(row)
        if not root_did or not text:
            continue
        out.append(
            EmbeddingCandidate(
                source_uri=f"actor:{root_did}",
                source_kind="actor_profile",
                source_vertex_id=root_did,
                modality="text",
                tenant_id="public",
                shard_id=shard_id,
                text=text,
                text_preview=text[:500],
                repo=facade_did or root_did,
                created_at="",
            )
        )
    return out


def plan_post_candidates(limit: int = 100, shard_id: int | None = None) -> list[EmbeddingCandidate]:
    batch = max(1, min(int(limit or 100), 1000))
    sql = f"""
        SELECT
          vertex_id, source_uri, source_cid, repo, rkey, handle, text,
          embed_alt_text, lang, created_at, indexed_at
        FROM vertex_bluesky_post p
        WHERE source_uri IS NOT NULL
          AND text IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM vertex_vector_embedding_768 e
            WHERE e.source_uri = p.source_uri
              AND e.space_id = %s
              AND e.model_id = %s
          )
        ORDER BY indexed_at DESC
        LIMIT {batch}
    """
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (SPACE_ID, DEFAULT_TEXT_MODEL_ID))
        rows = _row_dicts(cur)
    out: list[EmbeddingCandidate] = []
    for row in rows:
        source_uri = str(row.get("source_uri") or "")
        text = _post_text(row)
        if not source_uri or not text:
            continue
        out.append(
            EmbeddingCandidate(
                source_uri=source_uri,
                source_kind="bluesky_post",
                source_vertex_id=str(row.get("vertex_id") or source_uri),
                modality="text",
                tenant_id="public",
                shard_id=shard_id,
                text=text,
                text_preview=text[:500],
                repo=str(row.get("repo") or ""),
                rkey=str(row.get("rkey") or ""),
                source_cid=str(row.get("source_cid") or ""),
                lang=str(row.get("lang") or ""),
                created_at=str(row.get("created_at") or row.get("indexed_at") or ""),
            )
        )
    return out


def plan_emotion_candidates(limit: int = 100, shard_id: int | None = None) -> list[EmbeddingCandidate]:
    batch = max(1, min(int(limit or 100), 1000))
    shard_filter = "AND s.shard_id = %s" if shard_id is not None else ""
    sql = f"""
        SELECT
          s.source_uri, s.source_kind, s.source_vertex_id, s.tenant_id,
          s.shard_id, s.modality, s.text_preview, s.repo, s.rkey,
          s.source_cid, s.lang, s.captured_at
        FROM vertex_vector_embedding_source s
        WHERE s.modality = 'text'
          AND s.text_preview IS NOT NULL
          {shard_filter}
          AND NOT EXISTS (
            SELECT 1 FROM vertex_vector_emotion_signal h
            WHERE h.source_uri = s.source_uri
              AND h.model_id = %s
          )
        ORDER BY s.indexed_at DESC
        LIMIT {batch}
    """
    params: list[Any] = [shard_id, HUME_EMOTION_MODEL_ID] if shard_id is not None else [HUME_EMOTION_MODEL_ID]
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _row_dicts(cur)
    out: list[EmbeddingCandidate] = []
    for row in rows:
        source_uri = str(row.get("source_uri") or "")
        text = _clean_text(row.get("text_preview"))
        if not source_uri or not text:
            continue
        out.append(
            EmbeddingCandidate(
                source_uri=source_uri,
                source_kind=str(row.get("source_kind") or "embedding_source"),
                source_vertex_id=str(row.get("source_vertex_id") or source_uri),
                modality=str(row.get("modality") or "text"),
                tenant_id=str(row.get("tenant_id") or "public"),
                shard_id=int(row["shard_id"]) if row.get("shard_id") is not None else None,
                text=text,
                text_preview=text[:500],
                repo=str(row.get("repo") or ""),
                rkey=str(row.get("rkey") or ""),
                source_cid=str(row.get("source_cid") or ""),
                lang=str(row.get("lang") or ""),
                created_at=str(row.get("captured_at") or ""),
            )
        )
    return out


def _source_row(candidate: EmbeddingCandidate, *, now: str) -> dict[str, Any]:
    return {
        "vertex_id": f"embedding-source:{candidate.source_uri}",
        "source_uri": candidate.source_uri,
        "source_cid": candidate.source_cid or None,
        "source_kind": candidate.source_kind,
        "source_table": "view_actor_universal"
        if candidate.source_kind == "actor_profile"
        else "vertex_bluesky_post",
        "source_vertex_id": candidate.source_vertex_id,
        "source_collection": None,
        "repo": candidate.repo or None,
        "rkey": candidate.rkey or None,
        "tenant_id": candidate.tenant_id,
        "shard_id": candidate.shard_id,
        "modality": candidate.modality,
        "media_type": "text/plain",
        "lang": candidate.lang or None,
        "text_preview": candidate.text_preview,
        "content_hash": hashlib.sha256(candidate.text.encode("utf-8")).hexdigest(),
        "blob_ref": None,
        "width_px": None,
        "height_px": None,
        "duration_ms": None,
        "sample_rate_hz": None,
        "frame_rate_millis": None,
        "sensor_vendor": None,
        "sensor_model": None,
        "sensor_frame": None,
        "captured_at": candidate.created_at or None,
        "indexed_at": now,
        "visibility": "public",
        "safety_label": None,
        "metadata_json": None,
        "created_at": now,
    }


def _embedding_row(candidate: EmbeddingCandidate, vector: list[float], *, now: str) -> dict[str, Any]:
    embedding_id = ":".join(
        [
            "emb768",
            SPACE_ID,
            DEFAULT_TEXT_MODEL_ID,
            DEFAULT_TEXT_PROJECTION_ID,
            candidate.source_uri,
            "root",
            "initial",
        ]
    )
    return {
        "embedding_id": embedding_id,
        "source_uri": candidate.source_uri,
        "chunk_id": None,
        "source_vertex_id": candidate.source_vertex_id,
        "tenant_id": candidate.tenant_id,
        "shard_id": candidate.shard_id,
        "modality": candidate.modality,
        "model_id": DEFAULT_TEXT_MODEL_ID,
        "space_id": SPACE_ID,
        "model_version": os.environ.get("VECTOR_EMBEDDING_TEXT_MODEL", DEFAULT_TEXT_MODEL_NAME),
        "projection_id": DEFAULT_TEXT_PROJECTION_ID,
        "emb": vector_literal(vector),
        "text_preview": candidate.text_preview,
        "created_at": candidate.created_at or now,
        "embedded_at": now,
    }


def write_embedding_rows(candidates: list[EmbeddingCandidate], vectors: list[list[float]]) -> int:
    if len(candidates) != len(vectors):
        raise ValueError("candidate/vector count mismatch")
    now = _utc_now_iso()
    written = 0
    if True:
        client = get_kotoba_client()
        for candidate, vector in zip(candidates, vectors):
            source = _source_row(candidate, now=now)
            _res = client.q(
                """
                INSERT INTO vertex_vector_embedding_source (
                  vertex_id, source_uri, source_cid, source_kind, source_table,
                  source_vertex_id, source_collection, repo, rkey, tenant_id,
                  shard_id, modality, media_type, lang, text_preview, content_hash,
                  blob_ref, width_px, height_px, duration_ms, sample_rate_hz,
                  frame_rate_millis, sensor_vendor, sensor_model, sensor_frame,
                  captured_at, indexed_at, visibility, safety_label, metadata_json,
                  created_at
                )
                SELECT
                  %(vertex_id)s, %(source_uri)s, %(source_cid)s, %(source_kind)s,
                  %(source_table)s, %(source_vertex_id)s, %(source_collection)s,
                  %(repo)s, %(rkey)s, %(tenant_id)s, %(shard_id)s::int, %(modality)s,
                  %(media_type)s, %(lang)s, %(text_preview)s, %(content_hash)s,
                  %(blob_ref)s, %(width_px)s::int, %(height_px)s::int,
                  %(duration_ms)s::bigint, %(sample_rate_hz)s::int,
                  %(frame_rate_millis)s::int, %(sensor_vendor)s,
                  %(sensor_model)s, %(sensor_frame)s, %(captured_at)s,
                  %(indexed_at)s, %(visibility)s, %(safety_label)s,
                  %(metadata_json)s, %(created_at)s
                WHERE NOT EXISTS (
                  SELECT 1 FROM vertex_vector_embedding_source
                  WHERE vertex_id = %(vertex_id)s
                )
                """,
                source,
            )
            emb = _embedding_row(candidate, vector, now=now)
            _res = client.q(
                """
                INSERT INTO vertex_vector_embedding_768 (
                  embedding_id, source_uri, chunk_id, source_vertex_id, tenant_id,
                  shard_id, modality, model_id, space_id, model_version,
                  projection_id, emb, text_preview, created_at, embedded_at
                )
                SELECT
                  %(embedding_id)s, %(source_uri)s, %(chunk_id)s,
                  %(source_vertex_id)s, %(tenant_id)s, %(shard_id)s::int,
                  %(modality)s, %(model_id)s, %(space_id)s, %(model_version)s,
                  %(projection_id)s, %(emb)s::vector(768), %(text_preview)s,
                  %(created_at)s, %(embedded_at)s
                WHERE NOT EXISTS (
                  SELECT 1 FROM vertex_vector_embedding_768
                  WHERE embedding_id = %(embedding_id)s
                )
                """,
                emb,
            )
            written += max(0, (len(_res) if isinstance(_res, list) else 1))
    return written


def _hume_enabled() -> bool:
    return os.environ.get("VECTOR_EMBEDDING_HUME", "").lower() in ("1", "true", "on", "yes")


def _hume_fake_enabled() -> bool:
    return os.environ.get("VECTOR_EMBEDDING_HUME_FAKE", "").lower() in ("1", "true", "on", "yes")


def _hume_request(method: str, path: str, *, body: dict[str, Any] | None = None) -> Any:
    api_key = os.environ.get("HUME_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("HUME_API_KEY is not set")
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{HUME_API_BASE}{path}",
        data=payload,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Hume-Api-Key": api_key,
        },
    )
    timeout = float(os.environ.get("HUME_API_TIMEOUT_SECONDS", "30"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hume API {method} {path} failed: {exc.code} {detail}") from exc


def _collect_emotion_scores(value: Any, out: dict[str, list[float]]) -> None:
    if isinstance(value, dict):
        emotions = value.get("emotions")
        if isinstance(emotions, list):
            for item in emotions:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                score = item.get("score")
                if name and isinstance(score, (int, float)):
                    out.setdefault(name, []).append(float(score))
        for child in value.values():
            _collect_emotion_scores(child, out)
    elif isinstance(value, list):
        for child in value:
            _collect_emotion_scores(child, out)


def _summarize_hume_prediction(value: Any) -> dict[str, Any]:
    grouped: dict[str, list[float]] = {}
    _collect_emotion_scores(value, grouped)
    scores = {name: sum(values) / len(values) for name, values in grouped.items() if values}
    top = max(scores.items(), key=lambda item: item[1]) if scores else (None, None)
    return {
        "scores": scores,
        "topEmotion": top[0],
        "topScore": top[1],
        "raw": value,
    }


def analyze_hume_emotions(candidates: list[EmbeddingCandidate]) -> list[dict[str, Any]]:
    if not candidates:
        return []
    if _hume_fake_enabled():
        out: list[dict[str, Any]] = []
        for candidate in candidates:
            digest = hashlib.sha256(candidate.text.encode("utf-8")).digest()
            calm = digest[0] / 255
            interest = digest[1] / 255
            scores = {"Calmness": calm, "Interest": interest}
            top = max(scores.items(), key=lambda item: item[1])
            out.append({"scores": scores, "topEmotion": top[0], "topScore": top[1], "raw": {"fake": True}})
        return out

    payload = {
        "models": {
            "language": {
                "granularity": os.environ.get("HUME_LANGUAGE_GRANULARITY", "sentence"),
            }
        },
        "text": [candidate.text for candidate in candidates],
        "notify": False,
    }
    started = _hume_request("POST", "/batch/jobs", body=payload)
    job_id = str(started.get("job_id") or "")
    if not job_id:
        raise RuntimeError(f"Hume API did not return job_id: {started}")

    deadline = time.monotonic() + float(os.environ.get("HUME_JOB_TIMEOUT_SECONDS", "120"))
    while True:
        details = _hume_request("GET", f"/batch/jobs/{job_id}")
        status = str(((details.get("state") or {}).get("status") or "")).upper()
        if status == "COMPLETED":
            break
        if status == "FAILED":
            raise RuntimeError(f"Hume job failed: {details}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Hume job timed out: {job_id}")
        time.sleep(float(os.environ.get("HUME_JOB_POLL_SECONDS", "2")))

    predictions = _hume_request("GET", f"/batch/jobs/{job_id}/predictions")
    items = predictions if isinstance(predictions, list) else [predictions]
    summaries = [_summarize_hume_prediction(item) for item in items[: len(candidates)]]
    while len(summaries) < len(candidates):
        summaries.append({"scores": {}, "topEmotion": None, "topScore": None, "raw": None})
    return summaries


def write_hume_emotion_rows(candidates: list[EmbeddingCandidate], emotions: list[dict[str, Any]]) -> int:
    if len(candidates) != len(emotions):
        raise ValueError("candidate/emotion count mismatch")
    now = _utc_now_iso()
    written = 0
    if True:
        client = get_kotoba_client()
        for candidate, emotion in zip(candidates, emotions):
            signal_id = ":".join(
                ["emotion", HUME_EMOTION_MODEL_ID, candidate.source_uri, "root", "initial"]
            )
            scores = emotion.get("scores") if isinstance(emotion.get("scores"), dict) else {}
            raw = emotion.get("raw")
            row = {
                "signal_id": signal_id,
                "source_uri": candidate.source_uri,
                "source_vertex_id": candidate.source_vertex_id,
                "tenant_id": candidate.tenant_id,
                "shard_id": candidate.shard_id,
                "modality": candidate.modality,
                "provider": "Hume AI",
                "model_id": HUME_EMOTION_MODEL_ID,
                "model_version": os.environ.get("HUME_EMOTION_MODEL_VERSION", "initial"),
                "granularity": os.environ.get("HUME_LANGUAGE_GRANULARITY", "sentence"),
                "language": candidate.lang or None,
                "top_emotion": emotion.get("topEmotion"),
                "top_score": emotion.get("topScore"),
                "scores_json": json.dumps(scores, ensure_ascii=False, sort_keys=True),
                "raw_json": json.dumps(raw, ensure_ascii=False) if raw is not None else None,
                "analyzed_at": now,
                "created_at": now,
            }
            _res = client.q(
                """
                INSERT INTO vertex_vector_emotion_signal (
                  signal_id, source_uri, source_vertex_id, tenant_id, shard_id,
                  modality, provider, model_id, model_version, granularity,
                  language, top_emotion, top_score, scores_json, raw_json,
                  analyzed_at, created_at
                )
                SELECT
                  %(signal_id)s, %(source_uri)s, %(source_vertex_id)s,
                  %(tenant_id)s, %(shard_id)s::int, %(modality)s, %(provider)s,
                  %(model_id)s, %(model_version)s, %(granularity)s, %(language)s,
                  %(top_emotion)s, %(top_score)s::double precision,
                  %(scores_json)s, %(raw_json)s, %(analyzed_at)s, %(created_at)s
                WHERE NOT EXISTS (
                  SELECT 1 FROM vertex_vector_emotion_signal
                  WHERE signal_id = %(signal_id)s
                )
                """,
                row,
            )
            written += max(0, (len(_res) if isinstance(_res, list) else 1))
    return written


def enrich_hume_emotions(candidates: list[EmbeddingCandidate], *, dry_run: bool = False) -> dict[str, Any]:
    if not candidates:
        return {"planned": 0, "written": 0, "enabled": _hume_enabled()}
    if not _hume_enabled() and not _hume_fake_enabled():
        return {"planned": len(candidates), "written": 0, "enabled": False}
    if dry_run:
        return {"planned": len(candidates), "written": 0, "enabled": True, "dryRun": True}
    if not _hume_fake_enabled() and not os.environ.get("HUME_API_KEY", "").strip():
        return {
            "planned": len(candidates),
            "written": 0,
            "enabled": True,
            "skipped": "HUME_API_KEY is not set",
        }
    emotions = analyze_hume_emotions(candidates)
    written = write_hume_emotion_rows(candidates, emotions)
    return {"planned": len(candidates), "written": written, "enabled": True}


def backfill_batch(
    surface: str,
    *,
    limit: int = 100,
    shard_id: int | None = None,
    dry_run: bool = False,
    emotion_only: bool = False,
) -> dict[str, Any]:
    surface_norm = (surface or "").strip().lower()
    if emotion_only:
        candidates = plan_emotion_candidates(limit=limit, shard_id=shard_id)
        emotion = enrich_hume_emotions(candidates, dry_run=dry_run)
        return {
            "surface": "emotion",
            "planned": len(candidates),
            "written": 0,
            "dryRun": bool(dry_run),
            "humeEmotion": emotion,
            "sample": [c.source_uri for c in candidates[:5]],
        }
    elif surface_norm in ("actor", "actors", "profile", "profiles"):
        candidates = plan_actor_candidates(limit=limit, shard_id=shard_id)
        canonical_surface = "actors"
    elif surface_norm in ("post", "posts", "feed"):
        candidates = plan_post_candidates(limit=limit, shard_id=shard_id)
        canonical_surface = "posts"
    else:
        return {"error": "surface must be actors or posts", "planned": 0, "written": 0}

    if dry_run or not candidates:
        return {
            "surface": canonical_surface,
            "planned": len(candidates),
            "written": 0,
            "dryRun": bool(dry_run),
            "humeEmotion": enrich_hume_emotions(candidates, dry_run=True),
            "sample": [c.source_uri for c in candidates[:5]],
        }

    vectors = embed_texts_768([c.text for c in candidates])
    written = write_embedding_rows(candidates, vectors)
    emotion = enrich_hume_emotions(candidates)
    return {
        "surface": canonical_surface,
        "planned": len(candidates),
        "written": written,
        "dryRun": False,
        "modelId": DEFAULT_TEXT_MODEL_ID,
        "spaceId": SPACE_ID,
        "humeEmotion": emotion,
    }


def task_vector_embedding_backfill_batch(
    surface: str = "posts",
    limit: int = 100,
    shardId: int | None = None,
    dryRun: bool = False,
    emotionOnly: bool = False,
) -> dict[str, Any]:
    return backfill_batch(
        surface,
        limit=limit,
        shard_id=shardId,
        dry_run=dryRun,
        emotion_only=emotionOnly,
    )


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="vectorEmbedding.backfillBatch",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_vector_embedding_backfill_batch)
