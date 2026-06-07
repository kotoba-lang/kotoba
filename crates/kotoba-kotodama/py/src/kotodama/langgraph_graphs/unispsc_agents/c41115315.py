from typing import TypedDict
from langgraph.graph import StateGraph, END

class PolariscopesState(TypedDict):
    spec_data: dict
    validation_result: bool
    error_log: list

def validate_optical_specs(state: PolariscopesState):
    specs = state.get('spec_data', {})
    valid = specs.get('wavelength') is not None and specs.get('extinction_ratio') > 1000
    return {'validation_result': valid}

def update_records(state: PolariscopesState):
    if state['validation_result']:
        return {'error_log': ['Compliance verified']}
    return {'error_log': ['Invalid optical intensity']}

graph = StateGraph(PolariscopesState)
graph.add_node('validate', validate_optical_specs)
graph.add_node('record', update_records)
graph.add_edge('validate', 'record')
graph.add_edge('record', END)
graph.set_entry_point('validate')
graph = graph.compile()
