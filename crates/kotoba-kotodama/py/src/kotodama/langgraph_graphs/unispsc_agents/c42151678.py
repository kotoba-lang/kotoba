from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    material: str
    is_sterile_ready: bool
    validation_passed: bool

def validate_holder_specs(state: ProcurementState):
    # Business logic for mixing slab holder quality assurance
    material = state.get('material', '').lower()
    passed = material in ['stainless steel', 'medical grade silicone', 'autoclavable plastic']
    return {'validation_passed': passed}

def approval_node(state: ProcurementState):
    return {'validation_passed': True if state['validation_passed'] else False}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_holder_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
