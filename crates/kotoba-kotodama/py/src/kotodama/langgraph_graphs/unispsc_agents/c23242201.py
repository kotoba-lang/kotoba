from typing import TypedDict
from langgraph.graph import StateGraph, END

class GearGenState(TypedDict):
    spec_data: dict
    validation_passed: bool
    log: list

def validate_specs(state: GearGenState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['precision', 'max_dia'])
    print(f'Validating gear specs: {is_valid}')
    return {'validation_passed': is_valid}

def process_cad(state: GearGenState):
    print('Running CAD simulation for gear teeth profile...')
    return {'log': state.get('log', []) + ['CAD Processing Complete']}

graph = StateGraph(GearGenState)
graph.add_node('validate', validate_specs)
graph.add_node('cad_process', process_cad)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cad_process')
graph.add_edge('cad_process', END)
graph = graph.compile()
