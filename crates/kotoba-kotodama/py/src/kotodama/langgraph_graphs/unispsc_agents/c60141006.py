from typing import TypedDict
from langgraph.graph import StateGraph, END

class BlockProcurementState(TypedDict):
    material_safety_passed: bool
    age_rating_verified: bool
    compliant: bool

def validate_safety(state: BlockProcurementState):
    state['material_safety_passed'] = True
    return state

def check_compliance(state: BlockProcurementState):
    state['compliant'] = state.get('material_safety_passed', False)
    return state

graph = StateGraph(BlockProcurementState)
graph.add_node('safety_check', validate_safety)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
