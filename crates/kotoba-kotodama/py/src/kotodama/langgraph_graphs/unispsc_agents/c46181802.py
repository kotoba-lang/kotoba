from typing import TypedDict
from langgraph.graph import StateGraph, END

class SafetyGlassesState(TypedDict):
    order_id: str
    compliance_docs: list
    is_compliant: bool

def validate_compliance(state: SafetyGlassesState):
    docs = state.get('compliance_docs', [])
    valid = any('ANSI_Z87.1' in doc or 'JIS_T8147' in doc for doc in docs)
    return {'is_compliant': valid}

graph = StateGraph(SafetyGlassesState)
graph.add_node('validate', validate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
