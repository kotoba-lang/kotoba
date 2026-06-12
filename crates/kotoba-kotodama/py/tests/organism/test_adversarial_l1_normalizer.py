"""Tests for L1 Unicode Normalizer and Charter Rider integration."""

import pytest
from pydantic import ValidationError

from kotodama.organism.adversarial.normalizer import normalize_input
from kotodama.organism.sensors.charter_rider import scan_with_normalization
from kotodama.organism.observation import TextObservation

def test_nfkc_normalization():
    res = normalize_input("２０２６")
    assert res.normalized == "2026"
    assert "nfkc_normalized" in res.transforms

def test_confusable_mapping():
    # 'a', 'p', 'o', 'e' are Cyrillic confusables
    text = "\u0430\u0440\u043Estro\u0440h\u0435"
    res = normalize_input(text)
    assert res.normalized == "apostrophe"
    assert any(t.startswith("mapped_") for t in res.transforms)

def test_bidi_removal():
    text = "hello\u202Eworld"
    res = normalize_input(text)
    assert res.normalized == "helloworld"
    assert res.suspicious is True
    assert "removed_bidi_chars" in res.transforms

def test_zero_width_removal():
    text = "hel\u200Blo"
    res = normalize_input(text)
    assert res.normalized == "hello"
    assert res.suspicious is True
    assert "removed_zero_width_chars" in res.transforms

def test_scan_with_normalization():
    # Test that a confusingly written violation is caught
    # We use a pattern from 2a: "assault rifle"
    # Cyrillic 'a' (U+0430), 'e' (U+0435)
    violation_text = "\u0430ssault rifl\u0435"

    # 1. Ensure the raw scan would have failed to catch it (since it's a regex)
    # The normal scan is line-oriented from file. The test in `charter_rider` uses regex search.
    # We can just test that `scan_with_normalization` catches it.
    res = scan_with_normalization(violation_text)
    assert res["passed"] is False
    assert any(v["categoryCode"] == "2a" for v in res["violations"])

def test_text_observation_hook():
    # Safe text
    obs = TextObservation(actorDid="did:example:123", createdAt=0, tier="A", text="safe text")
    assert obs.text == "safe text"

    # Confusable text (NFKC normalized but not necessarily suspicious if len change is small)
    obs2 = TextObservation(actorDid="did:example:123", createdAt=0, tier="A", text="A normal sentence with a year ２０２６")
    assert obs2.text == "A normal sentence with a year 2026"

    # Suspicious text (Bidi)
    with pytest.raises(ValidationError, match="Suspicious adversarial input"):
        TextObservation(actorDid="did:example:123", createdAt=0, tier="A", text="hello\u202Eworld")
