"""Hume teacher distillation pipeline primitives.

The pipeline keeps the operational loop inside Zeebe:

1. generate balanced text samples,
2. label them with Hume Expression Measurement,
3. build SFT JSONL,
4. train the lightweight TF-IDF centroid student,
5. write versioned artifacts and return a compact manifest.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

from kotodama.primitives import hume_emotion

CAUTION = hume_emotion.CAUTION
NON_EMOTION_LABELS = hume_emotion.NON_EMOTION_LABELS
STOP = hume_emotion.STOP

EMOTION_PROMPTS: dict[str, list[str]] = {
    "joy": [
        "I just heard wonderful news and I cannot stop smiling.",
        "The launch went better than expected, and everyone is celebrating.",
        "We finally solved it, and the whole room felt lighter.",
    ],
    "relief": [
        "The issue is fixed now, and I can finally breathe again.",
        "The backup worked, so the data is safe after all.",
        "It is over now, and the pressure has started to fade.",
    ],
    "anger": [
        "They ignored every warning, and now the same problem happened again.",
        "This decision was careless, and it put the whole team at risk.",
        "I asked for a clear answer and got another excuse instead.",
    ],
    "anxiety": [
        "I keep thinking about what could go wrong before the deadline.",
        "The numbers do not look stable, and I am worried about the review.",
        "Every alert makes me wonder whether a bigger failure is starting.",
    ],
    "sadness": [
        "I miss the way things used to feel before everything changed.",
        "The result was final, and I felt a quiet heaviness settle in.",
        "It hurts to let go of something I cared about.",
    ],
    "confusion": [
        "The instructions conflict with each other, and I am not sure what to follow.",
        "The logs point in three directions at once.",
        "I expected one result, but the system returned something unrelated.",
    ],
    "gratitude": [
        "Thank you for noticing the problem and helping me fix it.",
        "Your support made a difficult day much easier.",
        "I appreciate the time you spent reviewing the details.",
    ],
    "pride": [
        "We built this carefully, and I am proud of the result.",
        "I worked hard for this milestone, and it feels earned.",
        "The team handled the pressure well and delivered something solid.",
    ],
    "doubt": [
        "The idea might work, but I am not convinced yet.",
        "Something about this answer feels incomplete.",
        "I am not sure the evidence supports that conclusion.",
    ],
    "calm": [
        "Let's take this one step at a time and check the facts.",
        "The situation is manageable if we stay focused.",
        "I feel steady now that the plan is clear.",
    ],
    "excitement": [
        "This is exactly the breakthrough I hoped for.",
        "The prototype works, and the next version could be huge.",
        "This opens up so many possibilities.",
    ],
    "disappointment": [
        "I expected a stronger result after all that effort.",
        "The demo failed at the worst possible time.",
        "I hoped for better news, but the outcome fell short.",
    ],
}

MODIFIERS = [
    "Keep the tone direct and personal.",
    "Frame it as a short workplace message.",
    "Make it sound like a project update.",
    "Write it as a private reflection.",
    "Use a restrained, professional style.",
]


def _run_id(prefix: str = "hume-distill-text") -> str:
    return f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"


def _artifact_dir(path: str = "", run_id: str = "") -> Path:
    base = Path(path or os.environ.get("HUME_DISTILLATION_ARTIFACT_DIR", "/tmp/hume-distillation"))
    target = base / (run_id or _run_id())
    target.mkdir(parents=True, exist_ok=True)
    return target


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z']{1,}", (text or "").lower()) if t not in STOP]


def _build_vocab(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, float]]:
    df: dict[str, int] = {}
    for row in rows:
        for token in set(_tokenize(str(row.get("input", {}).get("text") or ""))):
            df[token] = df.get(token, 0) + 1
    vocab = sorted(df)
    idf = {token: math.log((1 + len(rows)) / (1 + df[token])) + 1 for token in vocab}
    return vocab, idf


def _vectorize(text: str, vocab: set[str], idf: dict[str, float]) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in _tokenize(text):
        if token in vocab:
            counts[token] = counts.get(token, 0.0) + 1.0
    norm = 0.0
    for token, count in list(counts.items()):
        value = count * float(idf.get(token, 1.0))
        counts[token] = value
        norm += value * value
    norm = math.sqrt(norm) or 1.0
    return {token: value / norm for token, value in counts.items()}


def _add_weighted(target: dict[str, float], vec: dict[str, float], weight: float) -> None:
    for token, value in vec.items():
        target[token] = target.get(token, 0.0) + value * weight


def _normalize_vec(vec: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in vec.values())) or 1.0
    for token in list(vec):
        vec[token] /= norm
    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * float(b.get(token, 0.0)) for token, value in a.items())


def _predict(model: dict[str, Any], text: str) -> dict[str, Any]:
    vocab = set(model["vocab"])
    vec = _vectorize(text, vocab, model["idf"])
    scored: list[dict[str, float]] = []
    for name, centroid in model["emotionCentroids"].items():
        if str(name).lower() in NON_EMOTION_LABELS:
            continue
        similarity = _cosine(vec, centroid)
        prior = float(model["primaryPriors"].get(name, 0.0))
        score = max(0.0, min(1.0, similarity * 0.82 + prior * 0.18))
        if score > 0:
            scored.append({"name": name, "score": score})
    fallback = [
        {"name": item["name"], "score": min(0.35, float(item["score"]))}
        for item in model["globalTopEmotions"]
        if str(item.get("name", "")).lower() not in NON_EMOTION_LABELS
    ]
    seen: set[str] = set()
    top: list[dict[str, float]] = []
    for item in sorted(scored + fallback, key=lambda value: value["score"], reverse=True):
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


def _train(rows: list[dict[str, Any]]) -> dict[str, Any]:
    vocab, idf = _build_vocab(rows)
    vocab_set = set(vocab)
    centroids: dict[str, dict[str, float]] = {}
    weights: dict[str, float] = {}
    primary_counts: dict[str, int] = {}
    global_scores: dict[str, float] = {}

    for row in rows:
        text = str(row.get("input", {}).get("text") or "")
        vec = _vectorize(text, vocab_set, idf)
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        primary = labels.get("primary") if isinstance(labels.get("primary"), dict) else {}
        primary_name = primary.get("name")
        for emotion in labels.get("topEmotions") or []:
            name = emotion.get("name")
            score = float(emotion.get("score") or 0.0)
            if not name or str(name).lower() in NON_EMOTION_LABELS:
                continue
            weight = score * 0.35 + (1.5 if name == primary_name else 0.0)
            centroids.setdefault(str(name), {})
            weights[str(name)] = weights.get(str(name), 0.0) + weight
            global_scores[str(name)] = global_scores.get(str(name), 0.0) + score
            _add_weighted(centroids[str(name)], vec, weight)
        if primary_name:
            primary_counts[str(primary_name)] = primary_counts.get(str(primary_name), 0) + 1

    for emotion, vec in centroids.items():
        divisor = weights.get(emotion, 1.0) or 1.0
        for token in list(vec):
            vec[token] /= divisor
        _normalize_vec(vec)

    total_primary = sum(primary_counts.values()) or 1
    data_hash = hashlib.sha256(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "com.etzhayyim.apps.hume.studentTextExpressionModel.v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "algorithm": "tfidf_emotion_centroid",
        "teacher": {"provider": "hume", "api": "expression-measurement", "sunset": hume_emotion.EXPRESSION_SUNSET},
        "outputSchema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "vocab": vocab,
        "idf": idf,
        "emotionCentroids": centroids,
        "primaryPriors": {name: count / total_primary for name, count in primary_counts.items()},
        "globalTopEmotions": [
            {"name": name, "score": score / max(1, len(rows))}
            for name, score in sorted(global_scores.items(), key=lambda item: item[1], reverse=True)[:24]
        ],
        "training": {"rows": len(rows), "sourceIds": [row.get("sourceId") for row in rows], "dataHash": data_hash},
    }


def _evaluate(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = {}
    confusion: dict[str, int] = {}
    for row in rows:
        split = str(row.get("split") or "train")
        stats = metrics.setdefault(split, {"total": 0, "top1": 0, "knownPrimary": 0, "confidenceAbsError": 0.0})
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        primary = labels.get("primary") if isinstance(labels.get("primary"), dict) else {}
        actual = primary.get("name")
        actual_conf = float(labels.get("confidence") or primary.get("score") or 0.0)
        pred = _predict(model, str(row.get("input", {}).get("text") or ""))
        predicted = (pred.get("primary") or {}).get("name")
        stats["total"] += 1
        stats["top1"] += 1 if predicted == actual else 0
        stats["knownPrimary"] += 1 if actual in model["emotionCentroids"] else 0
        stats["confidenceAbsError"] += abs(float(pred.get("confidence") or 0.0) - actual_conf)
        confusion[f"{actual}=>{predicted}"] = confusion.get(f"{actual}=>{predicted}", 0) + 1
    for stats in metrics.values():
        total = int(stats["total"]) or 1
        stats["top1Accuracy"] = stats["top1"] / total
        stats["meanConfidenceAbsError"] = stats["confidenceAbsError"] / total
        del stats["confidenceAbsError"]
    return {
        "schema": "com.etzhayyim.apps.hume.studentTextTrainingReport.v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": len(rows),
        "metrics": metrics,
        "confusion": confusion,
        "caveat": "Operational bootstrap model; expand real multimodal samples before high-risk routing.",
    }


def _media_feature_text(row: dict[str, Any]) -> str:
    input_obj = row.get("input") if isinstance(row.get("input"), dict) else {}
    modality = str(row.get("modality") or input_obj.get("modality") or "media")
    transcript = str(input_obj.get("transcript") or input_obj.get("text") or "")
    urls = input_obj.get("urls") if isinstance(input_obj.get("urls"), list) else []
    file_count = int(input_obj.get("fileCount") or 0)
    return " ".join(
        [
            f"modality_{modality}",
            f"files_{file_count}",
            f"urls_{len(urls)}",
            transcript,
        ]
    ).strip()


def _train_media(rows: list[dict[str, Any]]) -> dict[str, Any]:
    materialized = [{**row, "input": {**(row.get("input") or {}), "text": _media_feature_text(row)}} for row in rows]
    model = _train(materialized)
    model["schema"] = "com.etzhayyim.apps.hume.studentMediaExpressionModel.v1"
    model["algorithm"] = "media_metadata_tfidf_emotion_centroid"
    model["modalities"] = sorted({str(row.get("modality") or "media") for row in rows})
    model["featureContract"] = {
        "modality": "categorical token",
        "fileCount": "bucket token",
        "urlCount": "bucket token",
        "transcript": "optional text/prosody transcript tokenized with shared text pipeline",
    }
    model["training"]["sourceIds"] = [row.get("sourceId") for row in rows]
    return model


def _predict_media(model: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return _predict(model, _media_feature_text(row))


def _evaluate_media(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = {}
    confusion: dict[str, int] = {}
    for row in rows:
        split = str(row.get("split") or "train")
        stats = metrics.setdefault(split, {"total": 0, "top1": 0, "knownPrimary": 0, "confidenceAbsError": 0.0})
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        primary = labels.get("primary") if isinstance(labels.get("primary"), dict) else {}
        actual = primary.get("name")
        actual_conf = float(labels.get("confidence") or primary.get("score") or 0.0)
        pred = _predict_media(model, row)
        predicted = (pred.get("primary") or {}).get("name")
        stats["total"] += 1
        stats["top1"] += 1 if predicted == actual else 0
        stats["knownPrimary"] += 1 if actual in model["emotionCentroids"] else 0
        stats["confidenceAbsError"] += abs(float(pred.get("confidence") or 0.0) - actual_conf)
        confusion[f"{actual}=>{predicted}"] = confusion.get(f"{actual}=>{predicted}", 0) + 1
    for stats in metrics.values():
        total = int(stats["total"]) or 1
        stats["top1Accuracy"] = stats["top1"] / total
        stats["meanConfidenceAbsError"] = stats["confidenceAbsError"] / total
        del stats["confidenceAbsError"]
    return {
        "schema": "com.etzhayyim.apps.hume.studentMediaTrainingReport.v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": len(rows),
        "modalities": model.get("modalities") or [],
        "metrics": metrics,
        "confusion": confusion,
        "caveat": "Bootstrap media head trained on teacher-labeled media metadata/transcripts; replace with audio/image encoders after collecting enough examples.",
    }


def _sft_rows(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system = (
        "You are an emotion-expression classifier used as a student model. "
        "Infer perceived expression from the provided evidence. Return only valid JSON "
        "matching com.etzhayyim.apps.hume.normalizedExpression.v1. Do not claim a person's true internal state."
    )
    rows = []
    for row in examples:
        payload = {
            "modality": row.get("modality"),
            "text": row.get("input", {}).get("text", ""),
            "urls": row.get("input", {}).get("urls", []),
            "fileCount": row.get("input", {}).get("fileCount", 0),
            "context": "Classify perceived expression. Return JSON only.",
        }
        rows.append(
            {
                "sourceId": row.get("sourceId"),
                "split": row.get("split"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
                    {"role": "assistant", "content": json.dumps(row.get("labels") or {}, separators=(",", ":"))},
                ],
            }
        )
    return rows


def _walk_strings(value: Any, key_hint: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(_walk_strings(item, str(key)))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item, key_hint))
    elif isinstance(value, str):
        found.append((key_hint, value))
    return found


def _extract_tts_audio_base64(response: dict[str, Any]) -> str:
    candidates = _walk_strings(response)
    preferred_keys = {"audio", "audioBase64", "data", "content", "base64"}
    for key, value in candidates:
        if key in preferred_keys and len(value) > 200:
            if value.startswith("data:"):
                return value.split(",", 1)[-1]
            if "://" not in value:
                return value
    for _key, value in candidates:
        if len(value) > 200 and "://" not in value:
            if value.startswith("data:"):
                return value.split(",", 1)[-1]
            return value
    return ""


def _emotion_voice_description(emotion: str) -> str:
    descriptions = {
        "joy": "Bright, warm, smiling delivery with natural enthusiasm.",
        "relief": "Soft, relieved delivery with a gentle exhale and lower tension.",
        "anger": "Controlled but clearly frustrated delivery, firm and clipped.",
        "anxiety": "Uneasy, tense delivery with slight urgency and uncertainty.",
        "sadness": "Quiet, subdued delivery with gentle heaviness.",
        "confusion": "Puzzled delivery with hesitant pacing and questioning tone.",
        "gratitude": "Sincere, warm delivery with appreciative softness.",
        "pride": "Steady, confident delivery with grounded satisfaction.",
        "doubt": "Careful, skeptical delivery with restrained uncertainty.",
        "calm": "Even, grounded, composed delivery.",
        "excitement": "Energetic, eager delivery with lively pacing.",
        "disappointment": "Muted, let-down delivery with restrained frustration.",
    }
    return descriptions.get(emotion, "Natural, emotionally appropriate delivery.")


async def task_hume_distill_generate_text_samples(
    perEmotion: int = 2,
    maxSamples: int = 24,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    per_emotion = max(1, min(int(perEmotion or 2), 10))
    max_samples = max(1, min(int(maxSamples or 24), 240))
    for emotion, prompts in EMOTION_PROMPTS.items():
        for i in range(per_emotion):
            base = prompts[i % len(prompts)]
            modifier = MODIFIERS[(i // len(prompts)) % len(MODIFIERS)]
            samples.append(
                {
                    "sourceId": f"ops-text-{emotion}-{i + 1:03d}",
                    "split": "train" if i < max(1, math.floor(per_emotion * 0.8)) else "validation",
                    "expectedEmotion": emotion,
                    "text": f"{base} {modifier}",
                    "models": {"language": {"sentiment": {}, "toxicity": {}}},
                }
            )
            if len(samples) >= max_samples:
                return {"samples": samples, "count": len(samples)}
    return {"samples": samples[:max_samples], "count": min(len(samples), max_samples)}


async def task_hume_distill_generate_media_samples(
    perEmotion: int = 1,
    maxSamples: int = 6,
    modalities: list[str] | None = None,
    synthesizeAudio: bool = True,
    imageUrls: list[str] | None = None,
) -> dict[str, Any]:
    selected_modalities = {str(item).lower() for item in (modalities or ["audio"])}
    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_emotion = max(1, min(int(perEmotion or 1), 5))
    max_samples = max(1, min(int(maxSamples or 6), 120))

    if "audio" in selected_modalities and synthesizeAudio:
        for emotion, prompts in EMOTION_PROMPTS.items():
            for i in range(per_emotion):
                if len(samples) >= max_samples:
                    return {"samples": samples, "errors": errors, "count": len(samples), "errorCount": len(errors)}
                text = prompts[i % len(prompts)]
                tts = await hume_emotion.task_hume_tts_synthesize(
                    text=text,
                    description=_emotion_voice_description(emotion),
                    format={"type": "wav"},
                )
                audio_base64 = _extract_tts_audio_base64(tts.get("response") or {})
                if tts.get("error") or not audio_base64:
                    errors.append(
                        {
                            "sourceId": f"ops-audio-{emotion}-{i + 1:03d}",
                            "error": tts.get("error") or "tts response did not include audio",
                        }
                    )
                    continue
                samples.append(
                    {
                        "sourceId": f"ops-audio-{emotion}-{i + 1:03d}",
                        "split": "train" if i < max(1, math.floor(per_emotion * 0.8)) else "validation",
                        "expectedEmotion": emotion,
                        "text": "",
                        "transcript": text,
                        "modality": "audio",
                        "files": [
                            {
                                "name": f"ops-audio-{emotion}-{i + 1:03d}.wav",
                                "mimeType": "audio/wav",
                                "base64": audio_base64,
                            }
                        ],
                        "models": {"prosody": {"granularity": "utterance"}},
                    }
                )

    if "image" in selected_modalities:
        for index, url in enumerate(imageUrls or []):
            if len(samples) >= max_samples:
                break
            samples.append(
                {
                    "sourceId": f"ops-image-{index + 1:03d}",
                    "split": "train",
                    "expectedEmotion": "",
                    "text": "",
                    "modality": "image",
                    "urls": [str(url)],
                    "models": {"face": {"fps_pred": 1}},
                }
            )

    return {"samples": samples, "errors": errors, "count": len(samples), "errorCount": len(errors)}


async def task_hume_distill_collect_teacher_labels(
    samples: list[dict[str, Any]] | None = None,
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 1_000,
    concurrency: int = 2,
    maxSamples: int = 24,
) -> dict[str, Any]:
    if not samples:
        return {"error": "samples are required", "examples": []}
    selected = samples[: max(1, min(int(maxSamples or 24), len(samples)))]
    sem = asyncio.Semaphore(max(1, min(int(concurrency or 2), 6)))

    async def collect_one(index: int, sample: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            urls = sample.get("urls") if isinstance(sample.get("urls"), list) else []
            files = sample.get("files") if isinstance(sample.get("files"), list) else []
            modality = hume_emotion._infer_modality(  # noqa: SLF001
                text=str(sample.get("text") or ""),
                urls=[str(url) for url in urls],
                modality=str(sample.get("modality") or ""),
            )
            result = await hume_emotion.task_hume_expression_analyze_teacher(
                text=str(sample.get("text") or ""),
                urls=urls,
                files=files,
                fileBase64=str(sample.get("fileBase64") or ""),
                modality=modality,
                waitForResult=True,
                timeoutMs=int(timeoutMs or 120_000),
                pollIntervalMs=int(pollIntervalMs or 1_000),
                models=sample.get("models"),
            )
            if result.get("error"):
                return {
                    "sourceId": sample.get("sourceId") or f"ops-text-{index + 1:04d}",
                    "split": sample.get("split") or "train",
                    "error": result.get("error"),
                }
            input_obj: dict[str, Any] = {
                "text": sample.get("text") or "",
                "transcript": sample.get("transcript") or "",
                "urls": urls,
                "fileCount": len(files) + (1 if sample.get("fileBase64") else 0),
            }
            # Extract audio/image features inline so training can use them later
            if files:
                for part in files:
                    if not isinstance(part, dict):
                        continue
                    mt = str(part.get("mimeType") or "").lower()
                    is_audio = "audio" in mt or "wav" in mt
                    is_image = "image" in mt
                    if not (is_audio or is_image):
                        continue
                    try:
                        import base64 as _b64
                        encoded = str(part.get("base64") or part.get("dataBase64") or "")
                        raw = _b64.b64decode(encoded, validate=False) if encoded else b""
                        if raw and is_audio:
                            from kotodama.primitives.hume_audio_head import extract_wav_features
                            feats = extract_wav_features(raw)
                            if feats:
                                input_obj["audioFeatures"] = feats
                        elif raw and is_image:
                            from kotodama.primitives.hume_image_head import extract_image_features
                            input_obj["imageFeatures"] = extract_image_features(raw, mt)
                    except Exception:  # noqa: BLE001
                        pass
                    break  # first matching file is enough
            return {
                "schema": "com.etzhayyim.apps.hume.distillationExample.v1",
                "sourceId": sample.get("sourceId") or f"ops-text-{index + 1:04d}",
                "split": sample.get("split") or "train",
                "modality": modality,
                "input": input_obj,
                "labels": result.get("normalized"),
                "teacherRawRef": {"jobId": result.get("jobId")},
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

    results = await asyncio.gather(*(collect_one(i, sample) for i, sample in enumerate(selected)))
    examples = [row for row in results if not row.get("error")]
    errors = [row for row in results if row.get("error")]
    return {"examples": examples, "errors": errors, "count": len(examples), "errorCount": len(errors)}


async def task_hume_distill_train_student_text(
    examples: list[dict[str, Any]] | None = None,
    includeModel: bool = False,
) -> dict[str, Any]:
    rows = [row for row in (examples or []) if row.get("labels") and row.get("input", {}).get("text")]
    if not rows:
        return {"error": "examples with labels are required"}
    model = _train(rows)
    report = _evaluate(rows, model)
    result = {
        "modelSummary": {
            "schema": model["schema"],
            "rows": model["training"]["rows"],
            "dataHash": model["training"]["dataHash"],
            "algorithm": model["algorithm"],
            "emotionCount": len(model["emotionCentroids"]),
            "vocabSize": len(model["vocab"]),
        },
        "report": report,
    }
    if includeModel:
        result["model"] = model
    return result


async def task_hume_distill_train_student_media(
    examples: list[dict[str, Any]] | None = None,
    includeModel: bool = False,
) -> dict[str, Any]:
    rows = [row for row in (examples or []) if row.get("labels") and row.get("modality")]
    if not rows:
        return {"error": "media examples with labels are required"}
    model = _train_media(rows)
    report = _evaluate_media(rows, model)
    result = {
        "modelSummary": {
            "schema": model["schema"],
            "rows": model["training"]["rows"],
            "dataHash": model["training"]["dataHash"],
            "algorithm": model["algorithm"],
            "emotionCount": len(model["emotionCentroids"]),
            "vocabSize": len(model["vocab"]),
            "modalities": model.get("modalities") or [],
        },
        "report": report,
    }
    if includeModel:
        result["model"] = model
    return result


async def task_hume_distill_run_text_pipeline(
    perEmotion: int = 2,
    maxSamples: int = 24,
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 1_000,
    concurrency: int = 2,
    artifactDir: str = "",
    writeArtifacts: bool = True,
) -> dict[str, Any]:
    run_id = _run_id()
    generated = await task_hume_distill_generate_text_samples(perEmotion=perEmotion, maxSamples=maxSamples)
    collected = await task_hume_distill_collect_teacher_labels(
        samples=generated["samples"],
        timeoutMs=timeoutMs,
        pollIntervalMs=pollIntervalMs,
        concurrency=concurrency,
        maxSamples=maxSamples,
    )
    if collected.get("error") or not collected.get("examples"):
        return {"runId": run_id, "error": collected.get("error") or "no examples collected", "collected": collected}
    trained = await task_hume_distill_train_student_text(examples=collected["examples"], includeModel=True)
    if trained.get("error"):
        return {"runId": run_id, "error": trained["error"], "collected": collected}

    model = trained.pop("model")
    sft = _sft_rows(collected["examples"])
    manifest = {
        "schema": "com.etzhayyim.apps.hume.distillationRunManifest.v1",
        "runId": run_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sampleCount": len(generated["samples"]),
        "exampleCount": len(collected["examples"]),
        "errorCount": len(collected["errors"]),
        "modelSummary": trained["modelSummary"],
        "report": trained["report"],
    }
    if writeArtifacts:
        root = _artifact_dir(artifactDir, run_id)
        paths = {
            "samples": str(root / "samples.json"),
            "distillation": str(root / "distillation.jsonl"),
            "sft": str(root / "sft.jsonl"),
            "model": str(root / "student-text-model.json"),
            "report": str(root / "student-text-report.json"),
            "manifest": str(root / "manifest.json"),
        }
        Path(paths["samples"]).write_text(json.dumps(generated["samples"], indent=2) + "\n")
        Path(paths["distillation"]).write_text("\n".join(json.dumps(row) for row in collected["examples"]) + "\n")
        Path(paths["sft"]).write_text("\n".join(json.dumps(row) for row in sft) + "\n")
        Path(paths["model"]).write_text(json.dumps(model, indent=2) + "\n")
        Path(paths["report"]).write_text(json.dumps(trained["report"], indent=2) + "\n")
        manifest["artifactPaths"] = paths
        Path(paths["manifest"]).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


async def task_hume_distill_run_media_pipeline(
    perEmotion: int = 1,
    maxSamples: int = 6,
    modalities: list[str] | None = None,
    imageUrls: list[str] | None = None,
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 1_000,
    concurrency: int = 1,
    artifactDir: str = "",
    writeArtifacts: bool = True,
) -> dict[str, Any]:
    run_id = _run_id("hume-distill-media")
    generated = await task_hume_distill_generate_media_samples(
        perEmotion=perEmotion,
        maxSamples=maxSamples,
        modalities=modalities,
        synthesizeAudio=True,
        imageUrls=imageUrls,
    )
    if generated.get("error") or not generated.get("samples"):
        return {"runId": run_id, "error": generated.get("error") or "no media samples generated", "generated": generated}
    collected = await task_hume_distill_collect_teacher_labels(
        samples=generated["samples"],
        timeoutMs=timeoutMs,
        pollIntervalMs=pollIntervalMs,
        concurrency=concurrency,
        maxSamples=maxSamples,
    )
    if collected.get("error") or not collected.get("examples"):
        return {"runId": run_id, "error": collected.get("error") or "no media examples collected", "generated": generated, "collected": collected}

    trained = await task_hume_distill_train_student_media(examples=collected["examples"], includeModel=True)
    if trained.get("error"):
        return {"runId": run_id, "error": trained["error"], "generated": generated, "collected": collected}

    model = trained.pop("model")
    sft = _sft_rows(collected["examples"])
    manifest = {
        "schema": "com.etzhayyim.apps.hume.mediaDistillationRunManifest.v1",
        "runId": run_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sampleCount": len(generated["samples"]),
        "exampleCount": len(collected["examples"]),
        "generationErrorCount": len(generated.get("errors") or []),
        "teacherErrorCount": len(collected["errors"]),
        "modalities": sorted({str(row.get("modality") or "") for row in collected["examples"] if row.get("modality")}),
        "modelSummary": trained["modelSummary"],
        "report": trained["report"],
        "nextTrainingStep": "Replace this metadata/transcript bootstrap head with audio/image encoder heads after collecting enough examples.",
    }
    if writeArtifacts:
        root = _artifact_dir(artifactDir, run_id)
        paths = {
            "samples": str(root / "samples.json"),
            "distillation": str(root / "distillation.jsonl"),
            "sft": str(root / "sft.jsonl"),
            "model": str(root / "student-media-model.json"),
            "report": str(root / "student-media-report.json"),
            "manifest": str(root / "manifest.json"),
        }
        Path(paths["samples"]).write_text(json.dumps(generated["samples"], indent=2) + "\n")
        Path(paths["distillation"]).write_text("\n".join(json.dumps(row) for row in collected["examples"]) + "\n")
        Path(paths["sft"]).write_text("\n".join(json.dumps(row) for row in sft) + "\n")
        Path(paths["model"]).write_text(json.dumps(model, indent=2) + "\n")
        Path(paths["report"]).write_text(json.dumps(trained["report"], indent=2) + "\n")
        manifest["artifactPaths"] = paths
        Path(paths["manifest"]).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


async def task_hume_distill_train_student_audio(
    examples: list[dict[str, Any]] | None = None,
    includeModel: bool = False,
) -> dict[str, Any]:
    """Train an audio prosody centroid model from examples that have input.audioFeatures."""
    from kotodama.primitives.hume_audio_head import train_audio_centroid

    rows = [row for row in (examples or []) if row.get("labels") and (row.get("input") or {}).get("audioFeatures")]
    if not rows:
        return {"error": "audio examples with audioFeatures and labels are required"}
    model = train_audio_centroid(rows)
    n = len(rows)
    result: dict[str, Any] = {
        "modelSummary": {
            "schema": model["schema"],
            "rows": n,
            "algorithm": model["algorithm"],
            "featureKeys": model["featureKeys"],
            "emotionCount": len(model["emotionCentroids"]),
        },
    }
    if includeModel:
        result["model"] = model
    return result


async def task_hume_distill_train_student_image(
    examples: list[dict[str, Any]] | None = None,
    includeModel: bool = False,
) -> dict[str, Any]:
    """Train an image visual centroid model from examples that have input.imageFeatures."""
    from kotodama.primitives.hume_image_head import train_image_centroid

    rows = [row for row in (examples or []) if row.get("labels") and (row.get("input") or {}).get("imageFeatures")]
    if not rows:
        return {"error": "image examples with imageFeatures and labels are required"}
    model = train_image_centroid(rows)
    n = len(rows)
    result: dict[str, Any] = {
        "modelSummary": {
            "schema": model["schema"],
            "rows": n,
            "algorithm": model["algorithm"],
            "featureKeys": model["featureKeys"],
            "emotionCount": len(model["emotionCentroids"]),
        },
    }
    if includeModel:
        result["model"] = model
    return result


def register(worker: Any, timeout_ms: int = 900_000) -> None:
    worker.task(task_type="hume.distill.generateTextSamples", single_value=False, timeout_ms=30_000)(
        task_hume_distill_generate_text_samples
    )
    worker.task(task_type="hume.distill.generateMediaSamples", single_value=False, timeout_ms=timeout_ms)(
        task_hume_distill_generate_media_samples
    )
    worker.task(task_type="hume.distill.collectTeacherLabels", single_value=False, timeout_ms=timeout_ms)(
        task_hume_distill_collect_teacher_labels
    )
    worker.task(task_type="hume.distill.trainStudentText", single_value=False, timeout_ms=120_000)(
        task_hume_distill_train_student_text
    )
    worker.task(task_type="hume.distill.trainStudentMedia", single_value=False, timeout_ms=120_000)(
        task_hume_distill_train_student_media
    )
    worker.task(task_type="hume.distill.trainStudentAudio", single_value=False, timeout_ms=120_000)(
        task_hume_distill_train_student_audio
    )
    worker.task(task_type="hume.distill.trainStudentImage", single_value=False, timeout_ms=120_000)(
        task_hume_distill_train_student_image
    )
    worker.task(task_type="hume.distill.runTextPipeline", single_value=False, timeout_ms=timeout_ms)(
        task_hume_distill_run_text_pipeline
    )
    worker.task(task_type="hume.distill.runMediaPipeline", single_value=False, timeout_ms=timeout_ms)(
        task_hume_distill_run_media_pipeline
    )
