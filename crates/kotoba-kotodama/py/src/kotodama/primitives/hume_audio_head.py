"""Prosody-based audio student encoder head for Hume distillation.

Extracts 5 acoustic features from WAV PCM bytes using stdlib wave + numpy
and scores emotions via a heuristic table or trained centroid model.
Algorithm label: wav_prosody_bootstrap_v1.
"""

from __future__ import annotations

import io
import math
import struct
import time
import wave
from typing import Any

FEATURE_KEYS = ("rms", "zcr_norm", "spec_centroid", "energy_var", "hf_ratio")

_HEURISTIC: dict[str, list[tuple[str, float, float]]] = {
    # (feature, weight_when_high, weight_when_low)
    "rms": [
        ("joy", 0.30, 0.00), ("excitement", 0.40, 0.00), ("anger", 0.30, 0.00),
        ("pride", 0.20, 0.00), ("sadness", 0.00, 0.30), ("calm", 0.00, 0.20),
        ("disappointment", 0.00, 0.15),
    ],
    "zcr_norm": [
        ("anxiety", 0.40, 0.00), ("anger", 0.30, 0.00), ("excitement", 0.25, 0.00),
        ("confusion", 0.20, 0.00), ("calm", 0.00, 0.30), ("sadness", 0.00, 0.20),
        ("gratitude", 0.00, 0.15),
    ],
    "spec_centroid": [
        ("joy", 0.30, 0.00), ("excitement", 0.25, 0.00),
        ("sadness", 0.00, 0.30), ("calm", 0.00, 0.20), ("doubt", 0.00, 0.15),
    ],
    "energy_var": [
        ("excitement", 0.30, 0.00), ("anger", 0.20, 0.00), ("anxiety", 0.20, 0.00),
        ("calm", 0.00, 0.30), ("sadness", 0.00, 0.20),
    ],
    "hf_ratio": [
        ("anxiety", 0.20, 0.00), ("excitement", 0.15, 0.00),
        ("calm", 0.00, 0.20), ("sadness", 0.00, 0.15),
    ],
}

NON_EMOTION_LABELS = {
    "toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate",
}


def extract_wav_features(audio_bytes: bytes) -> dict[str, float] | None:
    """Return 5 prosody features from WAV PCM bytes, or None if not decodable."""
    try:
        with wave.open(io.BytesIO(audio_bytes)) as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
    except Exception:  # noqa: BLE001
        return None

    if not raw or sampwidth not in (1, 2, 3) or n_channels < 1 or framerate < 1:
        return None

    # Decode PCM to normalised float, take first channel only
    samples: list[float]
    if sampwidth == 1:
        samples = [raw[i] / 128.0 - 1.0 for i in range(0, len(raw), n_channels)]
    elif sampwidth == 2:
        step = 2 * n_channels
        n = len(raw) // step
        samples = [
            struct.unpack_from("<h", raw, i * step)[0] / 32768.0
            for i in range(n)
        ]
    else:  # 24-bit
        step = 3 * n_channels
        samples = []
        for i in range(0, len(raw) - 2, step):
            b = raw[i : i + 3]
            pad = b"\xff" if b[2] >= 0x80 else b"\x00"
            samples.append(struct.unpack("<i", b + pad)[0] / 8388608.0)

    n = len(samples)
    if n < 16:
        return None

    rms = math.sqrt(sum(s * s for s in samples) / n)
    zcr_count = sum(1 for i in range(1, n) if (samples[i] >= 0) != (samples[i - 1] >= 0))
    zcr = min(1.0, zcr_count / n * 10)

    try:
        import numpy as np

        arr = np.array(samples, dtype=np.float32)
        frame_size = min(1024, n)
        n_fft_frames = max(1, n // frame_size)

        centroids: list[float] = []
        for fi in range(n_fft_frames):
            frame = arr[fi * frame_size : (fi + 1) * frame_size]
            if len(frame) < 16:
                continue
            mag = np.abs(np.fft.rfft(frame))
            freqs = np.fft.rfftfreq(len(frame), 1.0 / framerate)
            total = float(np.sum(mag)) or 1.0
            centroids.append(float(np.sum(freqs * mag) / total))

        nyquist = framerate / 2.0
        spec_centroid = (sum(centroids) / len(centroids) / nyquist) if centroids else 0.5
        spec_centroid = min(1.0, max(0.0, spec_centroid))

        analysis = arr[: min(2048, n)]
        mag2 = np.abs(np.fft.rfft(analysis)) ** 2
        freqs = np.fft.rfftfreq(len(analysis), 1.0 / framerate)
        hf_idx = int(np.searchsorted(freqs, 1000.0))
        total_e = float(np.sum(mag2)) or 1.0
        hf_ratio = min(1.0, float(np.sum(mag2[hf_idx:])) / total_e)

        block_size = max(1, n // 16)
        block_rms = [
            float(np.sqrt(np.mean(arr[bi : bi + block_size] ** 2)))
            for bi in range(0, n - block_size + 1, block_size)
        ]
        energy_var = min(1.0, float(np.var(block_rms)) * 100) if len(block_rms) > 1 else 0.0

    except ImportError:
        spec_centroid = zcr
        hf_ratio = zcr
        n_blocks = max(1, n // 16)
        bs = n // n_blocks
        br = [
            math.sqrt(sum(s * s for s in samples[bi : bi + bs]) / max(1, bs))
            for bi in range(0, n - bs + 1, bs)
        ]
        if len(br) > 1:
            mean_r = sum(br) / len(br)
            energy_var = min(1.0, sum((r - mean_r) ** 2 for r in br) / len(br) * 100)
        else:
            energy_var = 0.0

    return {
        "rms": min(1.0, rms),
        "zcr_norm": min(1.0, zcr),
        "spec_centroid": min(1.0, spec_centroid),
        "energy_var": min(1.0, energy_var),
        "hf_ratio": min(1.0, hf_ratio),
    }


def _score_heuristic(features: dict[str, float]) -> list[dict[str, float]]:
    totals: dict[str, float] = {}
    for feat, table in _HEURISTIC.items():
        v = features.get(feat, 0.5)
        for emotion, w_high, w_low in table:
            score = w_high * v + w_low * (1.0 - v)
            totals[emotion] = totals.get(emotion, 0.0) + score
    max_score = max(totals.values()) if totals else 1.0
    norm = max_score or 1.0
    return sorted(
        [{"name": n, "score": min(1.0, s / norm)} for n, s in totals.items() if s > 0],
        key=lambda x: x["score"],
        reverse=True,
    )


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * float(b.get(k, 0.0)) for k, v in a.items())


def _normalize_vec(vec: dict[str, float]) -> None:
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    for k in list(vec):
        vec[k] /= norm


def score_audio(
    features: dict[str, float],
    model: dict[str, Any] | None = None,
) -> list[dict[str, float]]:
    """Return sorted emotion scores from audio features.

    Uses trained centroid model when provided, otherwise falls back to
    the heuristic weight table.
    """
    if model and model.get("emotionCentroids"):
        centroids: dict[str, dict[str, float]] = model["emotionCentroids"]
        priors: dict[str, float] = model.get("primaryPriors") or {}
        scored = []
        for name, centroid in centroids.items():
            if str(name).lower() in NON_EMOTION_LABELS:
                continue
            sim = _cosine(features, centroid)
            prior = float(priors.get(name, 0.0))
            s = max(0.0, min(1.0, sim * 0.82 + prior * 0.18))
            if s > 0:
                scored.append({"name": name, "score": s})
        fallback_globals: list[dict[str, float]] = [
            {"name": item["name"], "score": min(0.25, float(item["score"]))}
            for item in (model.get("globalTopEmotions") or [])
            if str(item.get("name", "")).lower() not in NON_EMOTION_LABELS
        ]
        seen: set[str] = set()
        merged: list[dict[str, float]] = []
        for item in sorted(scored + fallback_globals, key=lambda x: x["score"], reverse=True):
            if item["name"] in seen:
                continue
            seen.add(item["name"])
            merged.append(item)
            if len(merged) >= 12:
                break
        return merged

    return _score_heuristic(features)[:12]


def predict_audio_emotion(
    audio_bytes: bytes,
    model: dict[str, Any] | None = None,
    caution: str = "",
) -> dict[str, Any] | None:
    """Return normalizedExpression.v1 dict from WAV bytes, or None if not WAV."""
    features = extract_wav_features(audio_bytes)
    if features is None:
        return None

    top = score_audio(features, model)
    primary = top[0] if top else None
    algorithm = (model or {}).get("algorithm") or "wav_prosody_heuristic_v1"
    return {
        "schema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "primary": primary,
        "topEmotions": top,
        "confidence": primary["score"] if primary else 0.0,
        "caution": caution or "Expression scores estimate perceived expression.",
        "teacher": {
            "provider": "student",
            "api": "distilled-expression",
            "distilledFrom": "hume-expression-measurement",
            "algorithm": algorithm,
        },
        "evidence": {"modality": "audio", "audioFeatures": features},
    }


def train_audio_centroid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Train a centroid emotion model from examples with input.audioFeatures and labels."""
    centroids: dict[str, dict[str, float]] = {}
    weights: dict[str, float] = {}
    primary_counts: dict[str, int] = {}
    global_scores: dict[str, float] = {}

    for row in rows:
        features: dict[str, float] = (row.get("input") or {}).get("audioFeatures") or {}
        if not features:
            continue
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        primary = labels.get("primary") if isinstance(labels.get("primary"), dict) else {}
        primary_name = primary.get("name")

        for emotion in labels.get("topEmotions") or []:
            name = emotion.get("name")
            score = float(emotion.get("score") or 0.0)
            if not name or str(name).lower() in NON_EMOTION_LABELS:
                continue
            weight = score * 0.35 + (1.5 if name == primary_name else 0.0)
            centroids.setdefault(str(name), {k: 0.0 for k in FEATURE_KEYS})
            weights[str(name)] = weights.get(str(name), 0.0) + weight
            global_scores[str(name)] = global_scores.get(str(name), 0.0) + score
            for fk in FEATURE_KEYS:
                centroids[str(name)][fk] = centroids[str(name)].get(fk, 0.0) + features.get(fk, 0.0) * weight

        if primary_name:
            primary_counts[str(primary_name)] = primary_counts.get(str(primary_name), 0) + 1

    for name, centroid in centroids.items():
        div = weights.get(name, 1.0) or 1.0
        for fk in list(centroid):
            centroid[fk] /= div
        _normalize_vec(centroid)

    n = len(rows)
    total_primary = sum(primary_counts.values()) or 1
    return {
        "schema": "com.etzhayyim.apps.hume.studentAudioExpressionModel.v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "algorithm": "wav_prosody_centroid_v1",
        "featureKeys": list(FEATURE_KEYS),
        "teacher": {"provider": "hume", "api": "expression-measurement"},
        "outputSchema": "com.etzhayyim.apps.hume.normalizedExpression.v1",
        "emotionCentroids": centroids,
        "primaryPriors": {name: cnt / total_primary for name, cnt in primary_counts.items()},
        "globalTopEmotions": [
            {"name": name, "score": s / max(1, n)}
            for name, s in sorted(global_scores.items(), key=lambda x: x[1], reverse=True)[:24]
        ],
        "training": {"rows": n, "sourceIds": [row.get("sourceId") for row in rows]},
    }
