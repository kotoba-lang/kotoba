from typing import TypedDict
from langgraph.graph import StateGraph, END

class RepairKitState(TypedDict):
    kit_type: str
    material_type: str
    inspection_passed: bool

def validate_materials(state: RepairKitState):
    # Business logic for validating chemical safety of adhesives
    is_valid = state.get('material_type') in ['nylon', 'polyester', 'canvas']
    return {'inspection_passed': is_valid}

def route_verification(state: RepairKitState):
    return 'pass' if state['inspection_passed'] else 'fail'

graph = StateGraph(RepairKitState)
graph.add_node('validate', validate_materials)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
