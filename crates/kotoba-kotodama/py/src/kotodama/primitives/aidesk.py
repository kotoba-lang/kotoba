"""
aidesk primitives — AI Design Desk CAD synthesis (ADSKAILab Zero-To-CAD).

License:
  Zero-To-CAD-Qwen3-VL-2B: Apache 2.0 → commercial B2B (tsukuru handoff allowed)
  Make-A-Shape / WaLa:      Autodesk Non-Commercial → research only (Phase 2)

CRITICAL: _tsukuru_handoff_gate() is a structural gate, not a soft check.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import logging
from typing import Any

logger = logging.getLogger(__name__)

ZERO_TO_CAD_MODEL_ID = "ADSKAILab/Zero-To-CAD-Qwen3-VL-2B"
ZERO_TO_CAD_MODEL_CACHE = os.environ.get("AIDESK_MODEL_CACHE", "/model-cache/zero-to-cad")
COMMERCIAL_LICENSE_TIERS: frozenset[str] = frozenset({"apache2"})

B2_BUCKET = os.environ.get("B2_BUCKET_NAME", "etzhayyim-nats")
B2_KEY_ID = os.environ.get("B2_ACCESS_KEY_ID", "")
B2_APP_KEY = os.environ.get("B2_APPLICATION_KEY", "")
B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")

BPMN_DISPATCHER_URL = os.environ.get(
    "BPMN_DISPATCHER_INTERNAL_URL",
    "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
)
BPMN_DISPATCHER_SECRET = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "")


# ---------------------------------------------------------------------------
# Zeebe task: Zero-To-CAD inference
# ---------------------------------------------------------------------------

async def task_aidesk_cad_synthesize(variables: dict[str, Any]) -> dict[str, Any]:
    """
    Zero-To-CAD inference: 8-view input images → CadQuery Python code.

    Zeebe task type: aidesk.cad.synthesize
    Input variables: jobId, inputB2Keys (list[str]), inputType
    Output variables: cadqueryCode (str), licenseTier="apache2", modelId
    """
    job_id = variables["jobId"]
    b2_keys: list[str] = variables["inputB2Keys"]
    input_type: str = variables.get("inputType", "multi-view")

    logger.info("aidesk.cad.synthesize jobId=%s inputType=%s n_images=%d", job_id, input_type, len(b2_keys))

    # Download input images from B2
    image_paths = [_b2_download(k, f"/tmp/aidesk-{job_id}-{i}.jpg") for i, k in enumerate(b2_keys)]

    # Run Zero-To-CAD inference
    cadquery_code = _run_zero_to_cad(image_paths)

    # Cleanup temp images
    for p in image_paths:
        try:
            os.unlink(p)
        except OSError:
            pass

    return {
        "cadqueryCode": cadquery_code,
        "licenseTier": "apache2",
        "modelId": ZERO_TO_CAD_MODEL_ID,
    }


def _run_zero_to_cad(image_paths: list[str]) -> str:
    """Load Zero-To-CAD model and run inference. Returns CadQuery Python code."""
    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        from PIL import Image
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "transformers / Pillow / torch required for Zero-To-CAD inference. "
            "Install via: pip install transformers Pillow torch"
        ) from exc

    processor = AutoProcessor.from_pretrained(ZERO_TO_CAD_MODEL_CACHE, trust_remote_code=True)
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        ZERO_TO_CAD_MODEL_CACHE,
        torch_dtype=torch.float32,  # CPU inference
        device_map="cpu",
    )
    model.eval()

    images = [Image.open(p).convert("RGB") for p in image_paths]

    # Build prompt following Zero-To-CAD paper convention (8-view layout)
    image_content = [{"type": "image", "image": img} for img in images]
    messages = [
        {
            "role": "user",
            "content": image_content + [
                {
                    "type": "text",
                    "text": (
                        "Generate CadQuery Python code to reconstruct this 3D shape. "
                        "Output only the Python code. The variable `result` must hold the final CadQuery Workplane object."
                    ),
                }
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=images, return_tensors="pt")

    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=2048, do_sample=False)

    generated = processor.batch_decode(
        output_ids[:, inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )[0]

    # Extract code block if wrapped in ```python ... ```
    if "```python" in generated:
        generated = generated.split("```python")[1].split("```")[0].strip()
    elif "```" in generated:
        generated = generated.split("```")[1].split("```")[0].strip()

    return generated


# ---------------------------------------------------------------------------
# Zeebe task: CadQuery execution → STEP file → B2
# ---------------------------------------------------------------------------

async def task_aidesk_cad_execute(variables: dict[str, Any]) -> dict[str, Any]:
    """
    Execute CadQuery Python code → STEP file → upload to B2.

    Zeebe task type: aidesk.cad.execute
    Input variables: jobId, cadqueryCode
    Output variables: stepB2Key (str), format="step"
    """
    job_id: str = variables["jobId"]
    cadquery_code: str = variables["cadqueryCode"]

    logger.info("aidesk.cad.execute jobId=%s code_len=%d", job_id, len(cadquery_code))

    with tempfile.TemporaryDirectory() as tmpdir:
        py_path = os.path.join(tmpdir, "model.py")
        step_path = os.path.join(tmpdir, "model.step")

        # Write CadQuery script with STEP export appended
        with open(py_path, "w") as f:
            f.write(cadquery_code)
            f.write(f'\nimport cadquery as cq\ncq.exporters.export(result, "{step_path}")\n')

        subprocess.run(["python", py_path], timeout=120, check=True, cwd=tmpdir, capture_output=True)

        if not os.path.exists(step_path):
            raise RuntimeError(f"CadQuery execution did not produce a STEP file at {step_path}")

        b2_key = f"aidesk/{job_id}/model.step"
        _b2_upload(step_path, b2_key)

    return {"stepB2Key": b2_key, "format": "step"}


# ---------------------------------------------------------------------------
# Zeebe task: tsukuru handoff (license gate + K8s-internal dispatch)
# ---------------------------------------------------------------------------

async def task_aidesk_tsukuru_handoff(variables: dict[str, Any]) -> dict[str, Any]:
    """
    Forward Apache 2.0 artifact to tsukuru supplierExchange.normalizePackage via K8s-internal.

    Zeebe task type: aidesk.tsukuru.handoff
    CRITICAL: _tsukuru_handoff_gate() raises ValueError for Non-Commercial artifacts.
    """
    _tsukuru_handoff_gate(variables)

    step_b2_key: str = variables["stepB2Key"]
    cadquery_code: str = variables.get("cadqueryCode", "")
    rfq_notes: str = variables.get("rfqNotes", "")
    job_id: str = variables["jobId"]

    payload = {
        "package_id": f"aidesk-pkg-{job_id}",
        "exchange_format": "step",
        "artifacts": [
            {"type": "step", "b2_key": step_b2_key},
            {"type": "cadquery", "code": cadquery_code[:4000] if cadquery_code else ""},
        ],
        "requirements": {"origin": "aidesk", "license_tier": "apache2"},
        "channels": ["step", "cadquery"],
        "rfq_notes": rfq_notes,
    }

    import httpx
    headers = {"content-type": "application/json"}
    if BPMN_DISPATCHER_SECRET:
        headers["x-internal-trust"] = BPMN_DISPATCHER_SECRET

    nsid = "com.etzhayyim.apps.tsukuru.supplierExchange.normalizePackage"
    resp = httpx.post(
        f"{BPMN_DISPATCHER_URL}/xrpc/{nsid}",
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    resp.raise_for_status()
    result = resp.json()
    tsukuru_package_id = result.get("packageId", f"tsukuru-pkg-{job_id}")

    logger.info("aidesk.tsukuru.handoff jobId=%s tsukuruPackageId=%s", job_id, tsukuru_package_id)
    return {"tsukuruPackageId": tsukuru_package_id, "dispatched": True}


def _tsukuru_handoff_gate(variables: dict[str, Any]) -> None:
    """Structural gate — raises ValueError for any Non-Commercial artifact. Not a soft check."""
    license_tier = variables.get("license_tier") or variables.get("licenseTier", "")
    if license_tier not in COMMERCIAL_LICENSE_TIERS:
        raise ValueError(
            f"aidesk tsukuru handoff DENIED: license_tier={license_tier!r} is not in "
            f"COMMERCIAL_LICENSE_TIERS={COMMERCIAL_LICENSE_TIERS}. "
            "Only Apache 2.0 artifacts may be forwarded to tsukuru commercial supplier exchange. "
            "Autodesk Non-Commercial (Make-A-Shape/WaLa) artifacts must remain in aidesk.research.* namespace."
        )


# ---------------------------------------------------------------------------
# B2 helpers
# ---------------------------------------------------------------------------

def _b2_download(b2_key: str, local_path: str) -> str:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APP_KEY,
    )
    s3.download_file(B2_BUCKET, b2_key, local_path)
    return local_path


def _b2_upload(local_path: str, b2_key: str) -> str:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APP_KEY,
    )
    s3.upload_file(local_path, B2_BUCKET, b2_key)
    return b2_key


# ---------------------------------------------------------------------------
# Worker registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire aidesk CAD synthesis primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False,
                    timeout_ms=ms if ms is not None else timeout_ms)(fn)

    t("aidesk.cad.synthesize",  task_aidesk_cad_synthesize,  ms=600_000)  # up to 10min CPU inference
    t("aidesk.cad.execute",     task_aidesk_cad_execute,     ms=180_000)  # CadQuery + B2 upload
    t("aidesk.tsukuru.handoff", task_aidesk_tsukuru_handoff, ms=60_000)
