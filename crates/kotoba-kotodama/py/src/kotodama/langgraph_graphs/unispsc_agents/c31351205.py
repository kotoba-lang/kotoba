from typing import TypedDict
from langgraph.graph import StateGraph, END

class TubeAssemblyState(TypedDict):
    spec_data: dict
    validation_results: dict
    approved: bool

def validate_specs(state: TubeAssemblyState):
    specs = state.get('spec_data', {})
    critical_fields = ['Material Grade', 'Pressure Rating']
    valid = all(field in specs for field in critical_fields)
    return {'validation_results': {'complete': valid}}

def check_compliance(state: TubeAssemblyState):
    is_valid = state['validation_results'].get('complete', False)
    return {'approved': is_valid}

graph = StateGraph(TubeAssemblyState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
