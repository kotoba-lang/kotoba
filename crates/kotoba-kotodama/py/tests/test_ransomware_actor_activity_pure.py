from __future__ import annotations

from kotodama.langgraph_graphs import ransomware_actor_activity as M


def test_normalize_events_extracts_actor_and_indicators() -> None:
    state = {
        "raw_items": [
            {
                "sourceId": "unit",
                "sourceAuthority": 0.8,
                "title": "LockBit ransomware campaign exploits CVE-2026-12345",
                "summary": "Victims are posted to a leak site. Indicator: bad.example.com",
                "url": "https://example.test/report",
                "published": "2026-05-15",
            }
        ]
    }

    out = M.normalize_events(state)

    assert len(out["events"]) == 1
    event = out["events"][0]
    assert event["actor"] == "LockBit"
    assert "CVE-2026-12345" in event["indicators"]["cves"]
    assert "bad.example.com" in event["indicators"]["domains"]


def test_pregel_score_marks_strong_claim_active() -> None:
    state = {
        "events": [
            {
                "eventId": "e1",
                "actor": "Akira",
                "title": "Akira ransomware leak site update",
                "summary": "CVE-2026-12345 and victim leak site activity",
                "sourceId": "unit",
                "sourceAuthority": 0.75,
                "published": "2026-05-15",
                "indicators": {"domains": ["leak.example"], "cves": ["CVE-2026-12345"], "wallets": []},
            }
        ]
    }

    out = M.pregel_score(state)

    assert out["pregel_summary"]["evaluated"] == 1
    assert out["pregel_summary"]["active"] == 1
    assert out["events"][0]["pregelStatus"] == "active"
    assert out["pregel_summary"]["topActors"][0]["actor"] == "Akira"


def test_onion_item_normalizes_existing_crawl_metadata() -> None:
    item = M._onion_item({
        "onion_host": "lockbitabcd1234.onion",
        "site_did": "did:web:onion.etzhayyim.com:lockbitabcd1234",
        "risk_score": 76,
        "page_count": 4,
        "ransomware_page_count": 2,
        "reachable": True,
        "last_seen": "2026-05-15T00:00:00Z",
        "sample_title": "Leak site",
        "sample_threat_indicators": '["ransomware","leak site"]',
    })

    assert item["sourceId"] == M.ONION_SOURCE_ID
    assert item["onionHost"] == "lockbitabcd1234.onion"
    assert item["url"] == "http://lockbitabcd1234.onion/"
    assert "ransomware_pages=2" in item["summary"]


def test_normalize_events_preserves_onion_host() -> None:
    out = M.normalize_events({
        "raw_items": [
            M._onion_item({
                "onion_host": "akiraexample.onion",
                "risk_score": 80,
                "ransomware_page_count": 1,
                "sample_title": "Akira ransomware leak site update",
                "last_seen": "2026-05-15T00:00:00Z",
            })
        ]
    })

    assert len(out["events"]) == 1
    event = out["events"][0]
    assert event["sourceKind"] == "onion-metadata"
    assert event["onionHost"] == "akiraexample.onion"
    assert event["actor"] == "Akira"


def test_event_entity_id_uses_onion_host() -> None:
    assert (
        M._event_entity_id({"onionHost": "akiraexample.onion", "actor": "Akira"})
        == "onion-site-akiraexample-onion"
    )


def test_build_graph_compiles() -> None:
    assert M.build_graph() is not None
