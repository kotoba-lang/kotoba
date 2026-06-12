from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_type: str
    spec_compliance: bool
    inspection_result: str

def validate_specs(state: ProcurementState):
    compliance = state.get('material_type') == 'Cedar' and state.get('inspection_result') == 'Pass'
    return {'spec_compliance': compliance}

def finalize_order(state: ProcurementState):
    return {'inspection_result': 'Order Confirmed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
