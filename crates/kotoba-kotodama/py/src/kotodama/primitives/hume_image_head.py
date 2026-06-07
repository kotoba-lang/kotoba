"""Visual feature-based image student encoder head for Hume distillation.

Extracts 6 visual features from PNG (stdlib zlib/struct full-decode) or
any format (byte-histogram sampling) and scores emotions via a heuristic
table or trained centroid model.
Algorithm label: visual_bootstrap_v1.
"""

from __future__ import annotations

import math
import struct
import time
import zlib
from typing import Any

FEATURE_KEYS = ("luminance", "r_weight", "g_weight", "b_weight", "saturation", "contrast")

_HEURISTIC: dict[str, list[tuple[str, float, float]]] = {
    # (feature, weight_when_high, weight_when_low)
    "luminance": [
        ("joy", 0.30, 0.00), ("excitement", 0.25, 0.00), ("gratitude", 0.20, 0.00),
        ("sadness", 0.00, 0.25), ("doubt", 0.00, 0.15), ("anxiety", 0.00, 0.10),
    ],
    "r_weight": [
        ("anger", 0.30, 0.00), ("excitement", 0.25, 0.00), ("joy", 0.20, 0.00),
        ("calm", 0.00, 0.15), ("sadness", 0.00, 0.10),
    ],
    "g_weight": [
        ("calm", 0.25, 0.00), ("relief", 0.20, 0.00), ("gratitude", 0.15, 0.00),
        ("anger", 0.00, 0.10), ("anxiety", 0.00, 0.10),
    ],
    "b_weight": [
        ("calm", 0.25, 0.00), ("sadness", 0.20, 0.00), ("doubt", 0.15, 0.00),
        ("excitement", 0.00, 0.10), ("anger", 0.00, 0.15),
    ],
    "saturation": [
        ("excitement", 0.35, 0.00), ("joy", 0.30, 0.00), ("anger", 0.25, 0.00),
        ("calm", 0.00, 0.25), ("sadness", 0.00, 0.20),
    ],
    "contrast": [
        ("anxiety", 0.25, 0.00), ("excitement", 0.20, 0.00), ("anger", 0.15, 0.00),
        ("calm", 0.00, 0.25), ("sadness", 0.00, 0.15),
    ],
}

NON_EMOTION_LABELS = {
    "toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate",
}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _decode_png_pixels(data: bytes) -> tuple[int, int, int, list[int]] | None:
    """Return (width, height, channels, flat_pixels) for 8-bit PNG, else None."""
    if len(data) < 16 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None

    pos = 8
    width = height = 0
    bit_depth = color_type = 0
    idat: list[bytes] = []

    while pos + 12 <= len(data):
        chunk_len = struct.unpack_from(">I", data, pos)[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + chunk_len]
        pos += 12 + chunk_len

        if chunk_type == b"IHDR":
            if len(chunk_data) < 10:
                return None
            width, height = struct.unpack_from(">II", chunk_data)
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        elif chunk_type == b"IDAT":
            idat.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if not (width and height and idat):
        return None
    if bit_depth != 8:
        return None

    # Supported color types: 0=Grayscale, 2=RGB, 6=RGBA
    if color_type == 0:
        ch = 1
    elif color_type == 2:
        ch = 3
    elif color_type == 6:
        ch = 4
    else:
        return None

    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error:
        return None

    stride = 1 + width * ch
    if len(raw) < stride * height:
        return None

    pixels: list[int] = []
    prev = [0] * (width * ch)

    for y in range(height):
        base = y * stride
        ft = raw[base]
        row = list(raw[base + 1 : base + 1 + width * ch])

        if ft == 0:
            pass
        elif ft == 1:
            for x in range(ch, len(row)):
                row[x] = (row[x] + row[x - ch]) & 0xFF
        elif ft == 2:
            for x in range(len(row)):
                row[x] = (row[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(len(row)):
                left = row[x - ch] if x >= ch else 0
                row[x] = (row[x] + (left + prev[x]) // 2) & 0xFF
        elif ft == 4:
            for x in range(len(row)):
                left = row[x - ch] if x >= ch else 0
                ul = prev[x - ch] if x >= ch else 0
                row[x] = (row[x] + _paeth(left, prev[x], ul)) & 0xFF

        pixels.extend(row)
        prev = row

    return width, height, ch, pixels


def _sample_bytes_features(data: bytes) -> dict[str, float]:
    """Derive visual proxies by sampling raw file bytes (format-agnostic fallback)."""
    n = len(data)
    if n < 64:
        return {k: 0.5 for k in FEATURE_KEYS}

    step = max(1, n // 512)
    sampled = [data[i] for i in range(0, n, step)][:512]
    mean = sum(sampled) / len(sampled)
    luminance = mean / 255.0
    variance = sum((b - mean) ** 2 for b in sampled) / len(sampled)
    contrast = min(1.0, math.sqrt(variance) / 128.0)
    # crude R/G/B proxies from byte-value distribution
    low = sum(1 for b in sampled if b < 85) / len(sampled)
    mid = sum(1 for b in sampled if 85 <= b < 170) / len(sampled)
    high = sum(1 for b in sampled if b >= 170) / len(sampled)
    return {
        "luminance": luminance,
        "r_weight": high,
        "g_weight": mid,
        "b_weight": low,
        "saturation": contrast,
        "contrast": contrast,
    }


def _pixels_to_features(
    width: int, height: int, ch: int, pixels: list[int]
) -> dict[str, float]:
    """Compute 6 visual features from decoded pixel values."""
    n_pixels = width * height
    if n_pixels < 1:
        return {k: 0.5 for k in FEATURE_KEYS}

    step = max(1, n_pixels // 4096)
    r_vals, g_vals, b_vals, lum_vals = [], [], [], []

    for i in range(0, n_pixels, step):
        base = i * ch
        if ch == 1:
            r = g = b = pixels[base]
        elif ch >= 3:
            r, g, b = pixels[base], pixels[base + 1], pixels[base + 2]
        else:
            r = g = b = pixels[base]

        lum = int(0.299 * r + 0.587 * g + 0.114 * b)
        r_vals.append(r)
        g_vals.append(g)
        b_vals.append(b)
        lum_vals.append(lum)

    n = len(lum_vals) or 1
    mean_r = sum(r_vals) / n
    mean_g = sum(g_vals) / n
    mean_b = sum(b_vals) / n
    mean_lum = sum(lum_vals) / n

    total_rgb = mean_r + mean_g + mean_b + 1e-6
    r_weight = mean_r / total_rgb
    g_weight = mean_g / total_rgb
    b_weight = mean_b / total_rgb

    # saturation proxy: distance from gray normalised by brightness
    sat_vals = [
        math.sqrt(
            (r - mean_r) ** 2 + (g - mean_g) ** 2 + (b - mean_b) ** 2
        )
        for r, g, b in zip(r_vals, g_vals, b_vals)
    ]
    saturation = min(1.0, (sum(sat_vals) / n) / 128.0)

    lum_var = sum((l - mean_lum) ** 2 for l in lum_vals) / n
    contrast = min(1.0, math.sqrt(lum_var) / 128.0)

    return {
        "luminance": mean_lum / 255.0,
        "r_weight": r_weight,
        "g_weight": g_weight,
        "b_weight": b_weight,
        "saturation": saturation,
        "contrast": contrast,
    }


def extract_image_features(
    image_bytes: bytes, mime_type: str = ""
) -> dict[str, float]:
    """Extract visual features from image bytes.

    Attempts full PNG pixel decode; falls back to byte-histogram sampling for
    JPEG and other formats.
    """
    mt = (mime_type or "").lower()
    if "png" in mt or image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        decoded = _decode_png_pixels(image_bytes)
        if decoded:
            w, h, ch, px = decoded
            return _pixels_to_features(w, h, ch, px)

    return _sample_bytes_features(image_bytes)


def _score_heuristic(features: dict[str, float]) -> list[dict[str, float]]:
    totals: dict[str, float] = {}
    for feat, table in _HEURISTIC.items():
        v = features.get(feat, 0.5)
        for emotion, w_high, w_low in table:
            totals[emotion] = totals.get(emotion, 0.0) + w_high * v + w_low * (1.0 - v)
    max_s = max(totals.values()) if totals else 1.0
    norm = max_s or 1.0
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


def score_image(
    features: dict[str, float],
    model: dict[str, Any] | None = None,
) -> list[dict[str, float]]:
    """Return sorted emotion scores from image features."""
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
        fallback_globals = [
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


def predict_image_emotion(
    image_bytes: bytes,
    mime_type: str = "",
    model: dict[str, Any] | None = None,
    caution: str = "",
) -> dict[str, Any]:
    """Return normalizedExpression.v1 dict from image bytes."""
    features = extract_image_features(image_bytes, mime_type)
    top = score_image(features, model)
    primary = top[0] if top else None
    algorithm = (model or {}).get("algorithm") or "visual_heuristic_v1"
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
        "evidence": {"modality": "image", "imageFeatures": features},
    }


def train_image_centroid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Train a centroid emotion model from examples with input.imageFeatures and labels."""
    centroids: dict[str, dict[str, float]] = {}
    weights: dict[str, float] = {}
    primary_counts: dict[str, int] = {}
    global_scores: dict[str, float] = {}

    for row in rows:
        features: dict[str, float] = (row.get("input") or {}).get("imageFeatures") or {}
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
        "schema": "com.etzhayyim.apps.hume.studentImageExpressionModel.v1",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "algorithm": "visual_centroid_v1",
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
