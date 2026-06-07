"""
ADR-0092 L2 — actor embedding UDF.

Runs multilingual-e5-small (sentence-transformers) in the mitama-udf-pool
Python UDF pod. CPU-only by default — RW pod + UDF pod both sit on the
Vultr VKE cluster (LAX), so model weights fit in the existing 1.5 GiB
container request.

SQL usage
---------

  INSERT INTO vertex_actor_embedding (vertex_id, did, kind, emb, model_id, embedded_at)
  SELECT
    v.vertex_id,
    v.did,
    v.kind,
    actor_embed(v.display_name, v.description, v.kind, 'passage') AS emb,
    'multilingual-e5-small' AS model_id,
    NOW()::varchar AS embedded_at
  FROM view_actor_universal v
  WHERE v.kind = 'action'
    AND NOT EXISTS (
      SELECT 1 FROM vertex_actor_embedding e WHERE e.vertex_id = v.vertex_id
    );

Query-side: pass ``mode='query'`` so E5's "query: " prefix is applied.

  SELECT did, handle, display_name
  FROM vertex_actor_embedding e
  JOIN view_actor_universal v ON v.vertex_id = e.vertex_id
  ORDER BY e.emb <=> actor_embed('etzhayyim semiconductor', NULL, NULL, 'query')
  LIMIT 10;

Model weights
-------------

The sentence-transformers package downloads ``intfloat/multilingual-e5-small``
on first call (~120 MB ONNX-less float32 state dict). Cache lives at
``/home/kotodama/.cache/huggingface`` inside the container. Subsequent
cold starts reuse the mounted cache when the pod has a PVC, or re-download
when ephemeral. The download is idempotent and completes in seconds on
LAX egress; no Hugging Face auth needed (public model).

CPU footprint
-------------

multilingual-e5-small has 117M params (~470 MB RAM at FP32). The UDF
arrow-flight protocol batches rows, so the model's forward pass
amortises across ``io_threads=100`` concurrent calls (GIL-safe because
tokenisation/inference release the GIL inside PyTorch).

Backfill throughput on ``vhp-4c-8gb`` CPU-only: ~30-50 rows/sec per pod.
With the HPA ceiling of 3 replicas this is ~100 rps = 195 M rows in
~22 days worst case. Scoped backfills (1 kind at a time) finish in
minutes for small kinds.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from kotodama import udf

log = logging.getLogger(__name__)

# Lazy-loaded — we want the UDF server to boot even if sentence-transformers
# takes several seconds to pull weights on first call. The lock prevents
# multiple io_threads from instantiating the model in parallel (each instance
# pins ~470 MB; N concurrent = N×470 MB → OOMKill on pods with 1.5-2 GiB
# limits, observed 2026-04-23 pilot).
_model: Any = None
_model_lock = threading.Lock()


def _load_model() -> Any:
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:  # double-check after acquiring the lock
            return _model
        # Imported lazily so the worker bootstraps even when this handler is
        # unused. Putting the import inside the lock also ensures torch only
        # imports its native libs once (torch global state is not re-entrant
        # during first import).
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        log.info("loading multilingual-e5-small (cpu)")
        model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
        log.info("multilingual-e5-small loaded; dim=%d", model.get_sentence_embedding_dimension())
        _model = model
        return _model


def _compose(display_name: str | None, description: str | None, kind: str | None, mode: str) -> str:
    # E5 family recommends a leading "passage: " for indexed documents and
    # "query: " for search queries. Missing prefix degrades accuracy ~2-4%.
    prefix = "query: " if mode == "query" else "passage: "
    parts = []
    if display_name:
        parts.append(display_name.strip())
    if description:
        parts.append(description.strip())
    if kind:
        parts.append(f"kind={kind.strip()}")
    body = " | ".join(p for p in parts if p) or "(empty)"
    # Cap at 2k chars — the tokeniser truncates at 512 anyway.
    return f"{prefix}{body[:2000]}"


@udf(
    nsid="com.etzhayyim.actor.embed",
    io_threads=100,
    input_types=["VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR"],
    result_type="REAL[]",
    capability_tags=("actor", "embedding", "vector", "l2", "cosine"),
    agent_tool=(
        "Compute a 384-d multilingual-e5-small embedding for an actor profile "
        "or a search query. Cast the result to vector(384) in SQL for indexed "
        "queries against vertex_actor_embedding."
    ),
)
def actor_embed(
    display_name: str | None,
    description: str | None,
    kind: str | None,
    mode: str | None,
) -> list[float]:
    """
    Return a 384-d multilingual-e5-small embedding as REAL[].

    Parameters
    ----------
    display_name : VARCHAR
    description  : VARCHAR
    kind         : VARCHAR — appended as "kind=<k>" for schema awareness
    mode         : VARCHAR — ``'passage'`` (default) for indexed docs, ``'query'``
                   for search queries. E5 accuracy drops without the correct
                   prefix.

    Returns
    -------
    REAL[] of length 384. Cast to ``vector(384)`` on the SQL side:

        emb::vector(384)

    """
    effective_mode = (mode or "passage").strip().lower()
    if effective_mode not in ("passage", "query"):
        effective_mode = "passage"
    text = _compose(display_name, description, kind, effective_mode)
    model = _load_model()
    # convert_to_numpy keeps it off GPU/python-list hot path.
    vec = model.encode(
        text,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,  # unit vectors → cosine == inner product
    )
    return vec.astype("float32").tolist()
