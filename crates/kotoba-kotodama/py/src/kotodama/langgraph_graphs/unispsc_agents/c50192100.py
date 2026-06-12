from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SnackProcurementState(TypedDict):
    product_name: str
    quality_docs: List[str]
    compliance_cleared: bool

def validate_food_safety(state: SnackProcurementState):
    # Business logic for food safety compliance
    docs = state.get('quality_docs', [])
    cleared = 'HACCP' in docs or 'ISO22000' in docs
    return {'compliance_cleared': cleared}

def route_procurement(state: SnackProcurementState):
    return 'process_order' if state['compliance_cleared'] else 'request_documentation'

graph = StateGraph(SnackProcurementState)
graph.add_node('validate', validate_food_safety)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
