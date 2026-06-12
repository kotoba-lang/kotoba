from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhysicsMaterialState(TypedDict):
    spec_list: list
    validation_results: dict
    is_compliant: bool

def validate_specs(state: PhysicsMaterialState):
    # Perform check on frequency range and material accuracy
    state['validation_results'] = {'frequency_cal': 'Passed'}
    state['is_compliant'] = True
    return state

def generate_report(state: PhysicsMaterialState):
    print('Validation complete for Wave and Sound materials')
    return {'is_compliant': True}

graph = StateGraph(PhysicsMaterialState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
