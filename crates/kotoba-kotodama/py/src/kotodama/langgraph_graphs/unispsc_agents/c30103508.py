from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoreState(TypedDict):
    specs: dict
    validation_passed: bool
    thermal_report_url: str

def validate_materials(state: CoreState):
    # Simulate material compliance check for honeycomb structure
    specs = state.get('specs', {})
    passed = specs.get('alloy') == 'C1100' and specs.get('thickness') < 0.5
    return {'validation_passed': passed}

def process_thermal_data(state: CoreState):
    return {'thermal_report_url': 'https://storage.internal/report.pdf'}

graph = StateGraph(CoreState)
graph.add_node('validate', validate_materials)
graph.add_node('thermal', process_thermal_data)
graph.set_entry_point('validate')
graph.add_edge('validate', 'thermal')
graph.add_edge('thermal', END)
graph = graph.compile()
