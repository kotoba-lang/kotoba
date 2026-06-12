"""Tests for _classify, _today, _utc_now pure helpers in onion_crawl.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import onion_crawl as OC


# ─── _utc_now ────────────────────────────────────────────────────────────────

def test_utc_now_ends_with_z() -> None:
    assert OC._utc_now().endswith("Z")


def test_utc_now_matches_pattern() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", OC._utc_now())


def test_utc_now_no_microseconds() -> None:
    assert "." not in OC._utc_now()


def test_utc_now_has_t_separator() -> None:
    assert "T" in OC._utc_now()


# ─── _today ──────────────────────────────────────────────────────────────────

def test_today_matches_date_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", OC._today())


def test_today_no_time_component() -> None:
    assert "T" not in OC._today()


def test_today_is_string() -> None:
    assert isinstance(OC._today(), str)


# ─── _classify ───────────────────────────────────────────────────────────────

def test_classify_returns_dict() -> None:
    result = OC._classify("some text")
    assert isinstance(result, dict)


def test_classify_has_required_keys() -> None:
    result = OC._classify("text about drugs cocaine")
    assert "category" in result
    assert "threatIndicators" in result
    assert "riskScore" in result


def test_classify_empty_text_returns_unknown() -> None:
    result = OC._classify("")
    assert result["category"] == "unknown"
    assert result["riskScore"] == 0
    assert result["threatIndicators"] == []


def test_classify_benign_text_returns_unknown() -> None:
    result = OC._classify("welcome to our cooking website, recipes and food blog")
    assert result["category"] == "unknown"
    assert result["riskScore"] == 0


def test_classify_drugs_keywords() -> None:
    result = OC._classify("buy cocaine and heroin here")
    assert result["category"] == "drugs"
    assert result["riskScore"] > 0
    assert len(result["threatIndicators"]) > 0


def test_classify_marketplace_keywords() -> None:
    result = OC._classify("dark market vendor escrow btc payment")
    assert result["category"] == "marketplace"
    assert "market" in result["threatIndicators"] or "vendor" in result["threatIndicators"]


def test_classify_weapons_keywords() -> None:
    result = OC._classify("buy weapon firearm ammo here")
    assert result["category"] == "weapons"


def test_classify_fraud_keywords() -> None:
    result = OC._classify("fresh cvv fullz carding shop")
    assert result["category"] == "fraud"


def test_classify_hacking_keywords() -> None:
    result = OC._classify("0day exploit botnet ddos stresser")
    assert result["category"] == "hacking"


def test_classify_ransomware_keywords() -> None:
    result = OC._classify("ransomware victim decryptor negotiat")
    assert result["category"] == "ransomware"


def test_classify_risk_score_increases_with_more_keywords() -> None:
    result_few = OC._classify("cocaine")
    result_many = OC._classify("cocaine heroin mdma lsd meth")
    assert result_many["riskScore"] >= result_few["riskScore"]


def test_classify_risk_score_capped_at_100() -> None:
    very_long = " ".join(["cocaine", "heroin", "mdma", "lsd", "meth",
                           "weapon", "firearm", "cvv", "fullz", "exploit",
                           "botnet", "ransomware", "victim"] * 5)
    result = OC._classify(very_long)
    assert result["riskScore"] <= 100


def test_classify_threat_indicators_sorted() -> None:
    result = OC._classify("btc monero market vendor")
    indicators = result["threatIndicators"]
    assert indicators == sorted(indicators)


def test_classify_threat_indicators_no_duplicates() -> None:
    result = OC._classify("cocaine cocaine cocaine")
    assert len(result["threatIndicators"]) == len(set(result["threatIndicators"]))


def test_classify_case_insensitive() -> None:
    lower_result = OC._classify("cocaine")
    upper_result = OC._classify("COCAINE")
    assert lower_result["category"] == upper_result["category"]
