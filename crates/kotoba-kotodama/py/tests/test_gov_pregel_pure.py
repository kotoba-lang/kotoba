"""
Pure tests for Gov Fractal Pregel Graph Nodes.
Verifies the state transitions and conditional routing logic for the Map-Reduce and BFS expansion.
"""

import pytest
from typing import Dict, Any

from kotodama.agents.gov_pregel import (
    GovFractalState,
    fetch_jurisdictions,
    fetch_agencies,
    ingest_signals,
    extract_entities,
    bfs_expansion,
    analyze_policy,
)

@pytest.mark.asyncio
async def test_fetch_jurisdictions():
    initial_state = GovFractalState(target_did="global", level="global", discovered_entities=[], signals=[], policy_changes=[])
    new_state = await fetch_jurisdictions(initial_state)
    assert len(new_state["discovered_entities"]) > 0
    assert new_state["discovered_entities"][0]["did"] == "did:web:gov.etzhayyim.com:country:jpn"

@pytest.mark.asyncio
async def test_fetch_agencies():
    initial_state = GovFractalState(target_did="did:web:gov.etzhayyim.com:country:jpn", level="country", discovered_entities=[], signals=[], policy_changes=[])
    new_state = await fetch_agencies(initial_state)
    assert len(new_state["discovered_entities"]) > 0
    assert "moj" in new_state["discovered_entities"][0]["did"]

@pytest.mark.asyncio
async def test_extract_entities_and_bfs_expansion():
    initial_state = GovFractalState(
        target_did="did:web:gov.etzhayyim.com:country:jpn:moj", 
        level="agency", 
        discovered_entities=[], 
        signals=[{"type": "wet_diff", "content": "Civil affairs division updated."}], 
        policy_changes=[]
    )
    
    # 1. Extract entities should find a sub-agency
    state_after_extract = await extract_entities(initial_state)
    assert len(state_after_extract["discovered_entities"]) == 1
    assert "civil_affairs" in state_after_extract["discovered_entities"][0]["did"]

    # 2. BFS expansion conditional edge should route to fan_out_agencies because new entities were found
    next_node = await bfs_expansion(state_after_extract)
    assert next_node == "fan_out_agencies"

@pytest.mark.asyncio
async def test_bfs_expansion_stop_at_sub_agency():
    # If we are already at the lowest allowed level, do not expand further
    initial_state = GovFractalState(
        target_did="did:web:gov.etzhayyim.com:country:jpn:moj:civil_affairs", 
        level="sub_agency", 
        discovered_entities=[{"did": "some_further_entity"}], 
        signals=[], 
        policy_changes=[]
    )
    
    next_node = await bfs_expansion(initial_state)
    assert next_node == "analyze_policy"

@pytest.mark.asyncio
async def test_analyze_policy():
    initial_state = GovFractalState(
        target_did="did:web:gov.etzhayyim.com:country:jpn:moj", 
        level="agency", 
        discovered_entities=[], 
        signals=[{"type": "wet_diff", "content": "Update"}], 
        policy_changes=[]
    )
    
    new_state = await analyze_policy(initial_state)
    assert len(new_state["policy_changes"]) == 1
    assert new_state["policy_changes"][0]["id"] == "doc123"
