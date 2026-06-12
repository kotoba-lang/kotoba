import pytest
from kotodama.agents.gyosei_intake_agent import (
    GyoseiIntakeState,
    listen_yoro_messages,
    classify_intent,
    start_procedure,
    gather_missing_info,
    generate_draft,
    submit_draft
)
from kotodama.agents.gyosei_internal_processing import (
    GyoseiInternalState,
    receive_submitted_draft,
    validate_schema,
    decision_gate,
    update_case_status,
    notify_user_yoro
)

@pytest.mark.asyncio
async def test_intake_flow():
    # 1. User messages, intent classified
    state = GyoseiIntakeState(user_did="user", agency_did="moj", messages=[], intent="start_procedure", procedure_schema=None, collected_info={}, draft_payload=None, draft_ready=False, submitted=False)
    
    next_node = await classify_intent(state)
    assert next_node == "start_procedure"
    
    # 2. Procedure started
    state = await start_procedure(state)
    assert state["procedure_schema"] is not None
    
    # 3. Fast forward: info collected, draft generated, submitted
    state["draft_ready"] = True
    state["collected_info"] = {"name": "Test"}
    next_node = await gather_missing_info(state)
    assert next_node == "generate_draft"
    
    state = await generate_draft(state)
    assert state["draft_payload"]["name"] == "Test"
    
    state = await submit_draft(state)
    assert state["submitted"] is True

@pytest.mark.asyncio
async def test_internal_flow():
    state = GyoseiInternalState(case_id="case1", agency_did="moj", draft_payload={"name": "Test"}, schema_valid=False, decision="approve", notified=False)
    
    state = await validate_schema(state)
    assert state["schema_valid"] is True
    
    next_node = await decision_gate(state)
    assert next_node == "update_case_status"
    
    state = await notify_user_yoro(state)
    assert state["notified"] is True
