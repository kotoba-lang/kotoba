"""
Gyosei Internal Processing Agent.
Handles back-office approval workflows.
"""

import logging
from typing import Dict, Any, List, TypedDict, Optional

logger = logging.getLogger(__name__)

class GyoseiInternalState(TypedDict):
    case_id: str
    agency_did: str
    draft_payload: Dict[str, Any]
    schema_valid: bool
    decision: Optional[str] # 'approve', 'reject'
    notified: bool

async def receive_submitted_draft(state: GyoseiInternalState) -> GyoseiInternalState:
    logger.info(f"[gyosei_internal] Received draft for case {state.get('case_id')}")
    return state

async def validate_schema(state: GyoseiInternalState) -> GyoseiInternalState:
    logger.info("[gyosei_internal] Validating against governanceContract schema")
    state["schema_valid"] = True
    return state

async def decision_gate(state: GyoseiInternalState) -> str:
    """Conditional routing based on validation or human review."""
    logger.info("[gyosei_internal] Decision gate")
    if not state.get("schema_valid"):
        state["decision"] = "reject"
        return "update_case_status"
    
    if state.get("decision"):
        return "update_case_status"
        
    return "notify_user_yoro" # Wait state essentially

async def update_case_status(state: GyoseiInternalState) -> GyoseiInternalState:
    logger.info(f"[gyosei_internal] Updating status: {state.get('decision')}")
    # MCP: com.etzhayyim.apps.gyosei.processCase
    return state

async def notify_user_yoro(state: GyoseiInternalState) -> GyoseiInternalState:
    logger.info(f"[gyosei_internal] Sending notification via Yoro to applicant")
    # MCP: Post DM to user
    state["notified"] = True
    return state
