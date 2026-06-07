from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcureState(TypedDict):
    product_id: str
    compliance_docs: List[str]
    temp_log_verified: bool
    approved: bool

def validate_compliance(state: ProcureState):
    # Simulate regulatory check
    docs = state.get('compliance_docs', [])
    valid = 'GMP_Certificate' in docs and 'ColdChain_Log' in docs
    return {'approved': valid}

graph = StateGraph(ProcureState)
graph.add_node('compliance', validate_compliance)
graph.set_entry_point('compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
