from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChassisState(TypedDict):
    spec_data: dict
    validation_report: dict
    approved: bool

def validate_specs(state: ChassisState):
    specs = state.get('spec_data', {})
    is_valid = 'material' in specs and 'tensile_strength' in specs
    return {'validation_report': {'status': 'passed' if is_valid else 'failed'}, 'approved': is_valid}

def compliance_check(state: ChassisState):
    print('Running regulatory safety check...')
    return {'approved': state['approved']}

graph = StateGraph(ChassisState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
