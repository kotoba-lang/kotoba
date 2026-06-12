from typing import TypedDict
from langgraph.graph import StateGraph, END

class NozzleState(TypedDict):
    spec_data: dict
    validation_errors: list
    is_compliant: bool

def validate_specs(state: NozzleState):
    errors = []
    required = ['material', 'pressure_rating', 'thread_type']
    for field in required:
        if field not in state.get('spec_data', {}):
            errors.append(f'Missing field: {field}')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def check_dual_use(state: NozzleState):
    # logic for high-pressure/corrosion resistant materials control
    if state.get('spec_data', {}).get('material') == 'Hastelloy':
        print('Dual-use review triggered')
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(NozzleState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance_review', check_dual_use)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance_review')
graph.add_edge('compliance_review', END)
graph = graph.compile()
