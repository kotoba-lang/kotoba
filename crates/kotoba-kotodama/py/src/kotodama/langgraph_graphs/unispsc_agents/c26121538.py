from typing import TypedDict
from langgraph.graph import StateGraph, END

class WireAssemblyState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: WireAssemblyState):
    specs = state.get('spec_data', {})
    errors = []
    if 'conductor_gauge' not in specs: errors.append('Missing gauge')
    if 'insulation_rating' not in specs: errors.append('Missing insulation')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def assembly_workflow(state: WireAssemblyState):
    return {'validation_passed': True}

graph = StateGraph(WireAssemblyState)
graph.add_node('validate', validate_specs)
graph.add_node('assemble', assembly_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'assemble')
graph.add_edge('assemble', END)
graph = graph.compile()
