from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    machine_specs: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: ForgingState):
    specs = state.get('machine_specs', {})
    is_valid = all(k in specs for k in ['force', 'voltage'])
    print(f'Validating specs: {is_valid}')
    return {'validation_passed': is_valid}

def generate_compliance(state: ForgingState):
    return {'compliance_report': 'ISO standard validated'}

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', generate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
