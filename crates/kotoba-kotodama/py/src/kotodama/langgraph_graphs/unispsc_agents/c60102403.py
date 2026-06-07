from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MathCardState(TypedDict):
    card_id: str
    curriculum_level: str
    verified: bool
    compliance_report: List[str]

def validate_curriculum(state: MathCardState):
    # Simulate validation logic
    is_valid = state.get('curriculum_level') in ['Pre-K', 'Grade-1', 'Grade-2']
    return {"verified": is_valid, "compliance_report": ["Curriculum check passed"] if is_valid else ["Curriculum check failed"]}

def finalize_spec(state: MathCardState):
    return {"compliance_report": state['compliance_report'] + ["Finalized for procurement"]}

graph = StateGraph(MathCardState)
graph.add_node("validate", validate_curriculum)
graph.add_node("finalize", finalize_spec)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
