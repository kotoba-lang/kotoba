from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExamLightState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_specs(state: ExamLightState):
    specs = state.get('spec_data', {})
    # Check for medical standard compliance (e.g., IEC 60601)
    compliant = specs.get('iso_standard') == 'IEC 60601-2-41'
    return {'is_compliant': compliant}

graph = StateGraph(ExamLightState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
