from __future__ import annotations

from kotodama import agent_status_web_main


def test_build_status_html_contains_core_mount_points() -> None:
    html = agent_status_web_main.build_status_html()

    assert "Agent Organism Status" in html
    assert 'id="organismState"' in html
    assert 'id="erc8004State"' in html
    assert 'id="runtimeProofState"' in html
    assert 'id="runtimePublication"' in html
    assert 'id="authorityState"' in html
    assert 'id="authorityEffects"' in html
    assert 'id="effectChannels"' in html
    assert 'id="developmentMemory"' in html
    assert 'id="developmentEdges"' in html
    assert 'id="policyAdaptation"' in html
    assert 'id="activePriors"' in html
    assert 'id="counterparties"' in html
    assert 'id="protectedAssets"' in html
    assert 'id="minimaxEvaluations"' in html
    assert 'id="informationHeight"' in html
    assert 'id="informationFlow"' in html
    assert 'id="processes"' in html
    assert "/api/status" in html


def test_status_payload_delegates_to_status_report(monkeypatch) -> None:
    calls: list[str] = []

    def fake_load_status_report(agent_did: str):
        calls.append(agent_did)
        return {"agentDid": agent_did, "organismState": "active"}

    monkeypatch.setattr(agent_status_web_main, "load_status_report", fake_load_status_report)

    assert agent_status_web_main.status_payload("did:etzhayyim:agent:test") == {
        "agentDid": "did:etzhayyim:agent:test",
        "organismState": "active",
    }
    assert calls == ["did:etzhayyim:agent:test"]
