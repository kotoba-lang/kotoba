import io
import struct
import wave
import pytest
from pydantic import TypeAdapter
from PIL import Image

from kotodama.organism.observation import (
    Observation,
    TextObservation,
    ImageObservation,
    AudioObservation,
    NumericObservation,
    TimeseriesObservation,
    image_joucho_delta,
    audio_joucho_delta,
    numeric_joucho_delta,
    timeseries_joucho_delta,
)
from kotodama.organism.joucho_types import JouchoDelta

# 1. 5 modality 全て の discriminator serialization roundtrip
def test_discriminator_serialization_roundtrip():
    adapter = TypeAdapter(Observation)

    text_obs = TextObservation(
        actorDid="did:web:test", createdAt=123, tier="A", text="hello"
    )
    assert adapter.validate_python(text_obs.model_dump()) == text_obs

    image_obs = ImageObservation(
        actorDid="did:web:test", createdAt=123, tier="B", image=b"img", mime_type="image/png"
    )
    assert adapter.validate_python(image_obs.model_dump()) == image_obs

    audio_obs = AudioObservation(
        actorDid="did:web:test", createdAt=123, tier="C", internal_only=True, audio=b"aud", sample_rate=16000, channels=1
    )
    assert adapter.validate_python(audio_obs.model_dump()) == audio_obs

    numeric_obs = NumericObservation(
        actorDid="did:web:test", createdAt=123, tier="A", value=42.0, unit="celsius"
    )
    assert adapter.validate_python(numeric_obs.model_dump()) == numeric_obs

    ts_obs = TimeseriesObservation(
        actorDid="did:web:test", createdAt=123, tier="B", values=[1.0, 2.0], timestamps=[1, 2], unit="hpa"
    )
    assert adapter.validate_python(ts_obs.model_dump()) == ts_obs

# 2. 1x1 px PNG / 1ms WAV / float / list の minimal sample で feature extractor 動作 確認
def test_image_feature_extractor():
    # 1x1 px PNG
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    obs = ImageObservation(
        actorDid="did:web:test", createdAt=123, tier="A", image=buf.getvalue(), mime_type="image/png"
    )
    delta = image_joucho_delta(obs)
    # Red is high saturation, so kanjou and seimei should be > 0.
    # Entropy of 1 pixel is 0.
    assert isinstance(delta, JouchoDelta)
    assert delta.kanjou > 0
    assert delta.seimei > 0
    assert delta.kankaku == 0

def test_audio_feature_extractor():
    # 1ms WAV (e.g., a few samples)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        # 16 samples = 1ms
        frames = struct.pack("<16h", *([16384] * 16))
        w.writeframes(frames)

    obs = AudioObservation(
        actorDid="did:web:test", createdAt=123, tier="A", audio=buf.getvalue(), sample_rate=16000, channels=1
    )
    delta = audio_joucho_delta(obs)
    assert isinstance(delta, JouchoDelta)
    assert delta.kankaku > 0
    assert delta.yokkyu > 0

def test_numeric_feature_extractor():
    obs = NumericObservation(
        actorDid="did:web:test", createdAt=123, tier="A", value=100.0, unit="ms"
    )
    delta = numeric_joucho_delta(obs, baseline=50.0)
    assert isinstance(delta, JouchoDelta)
    assert delta.kakushin < 0 # -50 * 5 = -250
    assert delta.yokkyu > 0   # 50 * 2 = 100

def test_timeseries_feature_extractor():
    obs = TimeseriesObservation(
        actorDid="did:web:test", createdAt=123, tier="A", values=[10.0, 20.0, 30.0], timestamps=[1, 2, 3], unit="hz"
    )
    delta = timeseries_joucho_delta(obs)
    assert isinstance(delta, JouchoDelta)
    assert delta.yokkyu > 0
    assert delta.kakushin < 0

# 3. internal_only=True flag が PostSink (mock) で drop さ れる tes
class MockPostSink:
    def __init__(self):
        self.posted = []

    def send(self, obs: Observation):
        if obs.internal_only:
            return # DROP
        self.posted.append(obs)

def test_internal_only_dropped_by_post_sink():
    sink = MockPostSink()

    obs_public = TextObservation(actorDid="did:web:test", createdAt=123, tier="A", text="public")
    obs_internal = TextObservation(actorDid="did:web:test", createdAt=123, tier="C", text="secret", internal_only=True)

    sink.send(obs_public)
    sink.send(obs_internal)

    assert len(sink.posted) == 1
    assert sink.posted[0] == obs_public

# 4. 子供 fail-closed: vision_pii_filter mock が ChildDetected raise → Observation 構築 失敗 verify
class ChildDetected(Exception):
    pass

def mock_vision_pii_filter(image_bytes: bytes) -> bytes:
    if b"child" in image_bytes:
        raise ChildDetected("Child detected in image, rejecting frame.")
    return image_bytes

def create_image_observation_with_filter(actorDid: str, tier: str, image: bytes) -> ImageObservation:
    filtered_image = mock_vision_pii_filter(image)
    return ImageObservation(
        actorDid=actorDid,
        createdAt=123,
        tier=tier,
        image=filtered_image,
        mime_type="image/jpeg",
        pii_filter_applied=True
    )

def test_vision_pii_filter_fail_closed():
    # 正常系
    obs = create_image_observation_with_filter("did:web:test", "A", b"normal image data")
    assert obs.pii_filter_applied is True

    # 異常系 (子供検出)
    with pytest.raises(ChildDetected):
        create_image_observation_with_filter("did:web:test", "A", b"contains child face data")

