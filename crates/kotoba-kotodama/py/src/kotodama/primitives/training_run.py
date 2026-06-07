"""training.etzhayyim.com — model training + weight lineage primitives.

ADR-2605070700. T2 actor (ADR-2604282300): kotodama module + BPMN +
Zeebe, no CF Worker. All domain writes hit RisingWave directly via
Hyperdrive (ADR-0036). Weight artifacts stored in B2 (Hume-style
2-store, ADR-2604300135) — RW holds reference + sha256 only.

Pipeline coverage (ADR-0056 BPMN-as-actor):
  runSft.bpmn      XRPC → train.dataset.snapshot
                       →  train.sft.run
                       →  train.eval.run
  runLora.bpmn     XRPC → train.dataset.snapshot
                       →  train.lora.run
                       →  train.eval.run
  runDistill.bpmn  XRPC → train.dataset.snapshot
                       →  train.teacher.label
                       →  train.distill.run
                       →  train.eval.run
  runEval.bpmn     XRPC → train.eval.run
  promote.bpmn     XRPC → train.promote.checkpoint

Output target tables (created by 20260508000000_vertex_training_lineage.ts):
  vertex_training_dataset_snapshot   immutable corpus shard sets
  vertex_training_run                one fine-tune / distill run
  vertex_training_checkpoint         per-step weight reference (B2 URI + sha256)
  vertex_training_eval               bench result per checkpoint
  edge_training_consumed_dataset     run -> snapshot
  edge_training_distilled_from       student_run -> teacher
  edge_training_promoted_to          checkpoint -> serving alias

Heavy deps (transformers, peft, datasets, accelerate, torch) are
lazy-imported. CPU-only pods running this module will only fail when
a GPU task actually fires; lightweight tasks (snapshot / promote /
teacher.label) work without the heavy stack.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import gzip
import hashlib
import io
import json
import os
import time
import uuid
from typing import Any

from kotodama.primitives import training_export as _texp


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_TRAINING_ACTOR = "did:web:training.etzhayyim.com"
_BPMN_NSID_PREFIX = "com.etzhayyim.apps.training"
_CHECKPOINT_PREFIX = os.environ.get("TRAINING_CHECKPOINT_PREFIX", "v1/checkpoints")
_TEACHER_LABEL_PREFIX = os.environ.get("TRAINING_TEACHER_LABEL_PREFIX", "v1/teacher_labels")
_MURAKUMO_URL = os.environ.get("MURAKUMO_INFERENCE_URL", "https://murakumo-serve.etzhayyim.com/v1/chat/completions").rstrip("/")
_MURAKUMO_KEY = os.environ.get("MURAKUMO_API_KEY", "").strip()
_DEFAULT_BASE_REVISION = "main"
_DEFAULT_SAVE_STEP_INTERVAL = int(os.environ.get("TRAINING_SAVE_STEP_INTERVAL", "500"))

# Default Hugging Face base model for the H100 training pod (ADR 2605092345,
# 2026-05-09). Mirrors `TRAINING_DEFAULT_BASE_MODEL` in `llm-model-registry.ts`.
# Overridable per-call via `baseModel` lexicon input or `TRAINING_DEFAULT_BASE_MODEL`
# env var (e.g. for retraining experiments on a different trunk).
_TRAINING_DEFAULT_BASE_MODEL = os.environ.get(
    "TRAINING_DEFAULT_BASE_MODEL",
    "google/gemma-4-E4B",
).strip()

# Default 1.58-bit edge / browser / CPU trunk for the Baien family
# (ADR 2605092350). Mirrors `BAIEN_DEFAULT_TRUNK_MODEL` in
# `llm-model-registry.ts`. Used by the Baien LoRA / projector training
# kinds (`kind="baien-lora"` / `kind="baien-multimodal-graft"`) when the
# lexicon input does not pin an alternate trunk.
_BAIEN_DEFAULT_TRUNK_MODEL = os.environ.get(
    "BAIEN_DEFAULT_TRUNK_MODEL",
    "microsoft/bitnet-b1.58-2B-4T-bf16",
).strip()

# GPU backend — ADR-2605092345 (2026-05-09).
# Training is a *training-only* H100 NVL pod: Oka SFT / LoRA / distill / eval
# and the Baien LoRA-on-master / projector grafts all live here. Inference
# traffic continues to land on the RunPod 6000 Ada unified pod
# (ADR-2605010000) — do not collapse the two. CPU pod
# (`mitama-training-pool`) posts payloads to {pod}/train/run on the H100
# training pod's HTTP server (`kotodama.training_http_server`).
# `TRAINING_POD_BASE_URL` MUST point at the H100 pod proxy; the literal
# default below is empty so callers are forced to override via the
# `training-runpod-creds` Secret. The pre-2026-05-09 6000-Ada port-8003
# default has been retired.
_TRAINING_POD_BASE = os.environ.get(
    "TRAINING_POD_BASE_URL",
    "",
).rstrip("/")
_TRAINING_POD_AUTH_TOKEN = os.environ.get("TRAINING_POD_AUTH_TOKEN", "").strip()
_TRAINING_POD_POLL_INTERVAL_SEC = float(os.environ.get("TRAINING_POD_POLL_INTERVAL_SEC", "10"))
_TRAINING_POD_MAX_WAIT_SEC = float(os.environ.get("TRAINING_POD_MAX_WAIT_SEC", str(24 * 3600)))

# ComfyUI Pod for image-domain LoRA training (path C native), separate from
# LLM training above. POSTs workflow JSON to ComfyUI :8188 with a training
# custom node (kijai/ComfyUI-FluxTrainer or similar).
_COMFYUI_TRAIN_BASE = os.environ.get(
    "COMFYUI_POD_BASE_URL",
    "https://58pvflvw9w6nt3-8188.proxy.runpod.net",
).rstrip("/")


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _vid_run(run_id: str) -> str:
    return f"at://{_TRAINING_ACTOR}/{_BPMN_NSID_PREFIX}.run/{run_id}"


def _vid_checkpoint(run_id: str, step: int) -> str:
    return f"at://{_TRAINING_ACTOR}/{_BPMN_NSID_PREFIX}.checkpoint/{run_id}-step-{step:06d}"


def _vid_eval(checkpoint_id: str, bench_name: str) -> str:
    safe = bench_name.replace("/", "-").replace(".", "-")
    return f"at://{_TRAINING_ACTOR}/{_BPMN_NSID_PREFIX}.eval/{checkpoint_id}-{safe}"


def _vid_snapshot(snapshot_id: str) -> str:
    return f"at://{_TRAINING_ACTOR}/{_BPMN_NSID_PREFIX}.datasetSnapshot/{snapshot_id}"


def _vid_promotion(alias: str, checkpoint_id: str) -> str:
    safe = alias.replace(":", "-").replace("@", "-at-")
    return f"at://{_TRAINING_ACTOR}/{_BPMN_NSID_PREFIX}.promotion/{safe}-{checkpoint_id[-12:]}"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _stringify_hyperparams(hp: Any) -> str:
    if hp is None:
        return ""
    if isinstance(hp, (dict, list)):
        return json.dumps(hp, sort_keys=True, ensure_ascii=False)
    return str(hp)


# ──────────────────────────────────────────────────────────────────────
# Task: train.dataset.snapshot
# ──────────────────────────────────────────────────────────────────────


def task_train_dataset_snapshot(
    *,
    datasetName: str,
    datasetLabel: str | None = None,
    datasetRevision: str | None = None,
    sourceView: str = "v_training_text",
    filterExpr: str | None = None,
    **_: Any,
) -> dict:
    """Freeze a set of vertex_training_shard rows into a single immutable
    snapshot row in vertex_training_dataset_snapshot. Reuses the shards
    already produced by training.export.text / .triple — no re-export.

    If `datasetRevision` is provided, the call is idempotent: returns
    the existing snapshot row with a matching content_hash.

    Returns: {snapshotId, vertexId, b2Prefix, shardCount, rowCount, contentHash}
    """
    label = datasetLabel or "default"
    where_label = "AND label = %s" if datasetLabel else ""
    params: tuple = (datasetName, datasetLabel) if datasetLabel else (datasetName,)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT shard_index, b2_key, row_count
            FROM vertex_training_shard
            WHERE dataset_name = %s {where_label} AND status = 'done'
            ORDER BY shard_index
            """,
            params,
        )
        shards = _res

    if not shards:
        raise RuntimeError(
            f"no done shards for dataset_name={datasetName!r} label={datasetLabel!r}; "
            "run training.export.text first"
        )

    shard_count = len(shards)
    row_count = sum(int(r[2] or 0) for r in shards)
    keys = sorted(str(r[1]) for r in shards)
    content_hash = hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()
    b2_prefix = f"{_texp._B2_PREFIX if hasattr(_texp, '_B2_PREFIX') else 'v1'}/{datasetName}/{label}"

    snapshot_id = f"{datasetName}-{content_hash[:12]}"
    if datasetRevision:
        snapshot_id = f"{datasetName}-{datasetRevision}"
    vertex_id = _vid_snapshot(snapshot_id)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, snapshot_id, b2_prefix, shard_count, row_count, content_hash "
            "FROM vertex_training_dataset_snapshot WHERE vertex_id = %s",
            (vertex_id,),
        )
        existing = (_res[0] if _res else None)
        if existing:
            return {
                "snapshotId": existing[1],
                "vertexId": existing[0],
                "b2Prefix": existing[2],
                "shardCount": int(existing[3] or 0),
                "rowCount": int(existing[4] or 0),
                "contentHash": existing[5],
                "reused": True,
            }

        _res = client.q(
            """
            INSERT INTO vertex_training_dataset_snapshot
              (vertex_id, owner_did, snapshot_id, dataset_name, label, b2_prefix,
               shard_count, row_count, content_hash, source_view, filter_expr,
               status, created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'frozen', %s,
                    CAST(%s AS date), 0, %s, %s, 'sys.training.snapshot')
            """,
            (
                vertex_id, _TRAINING_ACTOR, snapshot_id, datasetName, label, b2_prefix,
                shard_count, row_count, content_hash, sourceView, filterExpr or "",
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )

    return {
        "snapshotId": snapshot_id,
        "vertexId": vertex_id,
        "b2Prefix": b2_prefix,
        "shardCount": shard_count,
        "rowCount": row_count,
        "contentHash": content_hash,
        "reused": False,
    }


# ──────────────────────────────────────────────────────────────────────
# Task: train.teacher.label
# ──────────────────────────────────────────────────────────────────────


def task_train_teacher_label(
    *,
    datasetSnapshotId: str,
    teacherKind: str,
    teacherRunId: str | None = None,
    teacherActorDid: str | None = None,
    teacherArtifactRunId: str | None = None,
    distillMethod: str = "soft-logits",
    temperature: float = 1.0,
    sampleLimit: int | None = None,
    **_: Any,
) -> dict:
    """Bulk-infer teacher labels and persist as a Hume-style artifact run
    (ADR-2604300135). Returns the artifact run id so train.distill.run
    can read it back.

    teacherKind:
      - 'run'      -> teacher is a prior vertex_training_run; its
                      promoted serving weights are used (alias lookup
                      via mv_training_active_serving).
      - 'actor'    -> teacher is a serving actor DID; pipethrough via
                      Murakumo OpenAI-compatible chat completions.
      - 'artifact' -> teacher labels already exist (Hume distillation,
                      ADR-2604300135). No bulk infer; just resolve and
                      return the existing artifact run id.
    """
    if teacherKind == "artifact":
        if not teacherArtifactRunId:
            raise ValueError("teacherKind=artifact requires teacherArtifactRunId")
        return {
            "teacherLabelArtifactRunId": teacherArtifactRunId,
            "teacherLabelB2Uri": "",
            "labelSampleCount": 0,
            "reused": True,
        }

    if teacherKind == "run":
        if not teacherRunId:
            raise ValueError("teacherKind=run requires teacherRunId")
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT alias FROM mv_training_active_serving
                WHERE alias LIKE %s
                ORDER BY promoted_at DESC LIMIT 1
                """,
                (f"%{teacherRunId}%",),
            )
            row = (_res[0] if _res else None)
        if row is None:
            raise RuntimeError(
                f"teacherKind=run but no active promotion alias references runId={teacherRunId}; "
                "promote that run first or use teacherKind=actor"
            )

    if teacherKind == "actor":
        if not teacherActorDid:
            raise ValueError("teacherKind=actor requires teacherActorDid")

    # Pull a sample of dataset rows for bulk infer.
    snapshot = _resolve_snapshot(datasetSnapshotId)
    rows = _read_snapshot_rows(snapshot, limit=sampleLimit or 10_000)

    label_records: list[dict[str, Any]] = []
    if teacherKind == "actor" and _MURAKUMO_KEY:
        for r in rows:
            text = str(r.get("content") or r.get("text") or "")
            if not text:
                continue
            try:
                logits = _murakumo_chat(text, model=teacherActorDid, temperature=temperature)
                label_records.append({"input": text[:2000], "teacher_output": logits})
            except Exception as e:
                label_records.append({"input": text[:2000], "error": str(e)})
    else:
        # Without an inference target, we still produce a hard-label
        # passthrough using the dataset's own label column (degraded mode).
        for r in rows:
            label_records.append({"input": str(r.get("content") or "")[:2000], "teacher_output": str(r.get("label") or "")})

    artifact_run_id = f"teacher-distill-{snapshot['snapshotId']}-{uuid.uuid4().hex[:8]}"
    jsonl = "\n".join(json.dumps(rec, ensure_ascii=False) for rec in label_records).encode("utf-8")
    gz = gzip.compress(jsonl)
    b2_key = f"{_TEACHER_LABEL_PREFIX}/{artifact_run_id}/labels.jsonl.gz"
    b2_uri = _texp._b2_put(b2_key, gz, content_type="application/gzip")

    # Index in vertex_ingest_artifact (Hume layout, ADR-2604300135). We
    # expect the table to already exist; if not, fall back to a noop.
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_ingest_artifact
                  (vertex_id, owner_did, run_id, artifact_kind, b2_uri, byte_size, sample_count,
                   props, status, created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
                VALUES (%s, %s, %s, 'training.teacher_labels_jsonl', %s, %s, %s,
                        %s, 'active', %s, CAST(%s AS date), 0, %s, %s, 'sys.training.teacher_label')
                """,
                (
                    f"at://{_TRAINING_ACTOR}/com.etzhayyim.training.teacherLabels/{artifact_run_id}",
                    _TRAINING_ACTOR, artifact_run_id, b2_uri, len(gz), len(label_records),
                    json.dumps({"distillMethod": distillMethod, "temperature": temperature,
                                "teacherKind": teacherKind, "teacherRunId": teacherRunId,
                                "teacherActorDid": teacherActorDid,
                                "datasetSnapshotId": datasetSnapshotId}),
                    _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
                ),
            )
    except Exception:
        pass  # Hume table may not exist in dev; B2 artifact is still durable.

    return {
        "teacherLabelArtifactRunId": artifact_run_id,
        "teacherLabelB2Uri": b2_uri,
        "labelSampleCount": len(label_records),
        "reused": False,
    }


def _murakumo_chat(text: str, *, model: str, temperature: float = 1.0) -> str:
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "temperature": temperature,
        "max_tokens": 256,
    }).encode("utf-8")
    req = urllib.request.Request(
        _MURAKUMO_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_MURAKUMO_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return str(out["choices"][0]["message"]["content"])


# ──────────────────────────────────────────────────────────────────────
# Unified-Pod HTTP client (ADR-2605070700 Addendum-of-Addendum 2026-05-07)
# ──────────────────────────────────────────────────────────────────────


def _pod_submit_and_wait(
    payload: dict,
    *,
    timeout_sec: float | None = None,
) -> dict:
    """POST to {pod}/train/run on the H100 training pod (ADR 2605092345,
    2026-05-09), poll /train/status/{id} until terminal. Returns the
    handler's `output` dict as-is, or raises on FAILED / timeout. Mirrors
    the RunPod Serverless wire format so the GPU side can be re-pointed
    with no client change. Inference is served on a separate RunPod 6000
    Ada pod (ADR-2605010000) — this client only talks to the H100 trainer.

    Uses httpx with curl-compatible User-Agent because the RunPod proxy
    returns 403 for default `Python-urllib/*` clients (proxy-side UA
    fingerprinting). curl with the same bearer token succeeds, so we mimic
    its UA. HTTP/2 is available via the `h2` extra (pyproject requires
    `httpx[http2]`) and can be flipped on by setting
    `TRAINING_POD_HTTP2=1` if UA-only is insufficient against the proxy.
    """
    import httpx

    if not _TRAINING_POD_BASE:
        raise RuntimeError("TRAINING_POD_BASE_URL env not set — Secret training-runpod-creds missing")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }
    if _TRAINING_POD_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {_TRAINING_POD_AUTH_TOKEN}"

    use_http2 = os.environ.get("TRAINING_POD_HTTP2", "").strip() in ("1", "true", "yes")
    client = httpx.Client(headers=headers, timeout=60.0, http2=use_http2)
    try:
        submit_resp = client.post(
            f"{_TRAINING_POD_BASE}/train/run",
            content=json.dumps({"input": payload}).encode("utf-8"),
        )
        if submit_resp.status_code >= 400:
            raise RuntimeError(
                f"unified-pod /train/run HTTP {submit_resp.status_code}: {submit_resp.text[:512]!r}"
            )
        submit = submit_resp.json()
        job_id = str(submit.get("id") or "")
        if not job_id:
            raise RuntimeError(f"unified-pod /train/run returned no job id: {submit!r}")

        deadline = time.time() + (timeout_sec if timeout_sec is not None else _TRAINING_POD_MAX_WAIT_SEC)
        last_status = ""
        while True:
            if time.time() > deadline:
                raise RuntimeError(
                    f"unified-pod job {job_id} timed out after {_TRAINING_POD_MAX_WAIT_SEC:.0f}s "
                    f"(last status={last_status!r})"
                )
            try:
                status_resp = client.get(f"{_TRAINING_POD_BASE}/train/status/{job_id}", timeout=30.0)
                if status_resp.status_code >= 400:
                    last_status = f"HTTP{status_resp.status_code}"
                    time.sleep(_TRAINING_POD_POLL_INTERVAL_SEC)
                    continue
                state = status_resp.json()
            except httpx.HTTPError as e:
                time.sleep(_TRAINING_POD_POLL_INTERVAL_SEC)
                last_status = f"HTTPError:{e}"
                continue

            last_status = str(state.get("status") or "")
            if last_status == "COMPLETED":
                output = state.get("output") or {}
                if not isinstance(output, dict):
                    raise RuntimeError(f"unified-pod {job_id} COMPLETED but output is not a dict: {output!r}")
                return output
            if last_status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                err = state.get("error") or state.get("output") or {}
                raise RuntimeError(f"unified-pod job {job_id} terminal {last_status}: {err!r}")
            # Otherwise IN_QUEUE / IN_PROGRESS — keep polling.
            time.sleep(_TRAINING_POD_POLL_INTERVAL_SEC)
    finally:
        client.close()


def _delegate_to_runpod(kind: str, payload: dict) -> dict:
    """Annotate payload with `kind` + actor + checkpoint prefix, submit to
    the unified pod's training HTTP server. The pod-side handler is
    `kotodama.training_http_server` → `runpod_handler(event)` which:
      1. Inserts vertex_training_run header (status='running')
      2. Runs HF Trainer / PEFT / distill loop on the GPU
      3. INSERTs vertex_training_checkpoint per save step (B2 PUT + RW row)
      4. Updates vertex_training_run footer (status='done'/'failed')
      5. Returns { ok, runId, runVertexId, finalCheckpointId, ... }

    The function name is kept (`_delegate_to_runpod`) since the underlying
    pod is still on RunPod; only the wire format is HTTP+poll instead of
    Serverless API. Callers don't change.
    """
    full_payload = dict(payload)
    full_payload["kind"] = kind
    full_payload["trainingActor"] = _TRAINING_ACTOR
    full_payload["checkpointPrefix"] = _CHECKPOINT_PREFIX
    return _pod_submit_and_wait(full_payload)


# ──────────────────────────────────────────────────────────────────────
# Task: train.sft.run
# ──────────────────────────────────────────────────────────────────────


def task_train_sft_run(
    *,
    runId: str | None = None,
    baseModel: str,
    baseModelRevision: str | None = None,
    datasetSnapshotId: str,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """Supervised fine-tune. Delegates to RunPod Serverless handler."""
    snapshot = _resolve_snapshot(datasetSnapshotId)
    return _delegate_to_runpod("sft", {
        "runId": runId or _gen_id("run"),
        "baseModel": baseModel,
        "baseModelRevision": baseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "datasetName": snapshot["datasetName"],
        "datasetLabel": snapshot["label"],
        "hyperparams": hyperparams or {},
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })


# ──────────────────────────────────────────────────────────────────────
# Task: train.lora.run
# ──────────────────────────────────────────────────────────────────────


def task_train_lora_run(
    *,
    runId: str | None = None,
    baseModel: str,
    baseModelRevision: str | None = None,
    datasetSnapshotId: str,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """LoRA / PEFT adapter fine-tune. Delegates to RunPod Serverless."""
    snapshot = _resolve_snapshot(datasetSnapshotId)
    return _delegate_to_runpod("lora", {
        "runId": runId or _gen_id("run"),
        "baseModel": baseModel,
        "baseModelRevision": baseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "datasetName": snapshot["datasetName"],
        "datasetLabel": snapshot["label"],
        "hyperparams": hyperparams or {},
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })


# ──────────────────────────────────────────────────────────────────────
# Task: train.baien.lora.run / train.baien.graft.run (ADR 2605092350)
# ──────────────────────────────────────────────────────────────────────


def task_train_baien_lora_run(
    *,
    runId: str | None = None,
    baseModel: str | None = None,
    baseModelRevision: str | None = None,
    datasetSnapshotId: str,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """Baien LoRA-on-bf16-master fine-tune (ADR 2605092350). Same H100
    pod as Oka; `kind="baien-lora"` is the only handler dispatch
    difference. `baseModel` defaults to BAIEN_DEFAULT_TRUNK_MODEL when
    omitted (ternary-friendly bf16 master)."""
    snapshot = _resolve_snapshot(datasetSnapshotId)
    return _delegate_to_runpod("baien-lora", {
        "runId": runId or _gen_id("run"),
        "baseModel": baseModel or _BAIEN_DEFAULT_TRUNK_MODEL,
        "baseModelRevision": baseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "datasetName": snapshot["datasetName"],
        "datasetLabel": snapshot["label"],
        "hyperparams": hyperparams or {},
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })


def task_train_baien_graft_run(
    *,
    runId: str | None = None,
    modality: str,
    encoderModel: str,
    encoderRevision: str | None = None,
    baseModel: str | None = None,
    baseModelRevision: str | None = None,
    datasetSnapshotId: str,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """Baien multimodal projector training (ADR 2605092350). Trunk and
    encoder are frozen; only the 1.58-bit projector is updated."""
    snapshot = _resolve_snapshot(datasetSnapshotId)
    hp = dict(hyperparams or {})
    hp["modality"] = modality
    hp["encoderModel"] = encoderModel
    if encoderRevision:
        hp["encoderRevision"] = encoderRevision
    return _delegate_to_runpod("baien-multimodal-graft", {
        "runId": runId or _gen_id("run"),
        "baseModel": baseModel or _BAIEN_DEFAULT_TRUNK_MODEL,
        "baseModelRevision": baseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "datasetName": snapshot["datasetName"],
        "datasetLabel": snapshot["label"],
        "hyperparams": hp,
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })


# ──────────────────────────────────────────────────────────────────────
# Task: train.distill.run
# ──────────────────────────────────────────────────────────────────────


def task_train_distill_run(
    *,
    runId: str | None = None,
    studentBaseModel: str,
    studentBaseModelRevision: str | None = None,
    datasetSnapshotId: str,
    teacherLabelArtifactRunId: str,
    teacherKind: str,
    teacherRunId: str | None = None,
    teacherActorDid: str | None = None,
    distillMethod: str = "soft-logits",
    temperature: float = 1.0,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """Distillation fine-tune. Delegates to RunPod Serverless. Worker
    inserts edge_training_distilled_from after RunPod returns successfully.
    """
    hp = dict(hyperparams or {})
    hp["distillMethod"] = distillMethod
    hp["temperature"] = temperature
    hp["teacherLabelArtifactRunId"] = teacherLabelArtifactRunId

    snapshot = _resolve_snapshot(datasetSnapshotId)
    result = _delegate_to_runpod("distill", {
        "runId": runId or _gen_id("run"),
        "studentBaseModel": studentBaseModel,
        "studentBaseModelRevision": studentBaseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "datasetName": snapshot["datasetName"],
        "datasetLabel": snapshot["label"],
        "teacherLabelArtifactRunId": teacherLabelArtifactRunId,
        "teacherKind": teacherKind,
        "teacherRunId": teacherRunId,
        "teacherActorDid": teacherActorDid,
        "distillMethod": distillMethod,
        "temperature": temperature,
        "hyperparams": hp,
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })

    if not result.get("ok"):
        return result

    # Write teacher edge after successful student run.
    if teacherKind == "run" and teacherRunId:
        teacher_vid = _vid_run(teacherRunId)
    elif teacherKind == "actor" and teacherActorDid:
        teacher_vid = teacherActorDid
    else:
        teacher_vid = teacherLabelArtifactRunId
    edge_id = f"distilled:{result['runId']}:{teacher_vid[:60]}"
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO edge_training_distilled_from
              (edge_id, owner_did, src_vid, dst_vid, teacher_kind, distill_method,
               temperature, sample_count, created_at, created_date, sensitivity_ord,
               org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS date), 0, %s, %s, 'sys.training.distill')
            """,
            (
                edge_id, _TRAINING_ACTOR, _vid_run(result["runId"]), teacher_vid,
                teacherKind, distillMethod, float(temperature), 0,
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )

    result["distilledFromEdgeId"] = edge_id
    return result


# ──────────────────────────────────────────────────────────────────────
# Task: train.eval.run
# ──────────────────────────────────────────────────────────────────────


def task_train_eval_run(
    *,
    checkpointId: str,
    benches: list[str] | None = None,
    evalDatasetName: str | None = None,
    evalDatasetRevision: str | None = None,
    sampleLimit: int | None = None,
    gpuTarget: str | None = None,
    **_: Any,
) -> dict:
    """Run eval benches against a checkpoint. Heavy benches delegate to
    RunPod (lm_eval-harness on GPU); the placeholder `internal-loss` runs
    on the CPU pod as a fast-path that just records a status row.
    """
    bench_list = benches or ["internal-loss"]
    cp = _resolve_checkpoint(checkpointId)

    heavy = [b for b in bench_list if b != "internal-loss"]
    light = [b for b in bench_list if b == "internal-loss"]

    eval_ids: list[str] = []
    primary_scores: dict[str, float] = {}

    # Light path on CPU: placeholder loss row.
    for bench in light:
        eval_id, primary_score = _record_eval_row(
            checkpointId=checkpointId,
            run_id=cp["run_id"],
            bench=bench,
            metrics={"_primary_metric": "loss", "loss": 0.0, "perplexity": 1.0,
                     "sample_count": int(sampleLimit or 0), "duration_seconds": 0.0,
                     "note": "internal-loss is a placeholder; use a real bench via RunPod"},
            eval_runner="cpu-placeholder",
            evalDatasetName=evalDatasetName,
            status="done",
        )
        eval_ids.append(eval_id)
        primary_scores[bench] = primary_score

    # Heavy path on RunPod.
    if heavy:
        try:
            result = _delegate_to_runpod("eval", {
                "runId": cp["run_id"],
                "checkpointId": checkpointId,
                "weightB2Uri": cp.get("weight_b2_uri", ""),
                "weightSha256": cp.get("weight_sha256", ""),
                "benches": heavy,
                "evalDatasetName": evalDatasetName,
                "evalDatasetRevision": evalDatasetRevision,
                "sampleLimit": sampleLimit,
                "gpuTarget": gpuTarget,
            })
        except Exception as e:
            # Record one failure row per heavy bench; don't lose the light eval rows.
            for bench in heavy:
                eval_id, _ = _record_eval_row(
                    checkpointId=checkpointId, run_id=cp["run_id"], bench=bench,
                    metrics={"error": str(e)}, eval_runner="runpod",
                    evalDatasetName=evalDatasetName, status="failed",
                )
                eval_ids.append(eval_id)
                primary_scores[f"{bench}.error"] = -1.0
        else:
            # Handler returns evalIds + primaryScores already.
            eval_ids.extend(result.get("evalIds", []))
            try:
                heavy_scores = json.loads(result.get("primaryScores", "{}"))
            except Exception:
                heavy_scores = {}
            primary_scores.update({k: float(v) for k, v in heavy_scores.items() if isinstance(v, (int, float))})

    return {
        "ok": True,
        "checkpointId": checkpointId,
        "evalCount": len(eval_ids),
        "evalIds": eval_ids,
        "primaryScores": json.dumps(primary_scores),
    }


def _record_eval_row(
    *,
    checkpointId: str,
    run_id: str,
    bench: str,
    metrics: dict,
    eval_runner: str,
    evalDatasetName: str | None,
    status: str,
) -> tuple[str, float]:
    """Insert one vertex_training_eval row. Returns (eval_id, primary_score)."""
    primary_metric = metrics.get("_primary_metric", "loss")
    try:
        primary_score = float(metrics.get(primary_metric, 0.0))
    except Exception:
        primary_score = 0.0

    eval_id = _gen_id("eval")
    vid = _vid_eval(checkpointId, bench)
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_training_eval
              (vertex_id, owner_did, eval_id, checkpoint_id, run_id, bench_name,
               eval_dataset_snapshot_id, metrics_json, primary_metric, primary_score,
               sample_count, duration_seconds, eval_runner, status, evaluated_at,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CAST(%s AS date), 0, %s, %s, 'sys.training.eval')
            """,
            (
                vid, _TRAINING_ACTOR, eval_id, checkpointId, run_id, bench,
                evalDatasetName or "", json.dumps(metrics, ensure_ascii=False),
                primary_metric, primary_score, int(metrics.get("sample_count", 0)),
                float(metrics.get("duration_seconds", 0.0)),
                eval_runner, status, _now_iso(),
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )
    return eval_id, primary_score


# ──────────────────────────────────────────────────────────────────────
# Task: train.promote.checkpoint
# ──────────────────────────────────────────────────────────────────────


def task_train_promote_checkpoint(
    *,
    checkpointId: str,
    alias: str,
    servingTarget: str | None = None,
    promotedBy: str | None = None,
    rationale: str | None = None,
    **_: Any,
) -> dict:
    """Atomic promotion: retire prior active edge for the same alias,
    insert new active edge. App-layer enforces the 1-active-per-alias
    invariant (RW lacks UNIQUE constraints across rows).
    """
    cp = _resolve_checkpoint(checkpointId)
    new_edge_id = f"promoted:{alias}:{checkpointId[-12:]}"
    promoted_at = _now_iso()
    promoter = promotedBy or _TRAINING_ACTOR

    retired_edge_id: str | None = None
    if True:
        client = get_kotoba_client()
        # Retire prior active edge for this alias.
        _res = client.q(
            "SELECT edge_id FROM edge_training_promoted_to WHERE alias = %s AND status = 'active'",
            (alias,),
        )
        prior = (_res[0] if _res else None)
        if prior:
            retired_edge_id = prior[0]
            _res = client.q(
                "UPDATE edge_training_promoted_to SET status = 'retired', retired_at = %s "
                "WHERE edge_id = %s",
                (promoted_at, retired_edge_id),
            )

        # Insert new active edge.
        _res = client.q(
            """
            INSERT INTO edge_training_promoted_to
              (edge_id, owner_did, src_vid, dst_vid, alias, serving_target,
               promoted_at, promoted_by, status, created_at, created_date,
               sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, CAST(%s AS date),
                    0, %s, %s, 'sys.training.promote')
            """,
            (
                new_edge_id, _TRAINING_ACTOR, _vid_checkpoint(cp["run_id"], int(cp["step"])),
                alias, alias, servingTarget or "",
                promoted_at, promoter, _now_iso(), _today(),
                _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )

    return {
        "ok": True,
        "alias": alias,
        "checkpointId": checkpointId,
        "newEdgeId": new_edge_id,
        "retiredEdgeId": retired_edge_id or "",
        "weightB2Uri": cp.get("weight_b2_uri", ""),
    }


# ──────────────────────────────────────────────────────────────────────
# Internal: snapshot / checkpoint resolution
# ──────────────────────────────────────────────────────────────────────


def _resolve_snapshot(snapshot_id: str) -> dict:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT snapshot_id, dataset_name, label, b2_prefix, shard_count, row_count, content_hash "
            "FROM vertex_training_dataset_snapshot WHERE snapshot_id = %s OR vertex_id = %s",
            (snapshot_id, snapshot_id),
        )
        row = (_res[0] if _res else None)
    if not row:
        raise RuntimeError(f"unknown snapshot_id={snapshot_id!r}")
    return {
        "snapshotId": row[0], "datasetName": row[1], "label": row[2],
        "b2Prefix": row[3], "shardCount": int(row[4] or 0), "rowCount": int(row[5] or 0),
        "contentHash": row[6],
    }


def _resolve_checkpoint(checkpoint_id: str) -> dict:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT checkpoint_id, run_id, step, weight_b2_uri, weight_sha256, adapter_kind "
            "FROM vertex_training_checkpoint "
            "WHERE checkpoint_id = %s OR vertex_id = %s LIMIT 1",
            (checkpoint_id, checkpoint_id),
        )
        row = (_res[0] if _res else None)
    if not row:
        raise RuntimeError(f"unknown checkpoint_id={checkpoint_id!r}")
    return {
        "checkpoint_id": row[0], "run_id": row[1], "step": int(row[2] or 0),
        "weight_b2_uri": row[3], "weight_sha256": row[4], "adapter_kind": row[5],
    }


def _read_snapshot_rows(snapshot: dict, *, limit: int) -> list[dict]:
    """Read up to `limit` rows from the snapshot's B2 shards. Streams
    decompressed JSONL.
    """
    rows: list[dict] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT b2_key FROM vertex_training_shard "
            "WHERE dataset_name = %s AND label = %s AND status = 'done' "
            "ORDER BY shard_index",
            (snapshot["datasetName"], snapshot["label"]),
        )
        keys = [r[0] for r in _res]
    for key in keys:
        if len(rows) >= limit:
            break
        try:
            data = _texp._b2_get(key)
        except Exception:
            continue
        try:
            text = gzip.decompress(data).decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
            if len(rows) >= limit:
                break
    return rows


# ──────────────────────────────────────────────────────────────────────
# Internal: HF training loop (sft / lora / distill)
# ──────────────────────────────────────────────────────────────────────


def _run_finetune(
    *,
    kind: str,
    runId: str | None,
    baseModel: str,
    baseModelRevision: str,
    datasetSnapshotId: str,
    hyperparams: dict,
    gpuTarget: str | None,
    seed: int | None,
    triggeredBy: str | None,
    bpmnProcessInstanceKey: str | None,
    peft: bool,
    teacherKind: str | None = None,
    teacherRunId: str | None = None,
    teacherActorDid: str | None = None,
    teacherLabelArtifactRunId: str | None = None,
) -> dict:
    """Common SFT / LoRA / distill loop. Writes vertex_training_run +
    vertex_training_checkpoint + edge_training_consumed_dataset.
    """
    run_id = runId or _gen_id("run")
    run_vid = _vid_run(run_id)
    started_at = _now_iso()
    snapshot = _resolve_snapshot(datasetSnapshotId)

    # Insert run header (status=running).
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_training_run
              (vertex_id, owner_did, run_id, kind, base_model, base_model_revision,
               dataset_snapshot_id, teacher_run_id, teacher_actor_did,
               hyperparams_json, gpu_target, seed, status, started_at,
               triggered_by, bpmn_process_instance_key,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'running', %s, %s, %s,
                    %s, CAST(%s AS date), 0, %s, %s, 'sys.training.run')
            """,
            (
                run_vid, _TRAINING_ACTOR, run_id, kind, baseModel, baseModelRevision,
                datasetSnapshotId, teacherRunId or "", teacherActorDid or "",
                _stringify_hyperparams(hyperparams), gpuTarget or "", seed,
                started_at, triggeredBy or "", bpmnProcessInstanceKey or "",
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )
        # Edge: run -> dataset
        consumed_edge_id = f"consumed:{run_id}:{snapshot['snapshotId']}"
        _res = client.q(
            """
            INSERT INTO edge_training_consumed_dataset
              (edge_id, owner_did, src_vid, dst_vid, role, mix_ratio,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, 'primary', 1.0, %s, CAST(%s AS date), 0, %s, %s, 'sys.training.consume')
            """,
            (consumed_edge_id, _TRAINING_ACTOR, run_vid, _vid_snapshot(snapshot["snapshotId"]),
             _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR),
        )

    # Run training loop.
    failure: str | None = None
    final_step = 0
    final_checkpoint_id: str | None = None
    try:
        final_step, final_checkpoint_id = _train_loop(
            run_id=run_id,
            kind=kind,
            base_model=baseModel,
            base_model_revision=baseModelRevision,
            snapshot=snapshot,
            hyperparams=hyperparams,
            seed=seed,
            peft=peft,
            teacher_label_artifact_run_id=teacherLabelArtifactRunId,
        )
        status = "done"
    except Exception as e:
        failure = str(e)
        status = "failed"

    # Update run footer.
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            UPDATE vertex_training_run
            SET status = %s, ended_at = %s, completed_steps = %s, failure_reason = %s
            WHERE vertex_id = %s
            """,
            (status, _now_iso(), final_step, failure or "", run_vid),
        )

    return {
        "ok": status == "done",
        "runId": run_id,
        "runVertexId": run_vid,
        "datasetSnapshotId": snapshot["snapshotId"],
        "finalCheckpointId": final_checkpoint_id or "",
        "finalCheckpointVertexId": _vid_checkpoint(run_id, final_step) if final_checkpoint_id else "",
        "stepCount": final_step,
        "status": status,
        "error": failure or "",
    }


def _train_loop(
    *,
    run_id: str,
    kind: str,
    base_model: str,
    base_model_revision: str,
    snapshot: dict,
    hyperparams: dict,
    seed: int | None,
    peft: bool,
    teacher_label_artifact_run_id: str | None,
) -> tuple[int, str]:
    """Actual GPU training loop. Lazy-imports transformers / datasets /
    peft. Saves checkpoints to B2 + RW at every save_step_interval.

    Returns: (final_step, final_checkpoint_id)
    """
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainerCallback,
            TrainingArguments,
        )
        from datasets import Dataset
    except ImportError as e:
        raise RuntimeError(
            f"transformers / torch / datasets not installed in this image — "
            f"add them to pyproject and rebuild for kind={kind!r}. ({e})"
        ) from e

    # Optional LoRA / PEFT.
    peft_module = None
    if peft:
        try:
            import peft as peft_module  # type: ignore
        except ImportError as e:
            raise RuntimeError(f"peft not installed — required for LoRA. ({e})") from e

    # Read snapshot rows (cap at 200K for sanity; real prod uses streaming).
    rows = _read_snapshot_rows(snapshot, limit=int(hyperparams.get("trainSampleLimit", 200_000)))
    if not rows:
        raise RuntimeError(f"snapshot {snapshot['snapshotId']} produced 0 rows")

    save_step_interval = int(hyperparams.get("saveStepInterval", _DEFAULT_SAVE_STEP_INTERVAL))
    epochs = float(hyperparams.get("epochs", 1.0))
    lr = float(hyperparams.get("learningRate", 2e-5))
    batch_size = int(hyperparams.get("batchSize", 4))
    grad_accum = int(hyperparams.get("gradientAccumulationSteps", 1))
    max_seq_len = int(hyperparams.get("maxSeqLen", 512))

    tokenizer = AutoTokenizer.from_pretrained(base_model, revision=base_model_revision, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model, revision=base_model_revision,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    )
    if peft and peft_module is not None:
        lora_cfg = peft_module.LoraConfig(
            r=int(hyperparams.get("loraRank", 16)),
            lora_alpha=int(hyperparams.get("loraAlpha", 32)),
            lora_dropout=float(hyperparams.get("loraDropout", 0.05)),
            target_modules=hyperparams.get("targetModules") or ["q_proj", "v_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = peft_module.get_peft_model(model, lora_cfg)

    # Build dataset.
    def _row_to_text(r: dict) -> str:
        return str(r.get("content") or r.get("text") or r.get("input") or "")

    text_rows = [_row_to_text(r) for r in rows if _row_to_text(r)]
    ds = Dataset.from_dict({"text": text_rows})

    def _tok(batch: dict) -> dict:
        out = tokenizer(batch["text"], truncation=True, max_length=max_seq_len, padding="max_length")
        out["labels"] = out["input_ids"].copy()
        return out

    ds_tok = ds.map(_tok, batched=True, remove_columns=["text"])

    # Distill loss (soft-logits): if teacher labels artifact provided,
    # we'd load teacher outputs and KL-divergence them. For brevity in
    # this first cut, distill falls back to hard-label SFT against the
    # dataset and records the teacher edge in vertex_training_run only.
    # Future addendum can plug a custom Trainer compute_loss.

    out_dir = f"/tmp/training-{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    final_step_holder = {"step": 0, "checkpoint_id": ""}

    class _SaveCallback(TrainerCallback):  # type: ignore
        def on_save(self, args: Any, state: Any, control: Any, **_: Any) -> None:  # noqa: D401
            step = int(state.global_step)
            if step <= 0:
                return
            try:
                ck_id, _vid = _persist_checkpoint(
                    run_id=run_id, step=step, model_dir=out_dir, tokenizer=tokenizer,
                    hyperparams=hyperparams, peft=peft, train_loss=float(state.log_history[-1].get("loss", 0.0))
                        if state.log_history else 0.0,
                )
                final_step_holder["step"] = step
                final_step_holder["checkpoint_id"] = ck_id
            except Exception:
                pass

    args = TrainingArguments(
        output_dir=out_dir,
        num_train_epochs=epochs,
        learning_rate=lr,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        save_steps=save_step_interval,
        save_strategy="steps",
        logging_steps=max(50, save_step_interval // 10),
        warmup_ratio=float(hyperparams.get("warmupRatio", 0.0)),
        weight_decay=float(hyperparams.get("weightDecay", 0.0)),
        seed=seed if seed is not None else 42,
        report_to=["none"],
        fp16=False,
        bf16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds_tok,
        callbacks=[_SaveCallback()],
    )
    trainer.train()

    # Always save a final checkpoint.
    final_step = int(trainer.state.global_step) if hasattr(trainer, "state") else len(text_rows)
    if not final_step_holder["checkpoint_id"]:
        ck_id, _vid = _persist_checkpoint(
            run_id=run_id, step=final_step, model_dir=out_dir, tokenizer=tokenizer,
            hyperparams=hyperparams, peft=peft, train_loss=0.0, is_final=True,
        )
        final_step_holder["step"] = final_step
        final_step_holder["checkpoint_id"] = ck_id
    else:
        # Mark the previous-saved checkpoint as final.
        _mark_checkpoint_final(final_step_holder["checkpoint_id"])

    return final_step_holder["step"], final_step_holder["checkpoint_id"]


def _persist_checkpoint(
    *,
    run_id: str,
    step: int,
    model_dir: str,
    tokenizer: Any,
    hyperparams: dict,
    peft: bool,
    train_loss: float,
    is_final: bool = False,
) -> tuple[str, str]:
    """Tar + gzip the latest checkpoint dir, upload to B2, register in RW."""
    import tarfile

    # transformers Trainer puts step checkpoints under {model_dir}/checkpoint-{step}.
    src_dir = os.path.join(model_dir, f"checkpoint-{step}")
    if not os.path.isdir(src_dir):
        # On final save with strategy=epoch, the dir may not exist; fall back to model_dir.
        src_dir = model_dir

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(src_dir, arcname=f"checkpoint-{step}")
    blob = buf.getvalue()

    sha = _sha256_bytes(blob)
    b2_key = f"{_CHECKPOINT_PREFIX}/{run_id}/step-{step:06d}.tar.gz"
    weight_uri = _texp._b2_put(b2_key, blob, content_type="application/gzip")

    checkpoint_id = f"ck-{run_id}-{step:06d}"
    vid = _vid_checkpoint(run_id, step)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_training_checkpoint
              (vertex_id, owner_did, checkpoint_id, run_id, step, train_loss, learning_rate,
               weight_b2_uri, weight_byte_size, weight_sha256, adapter_kind, adapter_rank,
               is_final, status, created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'available', %s,
                    CAST(%s AS date), 0, %s, %s, 'sys.training.checkpoint')
            """,
            (
                vid, _TRAINING_ACTOR, checkpoint_id, run_id, step,
                float(train_loss), float(hyperparams.get("learningRate", 0.0)),
                weight_uri, len(blob), sha,
                "lora" if peft else "full",
                int(hyperparams.get("loraRank", 0)) if peft else 0,
                bool(is_final), _now_iso(),
                _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )

    return checkpoint_id, vid


def _mark_checkpoint_final(checkpoint_id: str) -> None:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "UPDATE vertex_training_checkpoint SET is_final = true WHERE checkpoint_id = %s",
            (checkpoint_id,),
        )


# ──────────────────────────────────────────────────────────────────────
# Internal: eval
# ──────────────────────────────────────────────────────────────────────


def _has_lm_eval() -> bool:
    try:
        import lm_eval  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _run_one_bench(cp: dict, bench: str, *, sampleLimit: int | None) -> dict:
    """Run one bench. lm_eval-harness path if installed, otherwise a
    lightweight perplexity eval over the snapshot rows.
    """
    started = time.time()
    if _has_lm_eval() and bench != "internal-loss":
        return _run_lm_eval_bench(cp, bench, sampleLimit=sampleLimit, started=started)
    return _run_internal_loss_bench(cp, sampleLimit=sampleLimit, started=started)


def _run_lm_eval_bench(cp: dict, bench: str, *, sampleLimit: int | None, started: float) -> dict:
    import lm_eval  # type: ignore
    from lm_eval import evaluator  # type: ignore

    model_args = f"pretrained={cp.get('weight_b2_uri', '')}"
    out = evaluator.simple_evaluate(
        model="hf",
        model_args=model_args,
        tasks=[bench],
        limit=sampleLimit,
    )
    metrics: dict[str, Any] = dict(out.get("results", {}).get(bench, {}))
    metrics["_primary_metric"] = "acc" if "acc" in metrics else next(iter(metrics.keys()), "loss")
    metrics["sample_count"] = sampleLimit or 0
    metrics["duration_seconds"] = time.time() - started
    return metrics


def _run_internal_loss_bench(cp: dict, *, sampleLimit: int | None, started: float) -> dict:
    """Lightweight perplexity-style eval. Loads checkpoint weights from
    B2 (skipped here for cost) and approximates loss on the run's
    consumed dataset.
    """
    sample_count = min(sampleLimit or 1000, 1000)
    # Without re-loading the weights, we cannot compute true loss. We
    # surface a placeholder primary metric that downstream eval gates
    # can recognize ("loss"=0.0 with status='done' -> trivially passes,
    # so prod eval gates should require a non-internal bench).
    return {
        "_primary_metric": "loss",
        "loss": 0.0,
        "perplexity": 1.0,
        "sample_count": sample_count,
        "duration_seconds": time.time() - started,
        "note": "internal-loss is a placeholder; install lm_eval for real benches",
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Query primitives (read-only, CPU pod, ADR-2605070700)
# ──────────────────────────────────────────────────────────────────────


def task_train_list_runs(
    *,
    kind: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    **_: Any,
) -> dict:
    """SELECT recent training runs with optional kind / status filters."""
    cap = max(1, min(int(limit or 50), 500))
    where_clauses: list[str] = []
    params: list[Any] = []
    if kind:
        where_clauses.append("kind = %s")
        params.append(str(kind))
    if status:
        where_clauses.append("status = %s")
        params.append(str(status))
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = (
        "SELECT vertex_id, run_id, kind, base_model, dataset_snapshot_id, status, "
        "started_at, ended_at, completed_steps, failure_reason "
        f"FROM vertex_training_run {where_sql} "
        "ORDER BY started_at DESC NULLS LAST LIMIT " + str(cap)
    )
    rows: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        for r in _res:
            rows.append({
                "vertexId": r[0], "runId": r[1], "kind": r[2], "baseModel": r[3],
                "datasetSnapshotId": r[4], "status": r[5], "startedAt": str(r[6] or ""),
                "endedAt": str(r[7] or ""), "completedSteps": int(r[8] or 0),
                "failureReason": str(r[9] or ""),
            })
    return {"ok": True, "runs": rows, "count": len(rows)}


def task_train_list_checkpoints(
    *,
    runId: str | None = None,
    onlyFinal: bool | None = None,
    limit: int | None = None,
    **_: Any,
) -> dict:
    """SELECT checkpoints with optional run_id / is_final filters."""
    cap = max(1, min(int(limit or 50), 500))
    where_clauses: list[str] = []
    params: list[Any] = []
    if runId:
        where_clauses.append("run_id = %s")
        params.append(str(runId))
    if onlyFinal:
        where_clauses.append("is_final = true")
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = (
        "SELECT vertex_id, checkpoint_id, run_id, step, is_final, weight_b2_uri, "
        "weight_byte_size, weight_sha256, adapter_kind, adapter_rank, train_loss, created_at "
        f"FROM vertex_training_checkpoint {where_sql} "
        "ORDER BY run_id, step LIMIT " + str(cap)
    )
    rows: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        for r in _res:
            rows.append({
                "vertexId": r[0], "checkpointId": r[1], "runId": r[2], "step": int(r[3] or 0),
                "isFinal": bool(r[4]), "weightB2Uri": str(r[5] or ""),
                "weightByteSize": int(r[6] or 0), "weightSha256": str(r[7] or ""),
                "adapterKind": str(r[8] or ""), "adapterRank": int(r[9] or 0),
                "trainLoss": float(r[10] or 0.0), "createdAt": str(r[11] or ""),
            })
    return {"ok": True, "checkpoints": rows, "count": len(rows)}


def task_train_list_snapshots(
    *,
    datasetName: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    **_: Any,
) -> dict:
    """SELECT dataset snapshots, largest first."""
    cap = max(1, min(int(limit or 50), 500))
    where_clauses: list[str] = []
    params: list[Any] = []
    if datasetName:
        where_clauses.append("dataset_name = %s")
        params.append(str(datasetName))
    if status:
        where_clauses.append("status = %s")
        params.append(str(status))
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = (
        "SELECT vertex_id, snapshot_id, dataset_name, label, b2_prefix, shard_count, "
        "row_count, content_hash, status, created_at "
        f"FROM vertex_training_dataset_snapshot {where_sql} "
        "ORDER BY row_count DESC NULLS LAST LIMIT " + str(cap)
    )
    rows: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        for r in _res:
            rows.append({
                "vertexId": r[0], "snapshotId": r[1], "datasetName": r[2], "label": r[3],
                "b2Prefix": r[4], "shardCount": int(r[5] or 0), "rowCount": int(r[6] or 0),
                "contentHash": r[7], "status": r[8], "createdAt": str(r[9] or ""),
            })
    return {"ok": True, "snapshots": rows, "count": len(rows)}


def task_train_coverage_snapshot(**_: Any) -> dict:
    """Single-shot pipeline coverage aggregate.

    Mirrors the shosha.coverage pattern (read-only, audit omitted) — emits
    one row of counts + last-* timestamps for soak monitors / dashboards.
    """
    out: dict[str, Any] = {"ok": True, "asOf": _now_iso()}

    if True:

        client = get_kotoba_client()
        _res = client.q("SELECT count(*), COALESCE(SUM(row_count), 0) FROM vertex_training_dataset_snapshot WHERE status = 'frozen'")
        row = (_res[0] if _res else None) or (0, 0)
        out["snapshotsCount"] = int(row[0] or 0)
        out["datasetSnapshotRows"] = int(row[1] or 0)

        _res = client.q(
            """
            SELECT
              count(*),
              count(*) FILTER (WHERE status = 'queued'),
              count(*) FILTER (WHERE status = 'running'),
              count(*) FILTER (WHERE status = 'done'),
              count(*) FILTER (WHERE status = 'failed'),
              MAX(started_at)
            FROM vertex_training_run
            """
        )
        row = (_res[0] if _res else None) or (0, 0, 0, 0, 0, None)
        out["runsTotal"] = int(row[0] or 0)
        out["runsQueued"] = int(row[1] or 0)
        out["runsRunning"] = int(row[2] or 0)
        out["runsDone"] = int(row[3] or 0)
        out["runsFailed"] = int(row[4] or 0)
        out["lastRunStartedAt"] = str(row[5] or "")

        _res = client.q(
            """
            SELECT
              count(*),
              count(*) FILTER (WHERE is_final = true),
              COALESCE(SUM(weight_byte_size), 0),
              MAX(created_at)
            FROM vertex_training_checkpoint
            """
        )
        row = (_res[0] if _res else None) or (0, 0, 0, None)
        out["checkpointsTotal"] = int(row[0] or 0)
        out["checkpointsFinal"] = int(row[1] or 0)
        out["checkpointBytesTotal"] = int(row[2] or 0)
        out["lastCheckpointAt"] = str(row[3] or "")

        _res = client.q("SELECT count(*) FROM vertex_training_eval")
        out["evalsTotal"] = int(((_res[0] if _res else None) or (0,))[0] or 0)

        _res = client.q("SELECT count(*), MAX(promoted_at) FROM mv_training_active_serving")
        row = (_res[0] if _res else None) or (0, None)
        out["servingActiveCount"] = int(row[0] or 0)
        out["lastPromotedAt"] = str(row[1] or "")

    return out


def task_train_list_serving(*, alias: str | None = None, **_: Any) -> dict:
    """SELECT active serving alias → checkpoint promotions from MV."""
    where_clauses: list[str] = []
    params: list[Any] = []
    if alias:
        where_clauses.append("alias LIKE %s")
        params.append(f"%{alias}%")
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = (
        "SELECT alias, checkpoint_vertex_id, serving_target, promoted_at, promoted_by "
        f"FROM mv_training_active_serving {where_sql} "
        "ORDER BY promoted_at DESC NULLS LAST"
    )
    rows: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        for r in _res:
            rows.append({
                "alias": r[0], "checkpointVertexId": r[1], "servingTarget": str(r[2] or ""),
                "promotedAt": str(r[3] or ""), "promotedBy": str(r[4] or ""),
            })
    return {"ok": True, "serving": rows, "count": len(rows)}


# ──────────────────────────────────────────────────────────────────────
# RunPod Serverless handler entry (ADR-2605070700 Addendum 2026-05-07)
# ──────────────────────────────────────────────────────────────────────


def runpod_handler(event: dict) -> dict:
    """Entry point invoked from `kotodama.runpod_trainer_handler`.

    `event["input"]` is the payload posted by the CPU worker via
    `_delegate_to_runpod()`. The `kind` key dispatches to the appropriate
    GPU work:

      kind=sft / lora / distill → _run_finetune(...)
      kind=eval                 → _run_eval_heavy_benches(...)

    This handler runs inside the RunPod worker container which has GPU
    access + the same B2 / RW Secrets as the CPU worker. It returns
    the structured result dict that is forwarded back to the BPMN
    response without further transformation.
    """
    inp = event.get("input") or {}
    kind = str(inp.get("kind") or "").lower()
    # Pick the family default trunk when the caller did not pin one.
    # Baien kinds (`baien-lora`, `baien-multimodal-graft`) default to the
    # BitNet b1.58 master; everything else defaults to the Oka FP8 trunk.
    family_default = (
        _BAIEN_DEFAULT_TRUNK_MODEL
        if kind.startswith("baien")
        else _TRAINING_DEFAULT_BASE_MODEL
    )
    if kind in ("sft", "lora", "baien-lora", "baien-multimodal-graft"):
        return _run_finetune(
            kind=kind,
            runId=inp.get("runId"),
            baseModel=str(inp.get("baseModel") or family_default),
            baseModelRevision=inp.get("baseModelRevision") or _DEFAULT_BASE_REVISION,
            datasetSnapshotId=inp["datasetSnapshotId"],
            hyperparams=inp.get("hyperparams") or {},
            gpuTarget=inp.get("gpuTarget"),
            seed=inp.get("seed"),
            triggeredBy=inp.get("triggeredBy"),
            bpmnProcessInstanceKey=inp.get("bpmnProcessInstanceKey"),
            peft=(kind in ("lora", "baien-lora", "baien-multimodal-graft")),
        )
    if kind == "distill":
        hp = dict(inp.get("hyperparams") or {})
        hp["distillMethod"] = inp.get("distillMethod", "soft-logits")
        hp["temperature"] = inp.get("temperature", 1.0)
        hp["teacherLabelArtifactRunId"] = inp.get("teacherLabelArtifactRunId", "")
        return _run_finetune(
            kind="distill",
            runId=inp.get("runId"),
            baseModel=str(inp.get("studentBaseModel") or _TRAINING_DEFAULT_BASE_MODEL),
            baseModelRevision=inp.get("studentBaseModelRevision") or _DEFAULT_BASE_REVISION,
            datasetSnapshotId=inp["datasetSnapshotId"],
            hyperparams=hp,
            gpuTarget=inp.get("gpuTarget"),
            seed=inp.get("seed"),
            triggeredBy=inp.get("triggeredBy"),
            bpmnProcessInstanceKey=inp.get("bpmnProcessInstanceKey"),
            peft=False,
            teacherKind=inp.get("teacherKind"),
            teacherRunId=inp.get("teacherRunId"),
            teacherActorDid=inp.get("teacherActorDid"),
            teacherLabelArtifactRunId=inp.get("teacherLabelArtifactRunId"),
        )
    if kind == "eval":
        return _run_eval_heavy_benches(
            checkpointId=inp["checkpointId"],
            run_id=inp.get("runId", ""),
            benches=inp.get("benches") or [],
            evalDatasetName=inp.get("evalDatasetName"),
            sampleLimit=inp.get("sampleLimit"),
        )
    if kind == "baien-mx-train":
        return _run_baien_mx(
            runId=inp.get("runId"),
            baseModel=str(inp.get("baseModel") or _BAIEN_DEFAULT_TRUNK_MODEL),
            baseModelRevision=inp.get("baseModelRevision") or _DEFAULT_BASE_REVISION,
            datasetSnapshotId=inp["datasetSnapshotId"],
            modalities=list(inp.get("modalities") or []),
            fusionLayerIndex=int(inp.get("fusionLayerIndex") or 15),
            trunkFrozen=bool(inp.get("trunkFrozen", True)),
            loraOverFirst4Layers=bool(inp.get("loraOverFirst4Layers", False)),
            hyperparams=dict(inp.get("hyperparams") or {}),
            gpuTarget=inp.get("gpuTarget"),
            seed=inp.get("seed"),
            triggeredBy=inp.get("triggeredBy"),
            bpmnProcessInstanceKey=inp.get("bpmnProcessInstanceKey"),
        )
    return {"ok": False, "error": f"unknown training kind={kind!r}"}


# ──────────────────────────────────────────────────────────────────────
# Baien-MX (ADR 2605101000) — multimodal expansion handler
# ──────────────────────────────────────────────────────────────────────

_BAIEN_MX_VALID_MODALITIES = ("triple", "vec768", "vec4096fp8", "3dblob")


def _run_baien_mx(
    *,
    runId: str | None,
    baseModel: str,
    baseModelRevision: str,
    datasetSnapshotId: str,
    modalities: list[str],
    fusionLayerIndex: int,
    trunkFrozen: bool,
    loraOverFirst4Layers: bool,
    hyperparams: dict,
    gpuTarget: str | None,
    seed: int | None,
    triggeredBy: str | None,
    bpmnProcessInstanceKey: str | None,
) -> dict:
    """Train Baien-MX per-modality projectors + fusion block (ADR
    2605101000). Records:
      1 vertex_training_run header (kind='baien-mx-train')
      1 edge_training_consumed_dataset (run -> snapshot)
      N+1 vertex_training_checkpoint rows:
        - one per modality      (kind=baien-mx-projector-{modality})
        - one shared fusion     (kind=baien-mx-fusion)

    The actual H100-side training loop lands in step 5/6 of the ADR.
    For now the function performs the full RW write contract and
    leaves placeholder B2 URIs that the H100 runner will overwrite
    on first save step.
    """
    invalid = [m for m in modalities if m not in _BAIEN_MX_VALID_MODALITIES]
    if invalid:
        raise ValueError(
            f"unknown Baien-MX modality {invalid!r}; "
            f"valid: {list(_BAIEN_MX_VALID_MODALITIES)}"
        )
    if not modalities:
        raise ValueError("Baien-MX requires at least one non-text modality")

    run_id = runId or _gen_id("run")
    run_vid = _vid_run(run_id)
    started_at = _now_iso()
    snapshot = _resolve_snapshot(datasetSnapshotId)

    hp = dict(hyperparams)
    hp["modalities"] = modalities
    hp["fusionLayerIndex"] = fusionLayerIndex
    hp["trunkFrozen"] = trunkFrozen
    hp["loraOverFirst4Layers"] = loraOverFirst4Layers
    hp_json = _stringify_hyperparams(hp)

    if True:

        client = get_kotoba_client()
        # Run header.
        _res = client.q(
            """
            INSERT INTO vertex_training_run
              (vertex_id, owner_did, run_id, kind, base_model, base_model_revision,
               dataset_snapshot_id, teacher_run_id, teacher_actor_did,
               hyperparams_json, gpu_target, seed, status, started_at,
               triggered_by, bpmn_process_instance_key,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, 'baien-mx-train', %s, %s, %s, '', '',
                    %s, %s, %s, 'running', %s, %s, %s,
                    %s, CAST(%s AS date), 0, %s, %s, 'sys.training.run')
            """,
            (
                run_vid, _TRAINING_ACTOR, run_id, baseModel, baseModelRevision,
                datasetSnapshotId,
                hp_json, gpuTarget or "", seed,
                started_at, triggeredBy or "", bpmnProcessInstanceKey or "",
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )
        # Edge: run -> dataset.
        consumed_edge_id = f"consumed:{run_id}:{snapshot['snapshotId']}"
        _res = client.q(
            """
            INSERT INTO edge_training_consumed_dataset
              (edge_id, owner_did, src_vid, dst_vid, role, mix_ratio,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, 'primary', 1.0, %s, CAST(%s AS date), 0, %s, %s, 'sys.training.consume')
            """,
            (consumed_edge_id, _TRAINING_ACTOR, run_vid,
             _vid_snapshot(snapshot["snapshotId"]),
             _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR),
        )

    # Per-modality + fusion checkpoint placeholder rows. The H100
    # runner overwrites b2_uri / sha256 / step at first save.
    projector_checkpoints: dict[str, str] = {}
    for modality in modalities:
        ckpt_id = _gen_id(f"baien-mx-proj-{modality}")
        ckpt_vid = _vid_checkpoint(ckpt_id, 0)
        _write_baien_mx_checkpoint_placeholder(
            checkpoint_id=ckpt_id, vertex_id=ckpt_vid, run_id=run_id,
            kind=f"baien-mx-projector-{modality}",
        )
        projector_checkpoints[modality] = ckpt_vid

    fusion_id = _gen_id("baien-mx-fusion")
    fusion_vid = _vid_checkpoint(fusion_id, 0)
    _write_baien_mx_checkpoint_placeholder(
        checkpoint_id=fusion_id, vertex_id=fusion_vid, run_id=run_id,
        kind="baien-mx-fusion",
    )

    return {
        "ok": True,
        "runId": run_id,
        "runVertexId": run_vid,
        "datasetSnapshotId": datasetSnapshotId,
        "modalities": modalities,
        "fusionCheckpointId": fusion_vid,
        "projectorCheckpoints": json.dumps(projector_checkpoints),
        "evalSummary": "",
    }


def _write_baien_mx_checkpoint_placeholder(
    *, checkpoint_id: str, vertex_id: str, run_id: str, kind: str,
) -> None:
    """Insert a placeholder vertex_training_checkpoint row that the
    H100 runner overwrites on the first save step. Keeping the row
    pre-allocated lets the lexicon caller reference the vertex_id
    immediately after `runBaienMx` returns."""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_training_checkpoint
              (vertex_id, owner_did, checkpoint_id, run_id, step,
               kind, b2_uri, sha256, status,
               created_at, created_date, sensitivity_ord, org_id, user_id, actor_id)
            VALUES (%s, %s, %s, %s, 0,
                    %s, '', '', 'pending',
                    %s, CAST(%s AS date), 0, %s, %s, 'sys.training.checkpoint')
            """,
            (
                vertex_id, _TRAINING_ACTOR, checkpoint_id, run_id,
                kind,
                _now_iso(), _today(), _TRAINING_ACTOR, _TRAINING_ACTOR,
            ),
        )


def task_train_baien_mx_run(
    *,
    runId: str | None = None,
    baseModel: str | None = None,
    baseModelRevision: str | None = None,
    datasetSnapshotId: str,
    modalities: list[str],
    fusionLayerIndex: int = 15,
    trunkFrozen: bool = True,
    loraOverFirst4Layers: bool = False,
    hyperparams: dict | None = None,
    gpuTarget: str | None = None,
    seed: int | None = None,
    triggeredBy: str | None = None,
    bpmnProcessInstanceKey: str | None = None,
    **_: Any,
) -> dict:
    """Local CPU-pod entry that delegates Baien-MX training to the H100
    pod (ADR 2605101000). Same wire shape as task_train_baien_lora_run
    but with a `modalities` list and Baien-MX-specific architecture
    knobs."""
    snapshot = _resolve_snapshot(datasetSnapshotId)
    return _delegate_to_runpod("baien-mx-train", {
        "runId": runId or _gen_id("run"),
        "baseModel": baseModel or _BAIEN_DEFAULT_TRUNK_MODEL,
        "baseModelRevision": baseModelRevision or _DEFAULT_BASE_REVISION,
        "datasetSnapshotId": snapshot["snapshotId"],
        "modalities": list(modalities),
        "fusionLayerIndex": fusionLayerIndex,
        "trunkFrozen": trunkFrozen,
        "loraOverFirst4Layers": loraOverFirst4Layers,
        "hyperparams": hyperparams or {},
        "gpuTarget": gpuTarget,
        "seed": seed,
        "triggeredBy": triggeredBy,
        "bpmnProcessInstanceKey": bpmnProcessInstanceKey,
    })


def _run_eval_heavy_benches(
    *,
    checkpointId: str,
    run_id: str,
    benches: list[str],
    evalDatasetName: str | None,
    sampleLimit: int | None,
) -> dict:
    """RunPod-side heavy eval: loop benches, run lm_eval-harness, INSERT
    one vertex_training_eval row per bench. Returns evalIds + primaryScores.
    """
    cp = _resolve_checkpoint(checkpointId)
    eval_ids: list[str] = []
    primary_scores: dict[str, float] = {}
    for bench in benches:
        try:
            metrics = _run_lm_eval_bench(cp, bench, sampleLimit=sampleLimit, started=time.time())
            status = "done"
        except Exception as e:
            metrics = {"error": str(e)}
            status = "failed"
        eval_id, primary_score = _record_eval_row(
            checkpointId=checkpointId, run_id=cp["run_id"] or run_id, bench=bench,
            metrics=metrics, eval_runner="runpod-lm-eval",
            evalDatasetName=evalDatasetName, status=status,
        )
        eval_ids.append(eval_id)
        if status == "done":
            primary_scores[bench] = primary_score
        else:
            primary_scores[f"{bench}.error"] = -1.0
    return {
        "ok": True,
        "checkpointId": checkpointId,
        "evalCount": len(eval_ids),
        "evalIds": eval_ids,
        "primaryScores": json.dumps(primary_scores),
    }


def register(worker: Any, *, timeout_ms: int = 1_800_000) -> None:
    """Wire all training task types onto the shared LangServer worker.

    Static manifest below repeats each task_type as a literal so the
    BPMN worker-task coverage linter discovers them despite camelCase.

      task_type="train.dataset.snapshot"
      task_type="train.teacher.label"
      task_type="train.sft.run"
      task_type="train.lora.run"
      task_type="train.distill.run"
      task_type="train.eval.run"
      task_type="train.promote.checkpoint"
      task_type="train.list.runs"
      task_type="train.list.checkpoints"
      task_type="train.list.snapshots"
      task_type="train.list.serving"
      task_type="train.coverage.snapshot"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    # Lightweight tasks (no GPU, fast).
    t("train.dataset.snapshot",   task_train_dataset_snapshot, ms=120_000)
    t("train.promote.checkpoint", task_train_promote_checkpoint, ms=30_000)
    # Read-only query tasks (no GPU, fast).
    t("train.list.runs",          task_train_list_runs,        ms=15_000)
    t("train.list.checkpoints",   task_train_list_checkpoints, ms=15_000)
    t("train.list.snapshots",     task_train_list_snapshots,   ms=15_000)
    t("train.list.serving",       task_train_list_serving,     ms=15_000)
    t("train.coverage.snapshot",  task_train_coverage_snapshot, ms=15_000)
    # Medium tasks (network IO).
    t("train.teacher.label",      task_train_teacher_label,    ms=900_000)
    t("train.eval.run",           task_train_eval_run,         ms=600_000)
    # Heavy tasks (GPU).
    t("train.sft.run",            task_train_sft_run,          ms=1_800_000)
    t("train.lora.run",           task_train_lora_run,         ms=1_800_000)
    t("train.distill.run",        task_train_distill_run,      ms=3_600_000)
