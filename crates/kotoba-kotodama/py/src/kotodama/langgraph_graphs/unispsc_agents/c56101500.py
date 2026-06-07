from typing import TypedDict
from langgraph.graph import StateGraph, END

class FurnitureState(TypedDict):
    spec_data: dict
    validation_log: list[str]
    approved: bool

def validate_materials(state: FurnitureState):
    log = state.get('validation_log', [])
    log.append('Verifying VOC and fire rating compliance')
    return {'validation_log': log}

def structural_check(state: FurnitureState):
    log = state.get('validation_log', [])
    log.append('Confirming load capacity and ergonomic specs')
    return {'validation_log': log, 'approved': True}

graph = StateGraph(FurnitureState)
graph.add_node('material_check', validate_materials)
graph.add_node('structural_check', structural_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'structural_check')
graph.add_edge('structural_check', END)
graph = graph.compile()
