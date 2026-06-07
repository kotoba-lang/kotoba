"""
Dry run script for the Gov Fractal Pregel Graph.
Simulates the Map-Reduce and BFS execution locally.
"""
import asyncio
import json
from kotodama.agents.gov_pregel import (
    GovFractalState,
    fetch_jurisdictions,
    fan_out_countries,
    fetch_agencies,
    fan_out_agencies,
    ingest_signals,
    extract_entities,
    bfs_expansion,
    analyze_policy,
    commit_state
)

async def dry_run():
    print("--- 🚀 Starting Dry Run: Gov Fractal Pregel (country:jpn) ---")
    
    # 1. Map-Reduce (Periodic Pulse)
    print("\\n[Phase 1] Map-Reduce Fan-Out")
    state = GovFractalState(target_did="global", level="global", discovered_entities=[], signals=[], policy_changes=[])
    state = await fetch_jurisdictions(state)
    print(f"Jurisdictions fetched: {json.dumps(state['discovered_entities'], indent=2)}")
    
    # Simulating country graph transition
    country_did = state["discovered_entities"][0]["did"]
    print(f"\\n➡️ Fanning out to country graph: {country_did}")
    country_state = GovFractalState(target_did=country_did, level="country", discovered_entities=[], signals=[], policy_changes=[])
    
    country_state = await fetch_agencies(country_state)
    print(f"Agencies fetched for {country_did}: {json.dumps(country_state['discovered_entities'], indent=2)}")
    
    # 2. Iterative BFS Deep Research (Agency Agent)
    agency_did = country_state["discovered_entities"][0]["did"]
    print(f"\\n[Phase 2] Iterative BFS Deep Research starting for: {agency_did}")
    agency_state = GovFractalState(target_did=agency_did, level="agency", discovered_entities=[], signals=[], policy_changes=[])
    
    agency_state = await ingest_signals(agency_state)
    print(f"Signals ingested: {json.dumps(agency_state['signals'], indent=2)}")
    
    agency_state = await extract_entities(agency_state)
    print(f"Entities extracted: {json.dumps(agency_state['discovered_entities'], indent=2)}")
    
    next_node = await bfs_expansion(agency_state)
    print(f"BFS Expansion check returned: '{next_node}'")
    
    if next_node == "fan_out_agencies":
        sub_agency_did = agency_state["discovered_entities"][0]["did"]
        print(f"\\n➡️ BFS Expansion triggered. Spawning child agent for: {sub_agency_did}")
        sub_state = GovFractalState(target_did=sub_agency_did, level="sub_agency", discovered_entities=[], signals=[], policy_changes=[])
        
        sub_state = await ingest_signals(sub_state)
        sub_state = await extract_entities(sub_state)
        # Sub-agency does not expand further, routes to analyze
        sub_state["level"] = "sub_agency" 
        sub_next = await bfs_expansion(sub_state)
        print(f"Sub-agency BFS Expansion check returned: '{sub_next}'")
        
        sub_state = await analyze_policy(sub_state)
        print(f"Sub-agency policy analysis: {json.dumps(sub_state['policy_changes'], indent=2)}")
        
        await commit_state(sub_state)
        print(f"✅ Committed state for: {sub_agency_did}")

    # Back to agency level
    agency_state = await analyze_policy(agency_state)
    print(f"\\nAgency policy analysis: {json.dumps(agency_state['policy_changes'], indent=2)}")
    await commit_state(agency_state)
    print(f"✅ Committed state for: {agency_did}")
    
    print("\\n--- 🎉 Dry Run Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(dry_run())
