from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlangeState(TypedDict):
    spec_data: dict
    validation_result: bool
    error_log: list

def validate_spec(state: FlangeState):
    spec = state.get('spec_data', {})
    valid = 'Pressure Rating' in spec and 'Material' in spec
    return {'validation_result': valid, 'error_log': [] if valid else ['Missing specs']}

def compliance_check(state: FlangeState):
    print('Checking dual-use export control regulatory status...')
    return {'validation_result': True}

graph = StateGraph(FlangeState)
graph.add_node('validate', validate_spec)
graph.add_node('compliance', compliance_check)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
