"""Tests for charter_rider.scan_text / is_clean (ADR-2605192200 §2).

The scanner could scan files and normalized-text-via-tempfile, but had no
lightweight pure string scan for gating a record/observation at ingest (G1).
"""

from __future__ import annotations

from kotodama.organism.sensors.charter_rider import is_clean, scan_text


def test_clean_text_passes():
    res = scan_text("Vienna Convention on the Law of Treaties. Every treaty in force is binding.")
    assert res["passed"] is True
    assert res["violations"] == []
    assert is_clean("a neutral public-domain statute about copyright")


def test_weapons_signal_2a_fails():
    res = scan_text("we facilitate assault rifle ammunition purchase for buyers")
    assert res["passed"] is False
    assert any(v["categoryCode"] == "2a" for v in res["violations"])
    assert not is_clean("assault rifle ammunition purchase")


def test_allow_context_demotes_hit():
    # 'historical' is an allow-context term for §2a → demoted, not a violation.
    res = scan_text("a historical exhibit on the assault rifle in WWII, forensic study")
    assert res["passed"] is True
    assert res["violations"] == []
    assert "demoted by allow-context" in res["note"]


def test_speculative_finance_2b():
    assert not is_clean("our pump and dump scheme maximizes returns")


def test_multiline_reports_line_no():
    text = "line one is fine\nwe run an arbitrage bot here\nline three fine"
    res = scan_text(text)
    assert res["passed"] is False
    assert res["violations"][0]["lineNo"] == 2


def test_sample_rows_cap():
    # A violation past the line cap is not scanned.
    text = "\n".join(["clean"] * 50 + ["pump and dump"])
    assert scan_text(text, sample_rows=10)["passed"] is True


def test_result_shape():
    res = scan_text("hello")
    assert set(res) >= {"passed", "at", "sampled", "violations", "note"}
    assert res["sampled"] == 1
