from typing import TypedDict
from langgraph.graph import StateGraph, END

class SuitProcurementState(TypedDict):
    fabric_data: dict
    compliance_status: bool
    final_approval: bool

def validate_fabric_specs(state: SuitProcurementState):
    # Simulate CAD/Material compliance check
    quality = state.get('fabric_data', {}).get('quality', 0)
    return {'compliance_status': quality > 80}

def finalize_order(state: SuitProcurementState):
    return {'final_approval': state['compliance_status']}

graph = StateGraph(SuitProcurementState)
graph.add_node('validate', validate_fabric_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
