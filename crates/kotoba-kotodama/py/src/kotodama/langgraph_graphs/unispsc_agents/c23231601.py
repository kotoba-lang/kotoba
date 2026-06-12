from typing import TypedDict
from langgraph.graph import StateGraph, END

class LathePartState(TypedDict):
    part_id: str
    specifications: dict
    approved: bool

def validate_specs(state: LathePartState):
    specs = state.get('specifications', {})
    is_valid = 'material_grade' in specs and 'dimensional_tolerance' in specs
    return {'approved': is_valid}

def export_check(state: LathePartState):
    # Dual-use logic placeholder
    return {'approved': state['approved']}

graph = StateGraph(LathePartState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', export_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
