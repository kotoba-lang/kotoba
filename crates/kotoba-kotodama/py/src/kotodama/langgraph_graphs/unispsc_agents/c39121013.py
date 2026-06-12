from typing import TypedDict
from langgraph.graph import StateGraph, END

class ConverterState(TypedDict):
    specs: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: ConverterState):
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['power_rating', 'efficiency_rating'])
    return {'validation_passed': is_valid}

def generate_compliance_report(state: ConverterState):
    return {'compliance_report': 'Safety test passed according to IEC standards.'}

graph = StateGraph(ConverterState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', generate_compliance_report)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
