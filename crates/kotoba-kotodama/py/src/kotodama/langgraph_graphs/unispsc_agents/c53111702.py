from typing import TypedDict
from langgraph.graph import StateGraph, END

class SlipperState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_materials(state: SlipperState):
    materials = state.get('spec_data', {}).get('materials', [])
    is_valid = len(materials) > 0
    return {'validated': is_valid, 'error_log': [] if is_valid else ['Missing material data']}

def check_compliance(state: SlipperState):
    return {'validated': state['validated'] and True}

graph = StateGraph(SlipperState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
