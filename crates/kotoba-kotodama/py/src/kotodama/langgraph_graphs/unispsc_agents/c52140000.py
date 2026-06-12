from typing import TypedDict
from langgraph.graph import StateGraph, END

class ApplianceState(TypedDict):
    appliance_type: str
    specs_confirmed: bool
    compliance_passed: bool

def validate_specs(state: ApplianceState):
    print(f'Validating specs for {state.get(appliance_type)}')
    return {'specs_confirmed': True}

def check_compliance(state: ApplianceState):
    print('Checking regulatory compliance...')
    return {'compliance_passed': True}

graph = StateGraph(ApplianceState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
