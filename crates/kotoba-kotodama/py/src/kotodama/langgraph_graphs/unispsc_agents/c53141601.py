from typing import TypedDict
from langgraph.graph import StateGraph, END

class PinCushionState(TypedDict):
    spec_data: dict
    is_validated: bool

def validate_cushion_specs(state: PinCushionState):
    specs = state.get('spec_data', {})
    is_safe = all(key in specs for key in ['material_composition', 'filling_material_safety'])
    print(f'Validating specifications: {specs}')
    return {'is_validated': is_safe}

def process_workflow(state: PinCushionState):
    print('Running pin cushion procurement workflow...')
    return state

graph = StateGraph(PinCushionState)
graph.add_node('validate', validate_cushion_specs)
graph.add_node('process', process_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
