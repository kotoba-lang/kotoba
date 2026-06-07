import pytest
from kotodama.agents.gyosei_procedure_pregel import (
    GyoseiProcedureState,
    fetch_pending_cases,
    start_procedure,
    gather_evidence,
    generate_draft,
    review_gate,
    submit_draft
)

@pytest.mark.asyncio
async def test_fetch_cases():
    state = GyoseiProcedureState(batch_id="batch123", cases=[], current_case_id=None, agency_org_id=None, instance_key=None, evidence={}, draft_payload=None, review_status="pending", submission_status="pending")
    new_state = await fetch_pending_cases(state)
    assert len(new_state["cases"]) > 0

@pytest.mark.asyncio
async def test_review_gate_approved():
    state = GyoseiProcedureState(batch_id="batch123", cases=[], current_case_id="case-1", agency_org_id=None, instance_key=None, evidence={}, draft_payload={}, review_status="approved", submission_status="pending")
    next_node = await review_gate(state)
    assert next_node == "submit_draft"

@pytest.mark.asyncio
async def test_review_gate_rejected():
    state = GyoseiProcedureState(batch_id="batch123", cases=[], current_case_id="case-1", agency_org_id=None, instance_key=None, evidence={}, draft_payload={}, review_status="rejected", submission_status="pending")
    next_node = await review_gate(state)
    assert next_node == "commit_case_state"

@pytest.mark.asyncio
async def test_submit():
    state = GyoseiProcedureState(batch_id="batch123", cases=[], current_case_id="case-1", agency_org_id=None, instance_key=None, evidence={}, draft_payload={}, review_status="approved", submission_status="pending")
    new_state = await submit_draft(state)
    assert new_state["submission_status"] == "submitted"
