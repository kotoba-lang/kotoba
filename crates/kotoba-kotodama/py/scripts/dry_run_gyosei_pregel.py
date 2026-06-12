"""
Dry run script for the Gyosei Procedure Execution Pregel Graph.
"""
import asyncio
import json
from kotodama.agents.gyosei_procedure_pregel import (
    GyoseiProcedureState,
    fetch_pending_cases,
    fan_out_procedures,
    start_procedure,
    gather_evidence,
    generate_draft,
    review_gate,
    submit_draft,
    commit_case_state
)

async def dry_run():
    print("--- 🚀 Starting Dry Run: Gyosei Procedure Execution ---")
    
    # 1. Map-Reduce (Intake & Dispatch)
    print("\\n[Phase 1] Intake & Dispatch")
    state = GyoseiProcedureState(batch_id="batch_20260515_01", cases=[], current_case_id=None, agency_org_id=None, instance_key=None, evidence={}, draft_payload=None, review_status="pending", submission_status="pending")
    state = await fetch_pending_cases(state)
    print(f"Pending cases fetched: {json.dumps(state['cases'], indent=2)}")
    
    await fan_out_procedures(state)
    
    # 2. Individual Case Workflow
    case_id = state["cases"][0]["case_id"]
    agency_org_id = state["cases"][0]["agency_org_id"]
    
    print(f"\\n[Phase 2] Executing workflow for Case: {case_id} (Agency: {agency_org_id})")
    case_state = GyoseiProcedureState(
        batch_id="batch_20260515_01",
        cases=[],
        current_case_id=case_id,
        agency_org_id=agency_org_id,
        instance_key=None,
        evidence={},
        draft_payload=None,
        review_status="pending",
        submission_status="pending"
    )
    
    case_state = await start_procedure(case_state)
    print(f"Procedure started. Instance Key: {case_state['instance_key']}")
    
    case_state = await gather_evidence(case_state)
    print(f"Evidence gathered (using Vertex govOrg contacts): {json.dumps(case_state['evidence'], indent=2)}")
    
    case_state = await generate_draft(case_state)
    print(f"LLM drafted payload: {json.dumps(case_state['draft_payload'], indent=2)}")
    
    # Simulate Human/HAR Review Gate approval
    case_state["review_status"] = "approved"
    next_node = await review_gate(case_state)
    print(f"Review Gate check returned: '{next_node}'")
    
    if next_node == "submit_draft":
        case_state = await submit_draft(case_state)
        print(f"Draft submitted via MCP. Status: {case_state['submission_status']}")
        
    await commit_case_state(case_state)
    print(f"✅ Committed final state for case: {case_id}")
    
    print("\\n--- 🎉 Dry Run Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(dry_run())
