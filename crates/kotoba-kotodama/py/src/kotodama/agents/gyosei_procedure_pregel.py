"""
Gyosei Procedure Execution Pregel Graph Nodes.
Implements the administrative procedure dispatch and execution loop.
"""

import logging
from typing import Dict, Any, List, TypedDict, Optional

logger = logging.getLogger(__name__)

class GyoseiProcedureState(TypedDict):
    """State dict for the gyosei-procedure-pregel LangGraph."""
    batch_id: str
    cases: List[Dict[str, Any]]
    current_case_id: Optional[str]
    agency_org_id: Optional[str]
    instance_key: Optional[int]
    evidence: Dict[str, Any]
    draft_payload: Optional[Dict[str, Any]]
    review_status: str  # 'pending', 'approved', 'rejected'
    submission_status: str # 'pending', 'submitted', 'failed'


async def fetch_pending_cases(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Fetching pending cases for batch {state.get('batch_id')}")
    # MCP: Query RW for cases requiring submission
    state["cases"] = [{"case_id": "case-001", "agency_org_id": "moj-01"}]
    return state


async def fan_out_procedures(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info("[gyosei_pregel] Fanning out procedures (Send API)")
    return state


async def start_procedure(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Starting procedure for {state.get('current_case_id')}")
    # MCP: Call com.etzhayyim.apps.gyosei.startProcedure
    state["instance_key"] = 9999
    return state


async def gather_evidence(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Gathering evidence for case {state.get('current_case_id')}")
    # Use contact info from vertex_gov_org to map out the submission route
    state["evidence"] = {
        "applicant_did": "did:web:natural-person.etzhayyim.com",
        "target_address": "Tokyo, Chiyoda-ku..."
    }
    return state


async def generate_draft(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Generating draft payload for {state.get('current_case_id')}")
    # LLM node: construct payload
    state["draft_payload"] = {"form_field_1": "John Doe", "form_field_2": "Requested Action"}
    return state


async def review_gate(state: GyoseiProcedureState) -> str:
    """Conditional Edge: human in the loop"""
    logger.info(f"[gyosei_pregel] Review gate for {state.get('current_case_id')}")
    if state.get("review_status") == "approved":
        return "submit_draft"
    else:
        return "commit_case_state" # End here if not approved


async def submit_draft(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Submitting draft for {state.get('current_case_id')}")
    # MCP: Call com.etzhayyim.apps.gyosei.submitDraft
    state["submission_status"] = "submitted"
    return state


async def commit_case_state(state: GyoseiProcedureState) -> GyoseiProcedureState:
    logger.info(f"[gyosei_pregel] Committing case state for {state.get('current_case_id')}")
    # MCP: Update status in RW
    return state
