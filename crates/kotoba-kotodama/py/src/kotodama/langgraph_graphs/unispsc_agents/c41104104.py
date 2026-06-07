from typing import TypedDict
from langgraph.graph import StateGraph, END

class TourniquetState(TypedDict):
    product_sku: str
    compliance_docs: list
    is_sterile: bool
    approved: bool

def validate_compliance(state: TourniquetState):
    state['approved'] = all(state.get('compliance_docs', [])) and state.get('is_sterile', False)
    return state

workflow = StateGraph(TourniquetState)
workflow.add_node('validate', validate_compliance)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
