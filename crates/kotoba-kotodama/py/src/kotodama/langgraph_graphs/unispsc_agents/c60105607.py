from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    content_id: str
    curriculum_level: str
    expert_review_status: bool
    is_compliant: bool

def validate_content(state: MaterialState):
    # Simulate academic review logic
    is_valid = state.get('expert_review_status', False)
    return {'is_compliant': is_valid}

workflow = StateGraph(MaterialState)
workflow.add_node('validate', validate_content)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
