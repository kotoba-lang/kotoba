from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class HypnoticsState(TypedDict):
    product_name: str
    compliance_docs: List[str]
    is_approved: bool

def validate_compliance(state: HypnoticsState):
    # Business logic for pharmaceutical regulatory check
    docs = state.get('compliance_docs', [])
    state['is_approved'] = 'GMP' in docs and 'FDA_APPROVAL' in docs
    return state

workflow = StateGraph(HypnoticsState)
workflow.add_node('validation', validate_compliance)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
