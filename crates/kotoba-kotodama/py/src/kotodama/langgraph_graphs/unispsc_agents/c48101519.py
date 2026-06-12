from typing import TypedDict
from langgraph.graph import StateGraph, END

class PizzaOvenState(TypedDict):
    spec_data: dict
    validation_status: bool
    compliance_report: str

def validate_specs(state: PizzaOvenState):
    specs = state.get('spec_data', {})
    status = 'temperature_range_celsius' in specs and 'safety_certification' in specs
    return {'validation_status': status}

def generate_report(state: PizzaOvenState):
    return {'compliance_report': 'Safety and performance specs verified' if state['validation_status'] else 'Incomplete specs'}

graph = StateGraph(PizzaOvenState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()
