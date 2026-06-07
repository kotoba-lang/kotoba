from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_number: str
    material_compliance: bool
    dimension_check: bool
    approved: bool

def validate_materials(state: ProcurementState):
    state['material_compliance'] = True
    return state

def validate_specs(state: ProcurementState):
    state['dimension_check'] = True
    return state

def final_check(state: ProcurementState):
    state['approved'] = state['material_compliance'] and state['dimension_check']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('materials', validate_materials)
graph.add_node('specs', validate_specs)
graph.add_node('approval', final_check)
graph.set_entry_point('materials')
graph.add_edge('materials', 'specs')
graph.add_edge('specs', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
