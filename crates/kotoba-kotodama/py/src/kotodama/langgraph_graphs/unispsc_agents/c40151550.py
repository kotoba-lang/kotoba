from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: PumpState):
    specs = state.get('spec_data', {})
    required = ['pumping_rate_lpm', 'max_discharge_pressure_bar', 'wetted_parts_material']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def technical_review(state: PumpState):
    if state['validation_passed']:
        return {'error_log': ['Technical review successful']}
    return {'error_log': ['Missing mandatory technical specifications']}

graph = StateGraph(PumpState)
graph.add_node('validate', validate_specs)
graph.add_node('review', technical_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'review')
graph.add_edge('review', END)
graph = graph.compile()
