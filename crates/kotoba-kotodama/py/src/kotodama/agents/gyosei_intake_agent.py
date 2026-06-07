"""
Gyosei Intake Agent.
Handles public intake from Yoro social messages and drafts procedures.
"""

import logging
from typing import Dict, Any, List, TypedDict, Optional

logger = logging.getLogger(__name__)

class GyoseiIntakeState(TypedDict):
    """State for conversational intake via Yoro."""
    user_did: str
    agency_did: str
    messages: List[Dict[str, Any]]
    intent: Optional[str]
    procedure_schema: Optional[Dict[str, Any]]
    collected_info: Dict[str, Any]
    draft_payload: Optional[Dict[str, Any]]
    draft_ready: bool
    submitted: bool

async def listen_yoro_messages(state: GyoseiIntakeState) -> GyoseiIntakeState:
    logger.info(f"[gyosei_intake] Listening to messages from {state.get('user_did')}")
    # Triggered by webhook/poll on yoro.etzhayyim.com chat/mention
    return state

async def classify_intent(state: GyoseiIntakeState) -> str:
    """LLM Node / Conditional Edge"""
    logger.info("[gyosei_intake] Classifying user intent")
    # Identify if the user wants to start a procedure, ask a question, etc.
    if state.get("intent") == "start_procedure":
        return "start_procedure"
    return "gather_missing_info" # Default fallback for chat

async def start_procedure(state: GyoseiIntakeState) -> GyoseiIntakeState:
    logger.info("[gyosei_intake] Starting procedure via MCP")
    # Call MCP: com.etzhayyim.apps.gyosei.startProcedure
    state["procedure_schema"] = {"fields": ["name", "address", "reason"]}
    return state

async def gather_missing_info(state: GyoseiIntakeState) -> str:
    """Check if all required schema fields are collected."""
    logger.info("[gyosei_intake] Checking collected info")
    if state.get("draft_ready"):
        return "generate_draft"
    # Otherwise, would send a message back to user via Yoro
    return "listen_yoro_messages"

async def generate_draft(state: GyoseiIntakeState) -> GyoseiIntakeState:
    logger.info("[gyosei_intake] Generating JSON draft")
    # LLM construct draft
    state["draft_payload"] = state["collected_info"]
    return state

async def submit_draft(state: GyoseiIntakeState) -> GyoseiIntakeState:
    logger.info("[gyosei_intake] Submitting draft on behalf of user")
    # Call MCP: com.etzhayyim.apps.gyosei.submitDraft
    state["submitted"] = True
    return state
