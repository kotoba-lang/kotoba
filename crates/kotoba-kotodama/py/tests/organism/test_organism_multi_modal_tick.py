"""Multi-modal observation + tick integration tests.

Verifies R1 multi-modal push() + tick() -> JouchoScores path.
"""

import io
from typing import Any

from PIL import Image

from kotodama.organism.inbox import InboundCommit
from kotodama.organism.observation import (
    ImageObservation,
    NumericObservation,
    TextObservation,
)
from kotodama.organism.organism import Organism


def _make_stub_graph() -> Any:
    class StubGraph:
        def invoke(self, state: dict) -> str:
            return "stub"

    return StubGraph()


def _make_organism() -> Organism:
    org = Organism(
        code="stub",
        graph=_make_stub_graph(),
    )
    # Birth → ACTIVE so tick() runs its body (else the lifecycle gate
    # early-returns a no-op dummy cadence with default neutral joucho).
    org.lifecycle.handle_birth(org.actor_did)
    return org


def test_multi_modal_tick_joucho_shift():
    """Push 3 modalities -> tick -> verify JouchoScores shift."""
    org = _make_organism()

    # 1. Text Observation (tier A)
    org.inbox.push(
        TextObservation(
            actorDid="did:web:test",
            createdAt=123,
            tier="A",
            text="hello world",
        )
    )

    # 2. Image Observation (Solid red image for high saturation)
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    org.inbox.push(
        ImageObservation(
            actorDid="did:web:test",
            createdAt=123,
            tier="B",
            image=buf.getvalue(),
            mime_type="image/png",
        )
    )

    # 3. Numeric Observation (Large drift)
    org.inbox.push(
        NumericObservation(
            actorDid="did:web:test",
            createdAt=123,
            tier="B",
            value=100.0,
            unit="kg",
            context={"baseline": 50.0},
        )
    )

    res = org.tick(now_ms=1000)
    j = res.cadence.joucho

    # Expected shifts:
    # Image (red): saturation max -> s_mean=255 -> kanjou=10, seimei=5.
    # Numeric (drift=50): kakushin=-250 (cap=-30), yokkyu=100 (cap=30).
    # Text (tier A count=1): focus_delta=0, calm_delta=0.
    # Base: joy=50, calm=50, stress=30, gratitude=50, focus=50
    # Final: joy=60, calm=20, stress=60, gratitude=55, focus=50

    assert j.joy == 60, f"Expected joy=60, got {j.joy}"
    assert j.calm == 20, f"Expected calm=20, got {j.calm}"
    assert j.stress == 60, f"Expected stress=60, got {j.stress}"
    assert j.gratitude == 55, f"Expected gratitude=55, got {j.gratitude}"
    assert j.focus == 50, f"Expected focus=50, got {j.focus}"


def test_internal_only_tier_c_no_leak():
    """tier=C, internal_only=True の observation が tick 後 に external sink に 漏れない."""
    posts = []

    def mock_sink(text: str, **kwargs: Any) -> None:
        posts.append(text)

    org = Organism(
        code="stub",
        graph=_make_stub_graph(),
        post_sink=mock_sink,
    )
    org.lifecycle.handle_birth(org.actor_did)

    # Push internal tier C observation
    org.inbox.push(
        TextObservation(
            actorDid="did:web:test",
            createdAt=123,
            tier="C",
            text="secret internal insight",
        )
    )

    # Also push a regular commit so it tries to post
    org.inbox.add_commit(
        InboundCommit(collection="app.bsky.feed.post", repo="did", rkey="123", time="t")
    )

    # Fast forward post cooldown
    org.cadence_state.last_post_at = -10000000

    org.tick(now_ms=1000)

    assert len(posts) > 0
    assert "secret internal insight" not in posts[0]


def test_extreme_delta_cap():
    """delta cap: 1 observation で extreme delta は 飽和 (±30)."""
    org = _make_organism()

    # Numeric drift of 1000 -> normally yokkyu=2000, kakushin=-5000.
    # Should cap at ±30.
    org.inbox.push(
        NumericObservation(
            actorDid="did:web:test",
            createdAt=123,
            tier="B",
            value=1000.0,
            unit="kg",
            context={"baseline": 0.0},
        )
    )

    res = org.tick(now_ms=1000)
    j = res.cadence.joucho

    assert j.calm == 20, f"Expected calm=20, got {j.calm}"
    assert j.stress == 60, f"Expected stress=60, got {j.stress}"


def test_text_only_regression():
    """existing organism heartbeat regression (text-only)."""
    org = _make_organism()
    org.inbox.push("simple text observation fallback")
    res = org.tick(now_ms=1000)

    j = res.cadence.joucho
    assert j.focus == 50
    assert j.calm == 50
    assert j.joy == 50
    assert j.stress == 30
    assert j.gratitude == 50
