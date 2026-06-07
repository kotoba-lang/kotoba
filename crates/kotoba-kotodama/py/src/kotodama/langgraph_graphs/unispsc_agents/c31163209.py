from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_specs(state: ProcurementState):
    specs = state.get('part_specs', {})
    errors = []
    if 'tolerance' not in specs: errors.append('Missing tolerance data')
    if 'material' not in specs: errors.append('Missing material grade')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

def process_procurement(state: ProcurementState):
    print('Processing bearing holder procurement logic...')
    return {'validation_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
