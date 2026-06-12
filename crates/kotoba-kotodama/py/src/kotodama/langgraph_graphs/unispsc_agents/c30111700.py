from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlasterState(TypedDict):
    spec_data: dict
    validated: bool

def validate_materials(state: PlasterState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['tensile_strength_mpa', 'setting_time_minutes'])
    print(f'Validating plaster material compliance: {is_valid}')
    return {'validated': is_valid}

graph = StateGraph(PlasterState)
graph.add_node('validation', validate_materials)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
