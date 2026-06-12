from __future__ import annotations

import io
import math
import struct
import wave
from typing import Annotated, Any, Literal, Union

from pydantic import Field, field_validator, model_validator
from .embodiment import TelemetryObservation
from .base import BaseObservation
from .joucho_types import JouchoDelta
from kotodama.organism.adversarial.normalizer import normalize_input
from kotodama.organism.adversarial.semantic import scan_semantic


class TextObservation(BaseObservation):
    kind: Literal["text"] = "text"
    text: str
    _suspicious_l1: bool = False
    _suspicious_l2: bool = False
    _l2_scan_result: dict[str, Any] | None = None

    @field_validator("text")
    @classmethod
    def normalize_and_check_l1(cls, v: str) -> str:
        """L1 validation: normalization and basic suspicious checks."""
        res = normalize_input(v)
        if res.suspicious:
            # L1 is strict and raises an error, as per existing logic.
            raise ValueError(f"L1 adversarial input detected — Suspicious adversarial input: {res.transforms}")
        return res.normalized

    @model_validator(mode='after')
    def check_l2_semantic(self) -> 'TextObservation':
        """L2 validation: semantic adversarial scan."""
        if not self.text:
            return self

        actor_did = self.actorDid
        l2_res = scan_semantic(self.text, actor_did=actor_did)

        if l2_res.suspicious:
            if l2_res.severity == "high":
                raise ValueError(f"L2 adversarial input detected high severity: {l2_res.reason}")

            if l2_res.severity in ("low", "medium"):
                self._suspicious_l2 = True
                self._l2_scan_result = {
                    "severity": l2_res.severity,
                    "patterns": l2_res.flagged_patterns,
                }

        return self


class ImageObservation(BaseObservation):
    kind: Literal["image"] = "image"
    image: Union[bytes, str]  # base64 encoded bytes or file path
    mime_type: str
    pii_filter_applied: bool = False


class AudioObservation(BaseObservation):
    kind: Literal["audio"] = "audio"
    audio: Union[bytes, str]
    sample_rate: int
    channels: int


class NumericObservation(BaseObservation):
    kind: Literal["numeric"] = "numeric"
    value: float
    unit: str
    context: dict[str, Union[str, float, int]] | None = None


class TimeseriesObservation(BaseObservation):
    kind: Literal["timeseries"] = "timeseries"
    values: list[float]
    timestamps: list[int]
    unit: str


Observation = Annotated[
    Union[
        TextObservation,
        ImageObservation,
        AudioObservation,
        NumericObservation,
        TimeseriesObservation,
        TelemetryObservation,
    ],
    Field(discriminator="kind"),
]


def image_joucho_delta(obs: ImageObservation) -> JouchoDelta:
    from PIL import Image

    if isinstance(obs.image, bytes):
        img = Image.open(io.BytesIO(obs.image))
    else:
        img = Image.open(obs.image)

    img = img.convert("HSV")
    h_data, s_data, _ = img.split()

    s_hist = s_data.histogram()
    total_pixels = sum(s_hist)
    if total_pixels == 0:
        return JouchoDelta()

    s_mean = sum(i * count for i, count in enumerate(s_hist)) / total_pixels

    h_hist = h_data.histogram()
    entropy = 0.0
    for count in h_hist:
        if count > 0:
            p = count / total_pixels
            entropy -= p * math.log2(p)

    kanjou_delta = int((s_mean / 255.0) * 10)
    seimei_delta = int((s_mean / 255.0) * 5)

    kankaku_delta = int(entropy)

    return JouchoDelta(kankaku=kankaku_delta, kanjou=kanjou_delta, seimei=seimei_delta)


def audio_joucho_delta(obs: AudioObservation) -> JouchoDelta:
    samples = []
    width = 2
    if isinstance(obs.audio, bytes):
        try:
            with wave.open(io.BytesIO(obs.audio), "rb") as w:
                frames = w.readframes(w.getnframes())
                width = w.getsampwidth()
                fmt = f"<{len(frames) // width}{'h' if width == 2 else 'B'}"
                samples = struct.unpack(fmt, frames)
        except wave.Error:
            frames = obs.audio
            fmt = f"<{len(frames) // 2}h"
            samples = struct.unpack(fmt, frames[: len(frames) // 2 * 2])
    else:
        with wave.open(str(obs.audio), "rb") as w:
            frames = w.readframes(w.getnframes())
            width = w.getsampwidth()
            fmt = f"<{len(frames) // width}{'h' if width == 2 else 'B'}"
            samples = struct.unpack(fmt, frames)

    if not samples:
        return JouchoDelta()

    rms = math.sqrt(sum(float(s) * s for s in samples) / len(samples))
    normalized_rms = rms / (32768.0 if width == 2 else 256.0)

    kankaku_delta = int(normalized_rms * 20)
    yokkyu_delta = int(normalized_rms * 10)

    return JouchoDelta(kankaku=kankaku_delta, yokkyu=yokkyu_delta)


def numeric_joucho_delta(obs: NumericObservation, baseline: float) -> JouchoDelta:
    drift = obs.value - baseline
    kakushin_delta = -int(abs(drift) * 5)
    yokkyu_delta = int(abs(drift) * 2)

    return JouchoDelta(kakushin=kakushin_delta, yokkyu=yokkyu_delta)


def timeseries_joucho_delta(obs: TimeseriesObservation) -> JouchoDelta:
    if len(obs.values) < 2:
        return JouchoDelta()

    slope = obs.values[-1] - obs.values[0]

    yokkyu_delta = int(slope * 2)
    kakushin_delta = -int(abs(slope))

    return JouchoDelta(yokkyu=yokkyu_delta, kakushin=kakushin_delta)
