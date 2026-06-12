from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: List[str]

def validate_matrix_specs(state: DentalState):
    log = []
    material = state.get('spec_data', {}).get('material')
    if not material:
        log.append('Error: Missing material specification.')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

def router(state: DentalState):
    return 'compliant' if state['is_compliant'] else 'review'

graph = StateGraph(DentalState)
graph.add_node('validate', validate_matrix_specs)
graph.add_conditional_edges('validate', router, {'compliant': END, 'review': END})
graph.set_entry_point('validate')
graph = graph.compile()
